"""5b 语音消息 SSE 编排（api.md 接口 5b）。

串行两阶段：
- 阶段A（回复优先）：LLM 流式回复文本 → reply_delta；按句断句驱动 TTS →
  reply_audio_chunk（与 delta 交错）；reply_end 收尾（zh 翻译 + 语音落盘）。
- 阶段B（语法归一化链，级联三调用）：transcribe(en) 原始转录（中间产物不下发）
  → translate(en→zh) 得 user_zh → translate(zh→en) 得语法规范 user_en →
  TTS 分片 → 落库我方消息 → user_bubble → done。

TTS 失败降级（5b 保文本）：跳过剩余音频分片，reply_end 的 duration/url 为 null。
"""

import asyncio
import base64
import logging
import re
from typing import AsyncIterator

from app.core.config import Settings
from app.core.db import SessionLocal
from app.core.sse import sse, sse_error
from app.gateway.mllm import MLLMGateway
from app.gateway.sentence import SentenceAccumulator
from app.gateway.tts import TTSGateway
from app.modules.chat import repository as repo
from app.modules.speech.service import SpeechService, fmt_duration

logger = logging.getLogger(__name__)

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENT_SPLIT.split(text) if s.strip()]


class VoiceMessageOrchestrator:
    def __init__(
        self,
        settings: Settings,
        mllm: MLLMGateway,
        tts: TTSGateway,
        speech: SpeechService,
    ):
        self._settings = settings
        self._mllm = mllm
        self._tts = tts
        self._speech = speech

    async def run(
        self,
        *,
        user_id: str,
        contact_id: str,
        persona_prompt: str,
        upload: dict,  # SpeechService.save_upload 的产物
    ) -> AsyncIterator[str]:
        """产出 SSE 事件字符串流。任何异常 → error 事件 + done。"""
        try:
            async for event in self._run_inner(
                user_id=user_id,
                contact_id=contact_id,
                persona_prompt=persona_prompt,
                upload=upload,
            ):
                yield event
        except Exception as e:
            logger.exception("5b stream failed")
            yield sse_error(500, str(e))
        yield sse("done")

    async def _run_inner(
        self, *, user_id: str, contact_id: str, persona_prompt: str, upload: dict
    ) -> AsyncIterator[str]:
        audio_b64: str = upload["audio_b64"]

        # ── 阶段A 准备：占位插入对方消息拿 id ──────────────
        async with SessionLocal() as db:
            context = await repo.recent_context(
                db, user_id, contact_id, self._settings.context_limit
            )
            reply_msg = await repo.insert_message(
                db, user_id=user_id, contact_id=contact_id, from_side="them"
            )
            await db.commit()
            reply_id = reply_msg.id

        yield sse("reply_start", {"id": reply_id})

        # ── 阶段A：delta 与按句 TTS 分片经队列汇聚交错下发 ──
        out_q: asyncio.Queue[tuple[str, dict] | None] = asyncio.Queue()
        sent_q: asyncio.Queue[str | None] = asyncio.Queue()
        reply_parts: list[str] = []
        pcm_parts: list[bytes] = []
        tts_failed = False

        async def tts_worker():
            nonlocal tts_failed
            seq = 0
            while True:
                sentence = await sent_q.get()
                if sentence is None:
                    break
                if tts_failed:
                    continue  # 降级：跳过剩余分片
                try:
                    pcm = await self._tts.synthesize(sentence)
                except Exception as e:
                    logger.warning(f"TTS failed, degrade to text-only: {e}")
                    tts_failed = True
                    continue
                pcm_parts.append(pcm)
                await out_q.put((
                    "reply_audio_chunk",
                    {"seq": seq, "base64": base64.b64encode(pcm).decode("ascii")},
                ))
                seq += 1

        async def producer():
            acc = SentenceAccumulator()
            worker = asyncio.create_task(tts_worker())
            try:
                async for token in self._mllm.reply_stream(
                    persona_prompt, context, audio_b64=audio_b64
                ):
                    reply_parts.append(token)
                    await out_q.put(("reply_delta", {"text": token}))
                    for s in acc.push(token):
                        await sent_q.put(s)
                tail = acc.flush()
                if tail:
                    await sent_q.put(tail)
            finally:
                await sent_q.put(None)
                await worker
                await out_q.put(None)

        producer_task = asyncio.create_task(producer())
        while True:
            item = await out_q.get()
            if item is None:
                break
            yield sse(item[0], item[1])
        await producer_task  # 透传 LLM 流异常

        # ── 阶段A 收尾：zh 翻译、语音落盘、更新对方消息 ─────
        reply_en = "".join(reply_parts).strip()
        reply_zh = (
            await self._mllm.translate(reply_en, "en_to_zh") if reply_en else ""
        )

        reply_duration: str | None = None
        reply_url: str | None = None
        if pcm_parts and not tts_failed:
            tts_name = f"msg_{reply_id}_tts.wav"
            seconds = self._speech.save_tts_wav(
                b"".join(pcm_parts), self._tts.sample_rate, tts_name
            )
            reply_duration = fmt_duration(seconds)
            reply_url = f"/audio/{tts_name}"

        async with SessionLocal() as db:
            msg = await db.get(repo.Message, reply_id)
            if msg:
                msg.en = reply_en
                msg.zh = reply_zh
                msg.duration = reply_duration
            if reply_url:
                await repo.insert_audio_asset(
                    db, kind="tts", path=f"msg_{reply_id}_tts.wav",
                    message_id=reply_id,
                )
            await db.commit()

        yield sse(
            "reply_end",
            {"zh": reply_zh, "duration": reply_duration, "url": reply_url},
        )

        # ── 阶段B：语法归一化链（转录 → en→zh → zh→en）──────
        raw_transcription = await self._mllm.transcribe(audio_b64, "en")
        user_zh = (
            await self._mllm.translate(raw_transcription, "en_to_zh")
            if raw_transcription else ""
        )
        yield sse("user_zh", {"zh": user_zh})

        user_en = (
            await self._mllm.translate(user_zh, "zh_to_en") if user_zh else ""
        )
        yield sse("user_en", {"en": user_en})

        # 我方消息落库（en 存归一化后文本），并绑定原声文件
        user_duration = fmt_duration(upload["duration_sec"])
        async with SessionLocal() as db:
            me_msg = await repo.insert_message(
                db, user_id=user_id, contact_id=contact_id, from_side="me",
                en=user_en, zh=user_zh, duration=user_duration,
            )
            await db.flush()
            me_id = me_msg.id
            await db.commit()

        # 原声文件重命名为 msg_{id}_raw.{ext}
        raw_ext = upload["raw_name"].rsplit(".", 1)[-1]
        raw_name = f"msg_{me_id}_raw.{raw_ext}"
        upload["raw_path"].rename(self._speech.path_of(raw_name))

        # 我方英文合成语音（TTS 分片下发）
        me_pcm_parts: list[bytes] = []
        seq = 0
        tts_ok = True
        for sentence in _split_sentences(user_en):
            try:
                pcm = await self._tts.synthesize(sentence)
            except Exception as e:
                logger.warning(f"stage-B TTS failed, keep text: {e}")
                tts_ok = False
                break
            me_pcm_parts.append(pcm)
            yield sse(
                "user_audio_chunk",
                {"seq": seq, "base64": base64.b64encode(pcm).decode("ascii")},
            )
            seq += 1

        tts_audio = None
        if me_pcm_parts and tts_ok:
            tts_name = f"msg_{me_id}_tts.wav"
            seconds = self._speech.save_tts_wav(
                b"".join(me_pcm_parts), self._tts.sample_rate, tts_name
            )
            tts_audio = {"url": f"/audio/{tts_name}", "duration": fmt_duration(seconds)}

        async with SessionLocal() as db:
            await repo.insert_audio_asset(
                db, kind="user_raw", path=raw_name, message_id=me_id,
                duration_ms=int(upload["duration_sec"] * 1000),
            )
            if tts_audio:
                await repo.insert_audio_asset(
                    db, kind="tts", path=f"msg_{me_id}_tts.wav", message_id=me_id,
                )
            await db.commit()

        yield sse(
            "user_bubble",
            {
                "id": me_id,
                "en": user_en,
                "zh": user_zh,
                "userAudio": {"url": f"/audio/{raw_name}", "duration": user_duration},
                "ttsAudio": tts_audio,
            },
        )
