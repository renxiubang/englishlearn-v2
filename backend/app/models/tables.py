"""阶段一最小表集：users / contacts / messages / audio_assets。

字段与 api.md 契约对齐（ChatMessage / Contact / UserProfile）。
"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    avatar: Mapped[str] = mapped_column(String(512), default="")
    level: Mapped[int] = mapped_column(Integer, default=1)
    level_title: Mapped[str] = mapped_column(String(64), default="")
    total_hours: Mapped[int] = mapped_column(Integer, default=0)


class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    type: Mapped[str] = mapped_column(Enum("human", "ai", name="contact_type"))
    name: Mapped[str] = mapped_column(String(64))
    tag: Mapped[str | None] = mapped_column(String(32), nullable=True)
    avatar: Mapped[str | None] = mapped_column(String(512), nullable=True)
    emoji: Mapped[str | None] = mapped_column(String(16), nullable=True)
    avatar_bg: Mapped[str | None] = mapped_column(String(16), nullable=True)
    sub: Mapped[str] = mapped_column(String(128), default="")
    # 人设提示词（DB 配置，与 prompts.yaml 任务提示词组合使用）
    persona_prompt: Mapped[str] = mapped_column(Text, default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(32), index=True)
    contact_id: Mapped[str] = mapped_column(
        ForeignKey("contacts.id"), index=True
    )
    from_side: Mapped[str] = mapped_column(Enum("them", "me", name="msg_from"))
    en: Mapped[str] = mapped_column(Text, default="")
    zh: Mapped[str] = mapped_column(Text, default="")
    # 语音时长（如 "0:04"；NULL = 纯文本消息）
    duration: Mapped[str | None] = mapped_column(String(8), nullable=True)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    text_only: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )


class AudioAsset(Base):
    __tablename__ = "audio_assets"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    message_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, index=True
    )
    # user_raw = 用户原声；tts = 合成语音；assist = 辅助卡片合成语音
    kind: Mapped[str] = mapped_column(
        Enum("user_raw", "tts", "assist", name="audio_kind")
    )
    # 相对 storage_dir 的文件名，对外 URL = /audio/{path}
    path: Mapped[str] = mapped_column(String(255))
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
