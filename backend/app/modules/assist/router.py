"""辅助卡片模块（api.md 接口 16 / 17）。

- 16 POST /api/assist/translate：中文语音 → 中文文本(zh) → 英文文本(en)
  → TTS 分片(audio_chunk) → audio_end。SSE 流式。TTS 失败以 error 下发（不降级）。
- 17 POST /api/assist/verify：复读语音 + 目标英文 → 语义一致性判定（JSON 同步）。
"""

import base64
import logging
import uuid

from fastapi import APIRouter, Depends, Form, Request, UploadFile
from fastapi.responses import StreamingResponse
from starlette.datastructures import UploadFile as StarletteUploadFile

from app.core.deps import get_mllm, get_speech, get_tts
from app.core.errors import bad_request, ok
from app.core.sse import sse, sse_error
from app.gateway.mllm import MLLMGateway
from app.gateway.tts import TTSGateway
from app.modules.chat.orchestrator import _split_sentences
from app.modules.speech.service import SpeechService, fmt_duration

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/assist", tags=["assist"])


@router.post("/translate")
async def translate(
    request: Request,
    mllm: MLLMGateway = Depends(get_mllm),
    tts: TTSGateway = Depends(get_tts),
    speech: SpeechService = Depends(get_speech),
):
    """接口 16：辅助卡片翻译生成（SSE 流式）。"""
    form = await request.form()
    audio = form.get("audio")
    # 手动 request.form() 解析出的是 starlette 的 UploadFile（fastapi 版是其子类）
    if not isinstance(audio, StarletteUploadFile):
        raise bad_request("audio is required")

    # 建流前上传校验（400/413 JSON 统一包裹）
    upload = await speech.save_upload(audio, f"assist_{uuid.uuid4().hex[:12]}")
    audio_b64 = upload["audio_b64"]

    async def stream():
        try:
            zh = await mllm.transcribe(audio_b64, "zh")
            yield sse("zh", {"zh": zh})

            en = await mllm.translate(zh, "zh_to_en") if zh else ""
            yield sse("en", {"en": en})

            pcm_parts: list[bytes] = []
            seq = 0
            for sentence in _split_sentences(en):
                pcm = await tts.synthesize(sentence)  # 失败抛出 → error
                pcm_parts.append(pcm)
                yield sse(
                    "audio_chunk",
                    {"seq": seq, "base64": base64.b64encode(pcm).decode("ascii")},
                )
                seq += 1

            if not pcm_parts:
                raise RuntimeError("no audio synthesized")

            name = f"assist_{uuid.uuid4().hex[:12]}_tts.wav"
            seconds = speech.save_tts_wav(
                b"".join(pcm_parts), tts.sample_rate, name
            )
            yield sse(
                "audio_end",
                {"url": f"/audio/{name}", "duration": fmt_duration(seconds)},
            )
        except Exception as e:
            logger.warning(f"assist translate failed: {e}")
            yield sse_error(500, str(e))
        finally:
            upload["wav_path"].unlink(missing_ok=True)
            upload["raw_path"].unlink(missing_ok=True)
        yield sse("done")

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/verify")
async def verify(
    audio: UploadFile | None = None,
    en: str = Form(default=""),
    mllm: MLLMGateway = Depends(get_mllm),
    speech: SpeechService = Depends(get_speech),
):
    """接口 17：复读语义校验（JSON 同步）。"""
    if not isinstance(audio, StarletteUploadFile):
        raise bad_request("audio is required")
    target = en.strip()
    if not target:
        raise bad_request("en is required")

    upload = await speech.save_upload(audio, f"verify_{uuid.uuid4().hex[:12]}")
    try:
        consistent, reason = await mllm.verify_semantic(upload["audio_b64"], target)
    finally:
        upload["wav_path"].unlink(missing_ok=True)
        upload["raw_path"].unlink(missing_ok=True)

    data: dict = {"consistent": consistent}
    if not consistent and reason:
        data["reason"] = reason
    return ok(data)
