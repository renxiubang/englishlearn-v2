"""日志装配：控制台 + 轮转文件双输出，级别与轮转策略由 .env 配置。

- LOG_ROTATION=time：按日期轮转（每天午夜切分，保留 LOG_BACKUP_COUNT 天）
- LOG_ROTATION=size：按大小轮转（单文件 LOG_MAX_BYTES，保留 LOG_BACKUP_COUNT 份）
uvicorn 的 access/error 日志同样写入文件，避免终端关闭后丢失。
"""

import logging
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler

from app.core.config import Settings

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


def _build_file_handler(settings: Settings) -> logging.Handler:
    log_file = settings.log_path / "api.log"
    if settings.log_rotation == "size":
        handler: logging.Handler = RotatingFileHandler(
            log_file,
            maxBytes=settings.log_max_bytes,
            backupCount=settings.log_backup_count,
            encoding="utf-8",
        )
    else:  # time：每天午夜切分
        handler = TimedRotatingFileHandler(
            log_file,
            when="midnight",
            backupCount=settings.log_backup_count,
            encoding="utf-8",
        )
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    return handler


def setup_logging(settings: Settings) -> None:
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    file_handler = _build_file_handler(settings)

    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter(LOG_FORMAT))

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers = [console, file_handler]

    # 三方库 DEBUG 日志噪声大（连接帧、SQL 驱动细节），固定压到 INFO
    for noisy in ("httpcore", "httpx", "asyncmy", "aiomysql"):
        logging.getLogger(noisy).setLevel(max(level, logging.INFO))

    # uvicorn 自带 handler 且不向 root 传播，单独挂文件输出；
    # uvicorn.error 会向 uvicorn 传播，不另挂以免重复写入
    for name in ("uvicorn", "uvicorn.access"):
        uv_logger = logging.getLogger(name)
        if file_handler not in uv_logger.handlers:
            uv_logger.addHandler(file_handler)
