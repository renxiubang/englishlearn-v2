"""FastAPI 应用装配：CORS、统一异常、StaticFiles(/audio)、路由、生命周期。"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.core.deps import SessionGuard
from app.core.errors import AppError, app_error_handler, unhandled_error_handler
from app.core.logging import setup_logging
from app.gateway.mllm import MLLMGateway
from app.gateway.prompts import (
    load_prompts,
    refresh_prompts_cache,
    seed_prompts_if_empty,
)
from app.gateway.tts import TTSGateway
from app.modules.admin.router import router as admin_router
from app.modules.assist.router import router as assist_router
from app.modules.chat.router import router as chat_router
from app.modules.contacts.router import router as contacts_router
from app.modules.content.router import router as content_router
from app.modules.speech.service import SpeechService

settings = get_settings()
setup_logging(settings)
logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_prompts()  # 启动即校验 prompts.yaml 完整性（DB 缓存就绪前的兜底）
    # 提示词入库：表空则从 YAML 导种子，再加载进内存缓存（DB 不可用仅告警，回落 YAML）
    try:
        async with SessionLocal() as session:
            await seed_prompts_if_empty(session)
            await refresh_prompts_cache(session)
        logger.info("startup: prompts loaded from DB")
    except Exception as exc:
        logger.warning(f"startup: prompts DB load failed, fallback to yaml: {exc}")
    app.state.mllm = MLLMGateway(settings)
    app.state.tts = TTSGateway(settings)
    app.state.speech = SpeechService(settings)
    app.state.session_guard = SessionGuard()

    # 连通性探测（失败仅告警，不阻塞启动）
    mllm_ok = await app.state.mllm.ping()
    tts_ok = await app.state.tts.ping()
    logger.info(f"startup: mllm={'ok' if mllm_ok else 'DOWN'}, "
                f"tts={'ok' if tts_ok else 'DOWN'}")
    yield
    await app.state.mllm.aclose()
    await app.state.tts.aclose()


app = FastAPI(title="EnglishLearn Backend", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(Exception, unhandled_error_handler)

# 本地磁盘替代对象存储：/audio/{filename}
app.mount("/audio", StaticFiles(directory=settings.storage_path), name="audio")

app.include_router(contacts_router)
app.include_router(chat_router)
app.include_router(assist_router)
app.include_router(content_router)
app.include_router(admin_router)


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app", host="127.0.0.1", port=settings.api_port, reload=False
    )
