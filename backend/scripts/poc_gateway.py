"""模型链路冒烟：TTS → 转录 → 翻译（双向）→ 语义校验 → 流式回复。

前置：多模态服务 (:8000) 与 tts_server (:8880) 均在线。
用法：cd backend && uv run python scripts/poc_gateway.py [可选 16kHz wav 样本路径]
未提供样本时用 TTS 合成一句英文自举（24k PCM → ffmpeg 重采样 16k wav）。
"""

import asyncio
import base64
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402
from app.gateway.mllm import MLLMGateway  # noqa: E402
from app.gateway.tts import TTSGateway  # noqa: E402

SAMPLE_EN = "I played football with my friends today."


def _pcm_to_16k_wav_b64(pcm: bytes, sample_rate: int) -> str:
    """Int16 PCM → 24k wav → ffmpeg 重采样 16k mono wav → base64。"""
    with tempfile.TemporaryDirectory() as td:
        raw_wav = Path(td) / "raw.wav"
        out_wav = Path(td) / "16k.wav"
        with wave.open(str(raw_wav), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(pcm)
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw_wav),
             "-ar", "16000", "-ac", "1", "-sample_fmt", "s16", str(out_wav)],
            check=True,
        )
        return base64.b64encode(out_wav.read_bytes()).decode()


async def main() -> None:
    settings = get_settings()
    mllm = MLLMGateway(settings)
    tts = TTSGateway(settings)

    print(f"[0] ping: mllm={await mllm.ping()} tts={await tts.ping()}")

    # 1. TTS：合成样音（或使用传入的 16kHz wav）
    if len(sys.argv) > 1:
        audio_b64 = base64.b64encode(Path(sys.argv[1]).read_bytes()).decode()
        print(f"[1] TTS skipped, using sample: {sys.argv[1]}")
    else:
        pcm = await tts.synthesize(SAMPLE_EN)
        print(f"[1] TTS ok: {len(pcm)} bytes Int16 PCM @{tts.sample_rate}Hz")
        audio_b64 = _pcm_to_16k_wav_b64(pcm, tts.sample_rate)

    # 2. 转录（en）
    transcription = await mllm.transcribe(audio_b64, "en")
    print(f"[2] transcribe(en): {transcription!r}")

    # 3. 翻译：en→zh → zh→en（阶段B 语法归一化链）
    zh = await mllm.translate(transcription or SAMPLE_EN, "en_to_zh")
    print(f"[3] translate en→zh: {zh!r}")
    en = await mllm.translate(zh, "zh_to_en")
    print(f"    translate zh→en: {en!r}")

    # 4. 语义校验（同一段音频 vs 目标句，预期 consistent=True）
    consistent, reason = await mllm.verify_semantic(audio_b64, SAMPLE_EN)
    print(f"[4] verify_semantic: consistent={consistent} reason={reason!r}")

    # 5. 流式回复（语音输入）
    print("[5] reply_stream: ", end="", flush=True)
    persona = "You are a friendly English teacher chatting with a child."
    async for token in mllm.reply_stream(persona, [], audio_b64=audio_b64):
        print(token, end="", flush=True)
    print()

    await mllm.aclose()
    await tts.aclose()
    print("poc done ✅")


if __name__ == "__main__":
    asyncio.run(main())
