"""音频资产服务：上传校验、ffmpeg 转码、时长探测、本地落盘。

第一阶段以本地磁盘替代对象存储：文件写入 storage_dir，
对外 URL = /audio/{filename}（main.py StaticFiles 挂载）。
"""

import asyncio
import base64
import wave
from pathlib import Path

from fastapi import UploadFile

from app.core.config import Settings
from app.core.errors import bad_request, payload_too_large


def fmt_duration(seconds: float) -> str:
    """秒 → "m:ss" 展示格式（api.md duration 字段）。"""
    total = max(0, round(seconds))
    return f"{total // 60}:{total % 60:02d}"


async def _run(*cmd: str) -> tuple[int, bytes, bytes]:
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, err = await proc.communicate()
    return proc.returncode or 0, out, err


async def probe_duration(path: Path) -> float:
    """ffprobe 取音频时长（秒）。"""
    code, out, err = await _run(
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path),
    )
    if code != 0:
        raise bad_request(f"invalid audio file: {err.decode()[:200]}")
    try:
        return float(out.decode().strip())
    except ValueError:
        raise bad_request("cannot probe audio duration")


async def to_wav_16k_mono(src: Path, dst: Path) -> None:
    """任意格式 → 16kHz mono 16bit WAV（送多模态模型的标准输入）。"""
    code, _, err = await _run(
        "ffmpeg", "-y", "-i", str(src),
        "-ar", "16000", "-ac", "1", "-sample_fmt", "s16",
        str(dst),
    )
    if code != 0:
        raise bad_request(f"audio convert failed: {err.decode()[:200]}")


def write_pcm_as_wav(pcm_int16: bytes, sample_rate: int, dst: Path) -> float:
    """Int16 PCM mono → WAV 落盘，返回时长（秒）。"""
    with wave.open(str(dst), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_int16)
    return len(pcm_int16) / 2 / sample_rate


class SpeechService:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._storage = settings.storage_path

    def path_of(self, filename: str) -> Path:
        return self._storage / filename

    async def save_upload(self, audio: UploadFile, name_prefix: str) -> dict:
        """校验并保存上传音频，产出送模型的 wav 版本。

        返回 {raw_path, raw_name, wav_path, audio_b64, duration_sec}。
        校验（api.md）：白名单 webm/ogg/mp4/wav → 400；≤10MB → 413；≤60s → 400。
        """
        filename = audio.filename or ""
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext not in self._settings.audio_ext_whitelist:
            raise bad_request(
                f"audio format not allowed: {ext or '(none)'}, "
                f"expect {'/'.join(self._settings.audio_ext_whitelist)}"
            )

        content = await audio.read()
        if len(content) > self._settings.max_audio_bytes:
            raise payload_too_large("audio exceeds 10MB")
        if not content:
            raise bad_request("audio is empty")

        raw_name = f"{name_prefix}_raw.{ext}"
        raw_path = self.path_of(raw_name)
        raw_path.write_bytes(content)

        duration_sec = await probe_duration(raw_path)
        if duration_sec > self._settings.max_audio_seconds:
            raw_path.unlink(missing_ok=True)
            raise bad_request("audio exceeds 60s")

        # 已是 wav 也统一走 ffmpeg 规整为 16kHz mono s16（模型标准输入）
        wav_path = self.path_of(f"{name_prefix}_16k.wav")
        await to_wav_16k_mono(raw_path, wav_path)
        audio_b64 = base64.b64encode(wav_path.read_bytes()).decode("ascii")

        return {
            "raw_path": raw_path,
            "raw_name": raw_name,
            "wav_path": wav_path,
            "audio_b64": audio_b64,
            "duration_sec": duration_sec,
        }

    def save_tts_wav(self, pcm_int16: bytes, sample_rate: int, filename: str) -> float:
        """合并后的 TTS PCM 落盘为 wav，返回时长（秒）。"""
        return write_pcm_as_wav(pcm_int16, sample_rate, self.path_of(filename))
