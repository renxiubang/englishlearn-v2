"""应用级单例依赖：模型网关、音频服务、会话锁。

在 main.py lifespan 中初始化并挂到 app.state，路由经此模块的
依赖函数获取，便于测试替换。
"""

from fastapi import Request

from app.gateway.mllm import MLLMGateway
from app.gateway.tts import TTSGateway
from app.modules.speech.service import SpeechService


class SessionGuard:
    """进程内会话互斥（替代 Redis 分布式锁，单 worker 前提）。

    同一会话（user:contact）同时只允许一条 5b 流，冲突返回 409。
    """

    def __init__(self):
        self._active: set[str] = set()

    def try_acquire(self, key: str) -> bool:
        if key in self._active:
            return False
        self._active.add(key)
        return True

    def release(self, key: str) -> None:
        self._active.discard(key)


def get_mllm(request: Request) -> MLLMGateway:
    return request.app.state.mllm


def get_tts(request: Request) -> TTSGateway:
    return request.app.state.tts


def get_speech(request: Request) -> SpeechService:
    return request.app.state.speech


def get_session_guard(request: Request) -> SessionGuard:
    return request.app.state.session_guard


# 单用户免登阶段：所有请求注入默认用户（api.md 认证约定）
DEFAULT_USER_ID = "amy"
