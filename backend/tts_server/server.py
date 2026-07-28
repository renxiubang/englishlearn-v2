"""Kokoro TTS 独立常驻服务（第一阶段，端口 8880）。

移植自 ai-v2/src/tts_server.py，差异：
- 仅保留 MLX 后端（本机为 Apple Silicon，模型 mlx-community/Kokoro-82M-bf16）
- 返回 Int16 PCM（载荷减半，后端免转换直接分片下发）
- 错误用 HTTPException 规范返回（ai-v2 的元组写法在 FastAPI 下是 bug）

用法:
    python tts_server/server.py            # 默认端口 8880
    TTS_PORT=8880 python tts_server/server.py
"""

import base64
import logging
import os

import numpy as np
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("tts_server")


# ── 模型加载（进程启动时一次，常驻内存）─────────────────────

class KokoroMLX:
    def __init__(self):
        from mlx_audio.tts.generate import load_model

        self._model = load_model("mlx-community/Kokoro-82M-bf16")
        self.sample_rate = self._model.sample_rate
        # 预热：触发音素转换器等流水线初始化
        list(self._model.generate(text="Hello", voice="af_heart", speed=1.0))

    def generate(self, text: str, voice: str, speed: float) -> np.ndarray:
        results = list(self._model.generate(text=text, voice=voice, speed=speed))
        return np.concatenate([np.array(r.audio) for r in results])


logger.info("Loading Kokoro TTS model (this may take a few seconds)...")
backend = KokoroMLX()
logger.info(f"TTS model loaded (sample_rate={backend.sample_rate})")

# ── API ─────────────────────────────────────────────────────

app = FastAPI(title="Kokoro TTS Server")


class SpeechRequest(BaseModel):
    text: str = Field(..., min_length=1, description="要合成的文本")
    voice: str = Field(default="af_heart", description="语音名称")
    speed: float = Field(default=1.1, ge=0.5, le=2.0, description="语速倍率")


@app.get("/health")
def health():
    return {"status": "ok", "sample_rate": backend.sample_rate}


@app.post("/v1/audio/speech")
def speech(req: SpeechRequest):
    """文本合成语音，返回 base64 编码的 Int16 PCM mono。"""
    try:
        pcm = backend.generate(req.text, req.voice, req.speed)
        pcm_int16 = (pcm * 32767).clip(-32768, 32767).astype(np.int16)
        return {
            "audio_base64": base64.b64encode(pcm_int16.tobytes()).decode("ascii"),
            "sample_rate": backend.sample_rate,
        }
    except Exception as e:
        logger.error(f"Speech generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    port = int(os.environ.get("TTS_PORT", "8880"))
    logger.info(f"TTS server starting on port {port}")
    uvicorn.run(app, host="127.0.0.1", port=port)
