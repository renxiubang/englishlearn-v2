"""聊天数据访问：contacts / messages / audio_assets。"""

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tables import AudioAsset, Contact, Message


async def get_contact(db: AsyncSession, contact_id: str) -> Contact | None:
    return await db.get(Contact, contact_id)


async def list_contacts(db: AsyncSession) -> list[Contact]:
    result = await db.execute(
        select(Contact).order_by(Contact.sort_order, Contact.id)
    )
    return list(result.scalars())


async def page_messages(
    db: AsyncSession,
    user_id: str,
    contact_id: str,
    cursor: int | None,
    limit: int,
) -> tuple[list[Message], bool, int | None]:
    """游标分页（api.md 接口 4）：取比 cursor 更早的一页，页内 id 升序。"""
    stmt = (
        select(Message)
        .where(Message.user_id == user_id, Message.contact_id == contact_id)
    )
    if cursor is not None:
        stmt = stmt.where(Message.id < cursor)
    stmt = stmt.order_by(Message.id.desc()).limit(limit + 1)
    rows = list((await db.execute(stmt)).scalars())

    has_more = len(rows) > limit
    page = rows[:limit]
    page.reverse()  # 升序（时间正序）
    next_cursor = page[0].id if has_more and page else None
    return page, has_more, next_cursor


async def recent_context(
    db: AsyncSession, user_id: str, contact_id: str, limit: int = 20
) -> list[dict[str, str]]:
    """最近 N 条消息 → LLM 上下文（me=user / them=assistant，用英文内容）。"""
    stmt = (
        select(Message)
        .where(
            Message.user_id == user_id,
            Message.contact_id == contact_id,
            Message.en != "",
        )
        .order_by(Message.id.desc())
        .limit(limit)
    )
    rows = list((await db.execute(stmt)).scalars())
    rows.reverse()
    return [
        {
            "role": "user" if m.from_side == "me" else "assistant",
            "content": m.en,
        }
        for m in rows
    ]


async def insert_message(
    db: AsyncSession,
    *,
    user_id: str,
    contact_id: str,
    from_side: str,
    en: str = "",
    zh: str = "",
    raw: str = "",
    duration: str | None = None,
    score: int | None = None,
    text_only: bool = False,
) -> Message:
    msg = Message(
        user_id=user_id,
        contact_id=contact_id,
        from_side=from_side,
        en=en,
        zh=zh,
        raw=raw,
        duration=duration,
        score=score,
        text_only=text_only,
    )
    db.add(msg)
    await db.flush()  # 取自增 id
    return msg


async def insert_audio_asset(
    db: AsyncSession,
    *,
    kind: str,
    path: str,
    message_id: int | None = None,
    duration_ms: int = 0,
) -> AudioAsset:
    asset = AudioAsset(
        kind=kind, path=path, message_id=message_id, duration_ms=duration_ms
    )
    db.add(asset)
    await db.flush()
    return asset


async def delete_chat_history(
    db: AsyncSession, user_id: str, contact_id: str
) -> tuple[int, list[str]]:
    """清空会话消息与关联音频记录（api.md 接口 18）。

    返回 (删除消息数, 待删物理文件名列表)；audio_assets 无外键约束，
    需先按 message_id 查出 path 再删行，文件由调用方在事务提交后删除。
    """
    ids = list(
        (
            await db.execute(
                select(Message.id).where(
                    Message.user_id == user_id, Message.contact_id == contact_id
                )
            )
        ).scalars()
    )
    if not ids:
        return 0, []
    paths = list(
        (
            await db.execute(
                select(AudioAsset.path).where(AudioAsset.message_id.in_(ids))
            )
        ).scalars()
    )
    await db.execute(delete(AudioAsset).where(AudioAsset.message_id.in_(ids)))
    await db.execute(delete(Message).where(Message.id.in_(ids)))
    return len(ids), paths


def message_to_dict(m: Message) -> dict:
    """Message → api.md ChatMessage 形状（可选字段仅在有值时输出）。"""
    d: dict = {"id": m.id, "from": m.from_side, "en": m.en, "zh": m.zh}
    if m.raw:
        d["raw"] = m.raw
    if m.duration is not None:
        d["duration"] = m.duration
    if m.score is not None:
        d["score"] = m.score
    if m.text_only:
        d["textOnly"] = True
    return d
