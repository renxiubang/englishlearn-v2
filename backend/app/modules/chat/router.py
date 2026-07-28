"""聊天模块路由（api.md 接口 4 / 5a / 5b / 18）。

POST /api/chats/{contactId}/messages 按 Content-Type 分流：
- application/json → 5a 文本同步
- multipart/form-data → 5b 语音 SSE 流式
DELETE /api/chats/{contactId}/messages → 18 清空聊天记录
"""

import logging
import uuid

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import UploadFile

from app.core.config import get_settings
from app.core.db import SessionLocal, get_db
from app.core.deps import (
    DEFAULT_USER_ID,
    SessionGuard,
    get_mllm,
    get_session_guard,
    get_speech,
    get_tts,
)
from app.core.errors import bad_request, conflict, not_found, ok
from app.gateway.mllm import MLLMGateway
from app.gateway.tts import TTSGateway
from app.modules.chat import repository as repo
from app.modules.chat.orchestrator import VoiceMessageOrchestrator
from app.modules.speech.service import SpeechService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["chat"])


@router.get("/chats/{contact_id}/messages")
async def get_messages(
    contact_id: str,
    cursor: int | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """接口 4：游标分页历史消息。"""
    if not await repo.get_contact(db, contact_id):
        raise not_found("contact not found")
    page, has_more, next_cursor = await repo.page_messages(
        db, DEFAULT_USER_ID, contact_id, cursor, limit
    )
    return ok({
        "list": [repo.message_to_dict(m) for m in page],
        "hasMore": has_more,
        "nextCursor": next_cursor,
    })


@router.post("/chats/{contact_id}/messages")
async def send_message(
    contact_id: str,
    request: Request,
    mllm: MLLMGateway = Depends(get_mllm),
    tts: TTSGateway = Depends(get_tts),
    speech: SpeechService = Depends(get_speech),
    guard: SessionGuard = Depends(get_session_guard),
):
    """接口 5：文本（5a，JSON 同步）/ 语音（5b，SSE 流式）。"""
    settings = get_settings()

    # 校验联系人（独立短会话，SSE 长流程不占用请求级会话）
    async with SessionLocal() as db:
        contact = await repo.get_contact(db, contact_id)
    if not contact:
        raise not_found("contact not found")

    content_type = request.headers.get("content-type", "")

    # ── 5a 文本同步 ─────────────────────────────────────
    if content_type.startswith("application/json"):
        body = await request.json()
        text = (body.get("text") or "").strip()
        if not text:
            raise bad_request("text is required")

        async with SessionLocal() as db:
            context = await repo.recent_context(
                db, DEFAULT_USER_ID, contact_id, settings.context_limit
            )
            await repo.insert_message(
                db, user_id=DEFAULT_USER_ID, contact_id=contact_id,
                from_side="me", en=text, text_only=True,
            )
            await db.commit()

        reply_en = await mllm.reply_text(contact.persona_prompt, context, text)
        reply_zh = await mllm.translate(reply_en, "en_to_zh") if reply_en else ""

        async with SessionLocal() as db:
            reply_msg = await repo.insert_message(
                db, user_id=DEFAULT_USER_ID, contact_id=contact_id,
                from_side="them", en=reply_en, zh=reply_zh, text_only=True,
            )
            await db.commit()
            reply_id = reply_msg.id

        return ok({
            "reply": {
                "id": reply_id, "from": "them",
                "en": reply_en, "zh": reply_zh, "textOnly": True,
            }
        })

    # ── 5b 语音 SSE ─────────────────────────────────────
    if not content_type.startswith("multipart/form-data"):
        raise bad_request(f"unsupported content-type: {content_type}")

    form = await request.form()
    audio = form.get("audio")
    # 注意：手动 request.form() 解析出的是 starlette 的 UploadFile
    if not isinstance(audio, UploadFile):
        raise bad_request("audio is required")

    session_key = f"{DEFAULT_USER_ID}:{contact_id}"
    if not guard.try_acquire(session_key):
        raise conflict("another voice stream is in progress for this session")

    try:
        # 建流前完成上传校验（400/413 走 JSON 统一包裹）
        upload = await speech.save_upload(audio, f"tmp_{uuid.uuid4().hex[:12]}")
    except Exception:
        guard.release(session_key)
        raise

    orchestrator = VoiceMessageOrchestrator(settings, mllm, tts, speech)

    async def stream():
        try:
            async for event in orchestrator.run(
                user_id=DEFAULT_USER_ID,
                contact_id=contact_id,
                persona_prompt=contact.persona_prompt,
                upload=upload,
            ):
                yield event
        finally:
            guard.release(session_key)
            # 清理送模型的中间 wav
            upload["wav_path"].unlink(missing_ok=True)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.delete("/chats/{contact_id}/messages")
async def clear_messages(
    contact_id: str,
    db: AsyncSession = Depends(get_db),
    speech: SpeechService = Depends(get_speech),
    guard: SessionGuard = Depends(get_session_guard),
):
    """接口 18：清空会话聊天记录（消息 + 音频记录 + 物理文件）。"""
    if not await repo.get_contact(db, contact_id):
        raise not_found("contact not found")

    # 与 5b 同一把会话锁：流进行中清空会产生孤儿文件/幽灵消息，直接 409
    session_key = f"{DEFAULT_USER_ID}:{contact_id}"
    if not guard.try_acquire(session_key):
        raise conflict("another voice stream is in progress for this session")

    try:
        removed, paths = await repo.delete_chat_history(
            db, DEFAULT_USER_ID, contact_id
        )
        await db.commit()
    finally:
        guard.release(session_key)

    # 事务提交后再删物理文件，残留文件不影响数据正确性
    for name in paths:
        speech.path_of(name).unlink(missing_ok=True)
    return ok({"removed": removed})
