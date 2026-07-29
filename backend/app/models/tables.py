"""数据表集：users / contacts / messages / audio_assets
+ 运营内容表 prompts / categories / stories（管理后台维护）。

字段与 api.md 契约对齐（ChatMessage / Contact / UserProfile / PicStory）。
"""

from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
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
    # 我方语音消息的原始逐字转录（"原译"，5b 阶段B 产出；其余消息为空）
    raw: Mapped[str] = mapped_column(Text, default="")
    # 语音时长（如 "0:04"；NULL = 纯文本消息）
    duration: Mapped[str | None] = mapped_column(String(8), nullable=True)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    text_only: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )


class Prompt(Base):
    """任务提示词（原 prompts.yaml 迁入 DB，管理后台可维护，保存即生效）。"""

    __tablename__ = "prompts"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    content: Mapped[str] = mapped_column(Text, default="")
    remark: Mapped[str] = mapped_column(String(255), default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class Category(Base):
    """内容分类（接口 13）；"全部"由接口层拼在首位，不入表。"""

    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("module_type", "name", name="uk_module_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # picStory / storyRead / dialogueRead / listenStory
    module_type: Mapped[str] = mapped_column(String(32), index=True)
    name: Mapped[str] = mapped_column(String(32))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class Story(Base):
    """统一运营内容表：四个模块共用，content JSON 承载模块差异化载荷。

    - storyRead / picStory / listenStory: {"sentences": [...]}（listenStory 预留 "audio"）
    - dialogueRead: {"turns": [{"role", "en", "zh"}, ...]}
    """

    __tablename__ = "stories"
    __table_args__ = (UniqueConstraint("module_type", "seed", name="uk_module_seed"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    module_type: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(String(64))
    # picStory 取图与进度主键；其他模块可空
    seed: Mapped[str | None] = mapped_column(String(64), nullable=True)
    cat: Mapped[str] = mapped_column(String(32), default="")
    content: Mapped[dict] = mapped_column(JSON, default=dict)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


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
