"""Kokoro TTS 网关：调用独立常驻服务（:8880），返回 Int16 PCM。"""

import base64
import logging
import re

import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)

DEFAULT_SAMPLE_RATE = 24000

# emoji 及相关控制符：国旗/表情/图形符号（含扩展）、杂项符号与装饰符、
# 变体选择符、零宽连接符、键帽组合符
EMOJI_RE = re.compile(
    "["
    "\U0001F1E6-\U0001FAFF"
    "\u2600-\u27BF"
    "\u2B00-\u2BFF"
    "\uFE0E\uFE0F\u200D\u20E3"
    "]+"
)


def strip_emoji(text: str) -> str:
    """去除 emoji 后归并多余空白，避免 TTS 读出表情符号。"""
    cleaned = EMOJI_RE.sub("", text)
    return re.sub(r"\s{2,}", " ", cleaned).strip()


class TTSGateway:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None):
        self._settings = settings
        self._client = client or httpx.AsyncClient(
            base_url=settings.tts_base_url,
            timeout=settings.tts_timeout,
        )
        self.sample_rate = DEFAULT_SAMPLE_RATE

    async def aclose(self):
        await self._client.aclose()

    async def ping(self) -> bool:
        """探测 /health 并同步 sample_rate。"""
        try:
            resp = await self._client.get("/health")
            resp.raise_for_status()
            self.sample_rate = resp.json().get("sample_rate", DEFAULT_SAMPLE_RATE)
            logger.info(f"TTS server ok (sample_rate={self.sample_rate})")
            return True
        except httpx.HTTPError as e:
            logger.warning(f"TTS server not reachable: {e}")
            return False

    async def synthesize(self, text: str) -> bytes:
        """文本→Int16 PCM mono 字节流（服务端直出 Int16，无需转换）。

        合成前过滤 emoji；过滤后为空（纯表情分片）直接返回空字节，不请求服务。
        """
        text = strip_emoji(text)
        if not text:
            return b""
        resp = await self._client.post(
            "/v1/audio/speech",
            json={
                "text": text,
                "voice": self._settings.tts_voice,
                "speed": self._settings.tts_speed,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        self.sample_rate = data.get("sample_rate", self.sample_rate)
        return base64.b64decode(data["audio_base64"])
