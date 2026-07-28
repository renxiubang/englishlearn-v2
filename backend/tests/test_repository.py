"""repository 游标分页单测（sqlite 内存库）。"""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.db import Base
from app.models.tables import Contact, Message
from app.modules.chat import repository


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        session.add(Contact(id="lily", type="ai", name="Lily"))
        # 15 条消息，id 1..15（sqlite BIGINT pk 不自增，显式赋 id）
        for i in range(1, 16):
            session.add(Message(
                id=i, user_id="amy", contact_id="lily",
                from_side="me" if i % 2 else "them",
                en=f"msg {i}", zh=f"消息 {i}",
            ))
        await session.commit()
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_first_page_latest_ascending(db):
    page, has_more, next_cursor = await repository.page_messages(
        db, "amy", "lily", cursor=None, limit=10
    )
    assert [m.id for m in page] == list(range(6, 16))  # 页内升序
    assert has_more is True
    assert next_cursor == 6  # 本页最旧 id


@pytest.mark.asyncio
async def test_second_page_via_cursor(db):
    page, has_more, next_cursor = await repository.page_messages(
        db, "amy", "lily", cursor=6, limit=10
    )
    assert [m.id for m in page] == [1, 2, 3, 4, 5]
    assert has_more is False
    assert next_cursor is None


@pytest.mark.asyncio
async def test_exact_page_boundary(db):
    """恰好取完剩余数据时 hasMore=False。"""
    page, has_more, next_cursor = await repository.page_messages(
        db, "amy", "lily", cursor=None, limit=15
    )
    assert len(page) == 15
    assert has_more is False
    assert next_cursor is None


@pytest.mark.asyncio
async def test_empty_conversation(db):
    page, has_more, next_cursor = await repository.page_messages(
        db, "amy", "nobody", cursor=None, limit=10
    )
    assert page == []
    assert has_more is False
    assert next_cursor is None


@pytest.mark.asyncio
async def test_recent_context_role_mapping(db):
    ctx = await repository.recent_context(db, "amy", "lily", limit=4)
    assert len(ctx) == 4
    assert [c["content"] for c in ctx] == ["msg 12", "msg 13", "msg 14", "msg 15"]
    # 奇数 id = me → user；偶数 id = them → assistant
    assert ctx[0]["role"] == "assistant" and ctx[1]["role"] == "user"
