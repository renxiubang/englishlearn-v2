"""管理后台模块测试：鉴权 / 提示词 / 分类 / 内容 CRUD / 学生端只读契约。

sqlite 内存库 + 依赖覆盖，独立测试应用（不触发 main.py lifespan）。
"""

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.db import Base, get_db
from app.core.errors import AppError, app_error_handler
from app.gateway import prompts as prompts_module
from app.gateway.prompts import invalidate_prompts_cache, load_yaml_prompts
from app.models.tables import Contact, Message, Prompt
from app.modules.admin.auth import issue_token, verify_token
from app.modules.admin.router import router as admin_router
from app.modules.content.router import router as content_router


@pytest_asyncio.fixture
async def client():
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)

    app = FastAPI()
    app.add_exception_handler(AppError, app_error_handler)
    app.include_router(admin_router)
    app.include_router(content_router)

    async def override_db():
        async with maker() as session:
            yield session
            await session.commit()

    app.dependency_overrides[get_db] = override_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        ac._maker = maker  # 供个别用例直接造数
        yield ac
    invalidate_prompts_cache()  # 防止 DB 缓存污染其他测试
    await engine.dispose()


def _auth() -> dict:
    return {"Authorization": f"Bearer {issue_token()}"}


# ---------- 鉴权 ----------

def test_token_roundtrip():
    assert verify_token(issue_token())
    assert not verify_token("garbage")
    assert not verify_token("123.deadbeef")


async def test_login_wrong_password(client):
    resp = await client.post("/api/admin/login", json={"password": "wrong"})
    assert resp.status_code == 401


