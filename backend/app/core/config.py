"""应用配置：pydantic-settings 从 .env / 环境变量加载。"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # backend/


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 多模态大模型（OpenAI 兼容）
    # provider 兼容开关：local=本地 Gemma；dashscope=百炼 Qwen-Omni（开发期临时替换）
    mllm_provider: str = "local"
    mllm_base_url: str = "http://127.0.0.1:8000/v1"
    mllm_model: str = "gemma-4-e4b-it-4bit"
    mllm_api_key: str = "omlx-local"
    mllm_timeout: int = 120

    # Kokoro TTS 独立服务
    tts_base_url: str = "http://127.0.0.1:8880"
    tts_voice: str = "af_heart"
    tts_speed: float = 1.1
    tts_timeout: int = 60

    # 数据库
    db_url: str = "mysql+asyncmy://app:app@127.0.0.1:3306/english_learn"

    # 存储与服务
    storage_dir: str = "./storage"
    api_port: int = 8080
    cors_origins: list[str] = ["http://localhost:5173"]

    # 上传约束（api.md 通用约定）
    max_audio_bytes: int = 10 * 1024 * 1024  # 10MB → 413
    max_audio_seconds: int = 60              # 60s → 400
    # 白名单：webm/ogg/mp4 + wav（第一阶段新增，见 api.md）
    audio_ext_whitelist: list[str] = ["webm", "ogg", "mp4", "wav"]

    # 会话上下文条数
    context_limit: int = 20

    @property
    def storage_path(self) -> Path:
        p = Path(self.storage_dir)
        if not p.is_absolute():
            p = BASE_DIR / p
        p.mkdir(parents=True, exist_ok=True)
        return p


@lru_cache
def get_settings() -> Settings:
    return Settings()