async def test_login_and_access(client):
    resp = await client.post("/api/admin/login", json={"password": "admin123"})
    assert resp.status_code == 200
    token = resp.json()["data"]["token"]

    # 无 token → 401；有 token → 200
    assert (await client.get("/api/admin/contacts")).status_code == 401
    resp = await client.get(
        "/api/admin/contacts", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200


# ---------- 数字人 ----------

async def test_contact_crud_and_delete_guard(client):
    body = {"id": "buddy", "type": "ai", "name": "Buddy", "emoji": "🤖",
            "persona_prompt": "You are Buddy.", "sort_order": 9}
    resp = await client.post("/api/admin/contacts", json=body, headers=_auth())
    assert resp.status_code == 200
    assert resp.json()["data"]["personaPrompt"] == "You are Buddy."

    # 重复 id → 409
    resp = await client.post("/api/admin/contacts", json=body, headers=_auth())
    assert resp.status_code == 409

    # 更新
    upd = {"type": "ai", "name": "Buddy2", "persona_prompt": "v2"}
    resp = await client.put("/api/admin/contacts/buddy", json=upd, headers=_auth())
    assert resp.json()["data"]["name"] == "Buddy2"

    # 有消息记录 → 删除 409
    async with client._maker() as s:
        s.add(Message(id=1, user_id="amy", contact_id="buddy",
                      from_side="them", en="hi"))
        await s.commit()
    resp = await client.delete("/api/admin/contacts/buddy", headers=_auth())
    assert resp.status_code == 409


# ---------- 提示词 ----------

async def test_prompt_update_refreshes_cache(client):
    async with client._maker() as s:
        for key, content in load_yaml_prompts().items():
            s.add(Prompt(key=key, content=content))
        await s.commit()

    resp = await client.get("/api/admin/prompts", headers=_auth())
    keys = {p["key"] for p in resp.json()["data"]}
    assert set(prompts_module.REQUIRED_KEYS) <= keys

    resp = await client.put(
        "/api/admin/prompts/chat_reply",
        json={"content": "NEW PROMPT CONTENT for testing."},
        headers=_auth(),
    )
    assert resp.status_code == 200
    # 保存后缓存即时生效
    assert prompts_module.get_prompt("chat_reply") == "NEW PROMPT CONTENT for testing."

    # 不存在的 key → 404
    resp = await client.put(
        "/api/admin/prompts/no_such", json={"content": "x"}, headers=_auth()
    )
    assert resp.status_code == 404


# ---------- 分类 ----------

async def test_category_crud_and_ref_guard(client):
    body = {"module_type": "storyRead", "name": "动物自然", "sort_order": 1}
    resp = await client.post("/api/admin/categories", json=body, headers=_auth())
    assert resp.status_code == 200
    cat_id = resp.json()["data"]["id"]

    # 同模块重名 → 409
    assert (await client.post(
        "/api/admin/categories", json=body, headers=_auth()
    )).status_code == 409

    # 非法模块 → 400
    bad = {"module_type": "unknown", "name": "x"}
    assert (await client.post(
        "/api/admin/categories", json=bad, headers=_auth()
    )).status_code == 400

    # 被 stories 引用 → 删除 409
    story = {"module_type": "storyRead", "title": "小猫找妈妈", "cat": "动物自然",
             "content": {"sentences": ["The cat is cute."]}}
    resp = await client.post("/api/admin/stories", json=story, headers=_auth())
    assert resp.status_code == 200
    assert (await client.delete(
        f"/api/admin/categories/{cat_id}", headers=_auth()
    )).status_code == 409


# ---------- 内容 stories ----------

async def test_story_crud_and_content_validation(client):
    # picStory 缺 seed → 400
    bad = {"module_type": "picStory", "title": "无种子", "cat": "家庭生活",
           "content": {"sentences": ["A sentence."]}}
    assert (await client.post(
        "/api/admin/stories", json=bad, headers=_auth()
    )).status_code == 400

    # dialogueRead 缺 turns → 400
    bad = {"module_type": "dialogueRead", "title": "无对话", "cat": "日常对话",
           "content": {"sentences": ["x"]}}
    assert (await client.post(
        "/api/admin/stories", json=bad, headers=_auth()
    )).status_code == 400

    # 正常创建 + seed 重复 → 409
    story = {"module_type": "picStory", "title": "公园野餐", "seed": "picnic",
             "cat": "家庭生活", "content": {"sentences": ["s1", "s2"]}}
    resp = await client.post("/api/admin/stories", json=story, headers=_auth())
    assert resp.status_code == 200
    sid = resp.json()["data"]["id"]
    story2 = dict(story, title="另一个野餐")
    assert (await client.post(
        "/api/admin/stories", json=story2, headers=_auth()
    )).status_code == 409

    # 上下架
    resp = await client.patch(
        f"/api/admin/stories/{sid}/enabled", json={"enabled": False},
        headers=_auth(),
    )
    assert resp.json()["data"]["enabled"] is False

    # 分页列表
    resp = await client.get(
        "/api/admin/stories?type=picStory&page=1&limit=10", headers=_auth()
    )
    data = resp.json()["data"]
    assert data["total"] == 1 and len(data["list"]) == 1

    # 删除
    assert (await client.delete(
        f"/api/admin/stories/{sid}", headers=_auth()
    )).status_code == 200


# ---------- 学生端只读契约（api.md 接口 12/13） ----------

async def test_public_pic_stories_contract(client):
    story = {"module_type": "picStory", "title": "公园野餐", "seed": "picnic",
             "cat": "家庭生活", "content": {"sentences": ["s1", "s2"]}}
    await client.post("/api/admin/stories", json=story, headers=_auth())
    hidden = dict(story, title="下架故事", seed="hidden", enabled=False)
    await client.post("/api/admin/stories", json=hidden, headers=_auth())

    resp = await client.get("/api/pic-stories")
    assert resp.status_code == 200
    data = resp.json()["data"]
    # 仅返回上架内容，结构与 api.md 一致
    assert data == [{"title": "公园野餐", "seed": "picnic",
                     "cat": "家庭生活", "sentences": ["s1", "s2"]}]


async def test_public_categories_all_first(client):
    await client.post("/api/admin/categories",
                      json={"module_type": "picStory", "name": "动物自然",
                            "sort_order": 1}, headers=_auth())
    resp = await client.get("/api/categories?type=picStory")
    assert resp.json()["data"] == ["全部", "动物自然"]

    assert (await client.get("/api/categories?type=bad")).status_code == 400
