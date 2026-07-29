"""管理后台模块：数字人 / 提示词 / 分类 / 内容（stories）维护。

所有路由挂 /api/admin 前缀，除 login 外均需 Bearer token（require_admin）。
"""

import logging

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import bad_request, conflict, not_found, ok
from app.gateway.prompts import refresh_prompts_cache
from app.models.tables import Category, Contact, Message, Prompt, Story
from app.modules.admin.auth import issue_token, require_admin, unauthorized

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["admin"])

# 四个内容模块（与 api.md 接口 13 type 枚举一致）
MODULE_TYPES = {"picStory", "storyRead", "dialogueRead", "listenStory"}


def _check_module_type(module_type: str) -> str:
    if module_type not in MODULE_TYPES:
        raise bad_request(f"invalid module_type: {module_type}")
    return module_type


# ---------- 登录 ----------

class LoginBody(BaseModel):
    password: str


@router.post("/login")
async def login(body: LoginBody):
    settings = get_settings()
    if not settings.admin_password or body.password != settings.admin_password:
        raise unauthorized("wrong password")
    return ok({"token": issue_token(), "expiresIn": settings.admin_token_ttl})


# ---------- 数字人（contacts 全字段维护） ----------

class ContactBody(BaseModel):
    type: str = Field(pattern="^(human|ai)$")
    name: str = Field(min_length=1, max_length=64)
    tag: str | None = None
    avatar: str | None = None
    emoji: str | None = None
    avatar_bg: str | None = None
    sub: str = ""
    persona_prompt: str = ""
    sort_order: int = 0


def _contact_to_dict(c: Contact) -> dict:
    return {
        "id": c.id, "type": c.type, "name": c.name, "tag": c.tag,
        "avatar": c.avatar, "emoji": c.emoji, "avatarBg": c.avatar_bg,
        "sub": c.sub, "personaPrompt": c.persona_prompt,
        "sortOrder": c.sort_order,
    }


@router.get("/contacts", dependencies=[Depends(require_admin)])
async def list_contacts(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(
        select(Contact).order_by(Contact.sort_order)
    )).scalars().all()
    return ok([_contact_to_dict(c) for c in rows])


class ContactCreateBody(ContactBody):
    id: str = Field(min_length=1, max_length=32, pattern="^[a-zA-Z][a-zA-Z0-9_-]*$")


@router.post("/contacts", dependencies=[Depends(require_admin)])
async def create_contact(body: ContactCreateBody, db: AsyncSession = Depends(get_db)):
    if await db.get(Contact, body.id):
        raise conflict(f"contact already exists: {body.id}")
    c = Contact(**body.model_dump())
    db.add(c)
    await db.flush()
    return ok(_contact_to_dict(c))


@router.put("/contacts/{contact_id}", dependencies=[Depends(require_admin)])
async def update_contact(
    contact_id: str, body: ContactBody, db: AsyncSession = Depends(get_db)
):
    c = await db.get(Contact, contact_id)
    if not c:
        raise not_found("contact not found")
    for k, v in body.model_dump().items():
        setattr(c, k, v)
    await db.flush()
    return ok(_contact_to_dict(c))


@router.delete("/contacts/{contact_id}", dependencies=[Depends(require_admin)])
async def delete_contact(contact_id: str, db: AsyncSession = Depends(get_db)):
    c = await db.get(Contact, contact_id)
    if not c:
        raise not_found("contact not found")
    # 已有聊天记录的联系人禁止删除（外键约束 + 学习数据保护）
    msg_count = await db.scalar(
        select(func.count()).select_from(Message).where(
            Message.contact_id == contact_id
        )
    )
    if msg_count:
        raise conflict(f"contact has {msg_count} messages, delete forbidden")
    await db.delete(c)
    return ok({"removed": True})


# ---------- 提示词 ----------

class PromptBody(BaseModel):
    content: str = Field(min_length=1)
    remark: str | None = None


@router.get("/prompts", dependencies=[Depends(require_admin)])
async def list_prompts(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(Prompt).order_by(Prompt.key))).scalars().all()
    return ok([
        {
            "key": p.key, "content": p.content, "remark": p.remark,
            "updatedAt": int(p.updated_at.timestamp() * 1000) if p.updated_at else None,
        }
        for p in rows
    ])


@router.put("/prompts/{key}", dependencies=[Depends(require_admin)])
async def update_prompt(
    key: str, body: PromptBody, db: AsyncSession = Depends(get_db)
):
    p = await db.get(Prompt, key)
    if not p:
        raise not_found("prompt key not found")
    p.content = body.content
    if body.remark is not None:
        p.remark = body.remark
    await db.commit()
    # 提交后立即重载缓存，下一次模型调用即用新提示词
    await refresh_prompts_cache(db)
    logger.info(f"admin: prompt updated & cache refreshed, key={key}")
    return ok({"key": p.key, "content": p.content, "remark": p.remark})


# ---------- 分类 ----------

class CategoryBody(BaseModel):
    module_type: str
    name: str = Field(min_length=1, max_length=32)
    sort_order: int = 0


def _category_to_dict(c: Category) -> dict:
    return {
        "id": c.id, "moduleType": c.module_type,
        "name": c.name, "sortOrder": c.sort_order,
    }


@router.get("/categories", dependencies=[Depends(require_admin)])
async def list_categories(
    type: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Category).order_by(Category.module_type, Category.sort_order)
    if type:
        stmt = stmt.where(Category.module_type == _check_module_type(type))
    rows = (await db.execute(stmt)).scalars().all()
    return ok([_category_to_dict(c) for c in rows])


@router.post("/categories", dependencies=[Depends(require_admin)])
async def create_category(body: CategoryBody, db: AsyncSession = Depends(get_db)):
    _check_module_type(body.module_type)
    dup = await db.scalar(select(Category).where(
        Category.module_type == body.module_type, Category.name == body.name
    ))
    if dup:
        raise conflict("category name already exists in this module")
    c = Category(**body.model_dump())
    db.add(c)
    await db.flush()
    return ok(_category_to_dict(c))


@router.put("/categories/{category_id}", dependencies=[Depends(require_admin)])
async def update_category(
    category_id: int, body: CategoryBody, db: AsyncSession = Depends(get_db)
):
    c = await db.get(Category, category_id)
    if not c:
        raise not_found("category not found")
    _check_module_type(body.module_type)
    dup = await db.scalar(select(Category).where(
        Category.module_type == body.module_type,
        Category.name == body.name,
        Category.id != category_id,
    ))
    if dup:
        raise conflict("category name already exists in this module")
    # 改名时同步更新引用该分类的 stories.cat，避免出现悬空分类
    if c.name != body.name or c.module_type != body.module_type:
        refs = (await db.execute(select(Story).where(
            Story.module_type == c.module_type, Story.cat == c.name
        ))).scalars().all()
        for s in refs:
            s.cat = body.name
    for k, v in body.model_dump().items():
        setattr(c, k, v)
    await db.flush()
    return ok(_category_to_dict(c))


@router.delete("/categories/{category_id}", dependencies=[Depends(require_admin)])
async def delete_category(category_id: int, db: AsyncSession = Depends(get_db)):
    c = await db.get(Category, category_id)
    if not c:
        raise not_found("category not found")
    ref_count = await db.scalar(
        select(func.count()).select_from(Story).where(
            Story.module_type == c.module_type, Story.cat == c.name
        )
    )
    if ref_count:
        raise conflict(f"category referenced by {ref_count} stories, delete forbidden")
    await db.delete(c)
    return ok({"removed": True})


# ---------- 内容（stories） ----------

class StoryBody(BaseModel):
    module_type: str
    title: str = Field(min_length=1, max_length=64)
    seed: str | None = Field(default=None, max_length=64)
    cat: str = ""
    content: dict = Field(default_factory=dict)
    sort_order: int = 0
    enabled: bool = True


def _story_to_dict(s: Story) -> dict:
    return {
        "id": s.id, "moduleType": s.module_type, "title": s.title,
        "seed": s.seed, "cat": s.cat, "content": s.content,
        "sortOrder": s.sort_order, "enabled": s.enabled,
    }


def _validate_story_content(module_type: str, seed: str | None, content: dict) -> None:
    """content JSON 结构校验（见 tables.Story 文档字符串约定）。"""
    if module_type == "dialogueRead":
        turns = content.get("turns")
        if not isinstance(turns, list) or not turns:
            raise bad_request("dialogueRead content requires non-empty turns[]")
        for t in turns:
            if not isinstance(t, dict) or not t.get("role") or not t.get("en"):
                raise bad_request("each turn requires role and en")
    else:
        sentences = content.get("sentences")
        if not isinstance(sentences, list) or not sentences:
            raise bad_request(f"{module_type} content requires non-empty sentences[]")
        if not all(isinstance(x, str) and x.strip() for x in sentences):
            raise bad_request("sentences must be non-empty strings")
    if module_type == "picStory" and not (seed and seed.strip()):
        raise bad_request("picStory requires seed (image seed & progress key)")


async def _check_seed_dup(
    db: AsyncSession, module_type: str, seed: str | None, exclude_id: int | None
) -> None:
    if not seed:
        return
    stmt = select(Story).where(
        Story.module_type == module_type, Story.seed == seed
    )
    if exclude_id is not None:
        stmt = stmt.where(Story.id != exclude_id)
    if await db.scalar(stmt):
        raise conflict(f"seed already exists in {module_type}: {seed}")


@router.get("/stories", dependencies=[Depends(require_admin)])
async def list_stories(
    type: str = Query(...),
    cat: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    _check_module_type(type)
    cond = [Story.module_type == type]
    if cat:
        cond.append(Story.cat == cat)
    total = await db.scalar(select(func.count()).select_from(Story).where(*cond))
    rows = (await db.execute(
        select(Story).where(*cond)
        .order_by(Story.sort_order, Story.id)
        .offset((page - 1) * limit).limit(limit)
    )).scalars().all()
    return ok({
        "list": [_story_to_dict(s) for s in rows],
        "total": total, "page": page, "limit": limit,
    })


@router.post("/stories", dependencies=[Depends(require_admin)])
async def create_story(body: StoryBody, db: AsyncSession = Depends(get_db)):
    _check_module_type(body.module_type)
    _validate_story_content(body.module_type, body.seed, body.content)
    await _check_seed_dup(db, body.module_type, body.seed, None)
    s = Story(**body.model_dump())
    db.add(s)
    await db.flush()
    return ok(_story_to_dict(s))


@router.put("/stories/{story_id}", dependencies=[Depends(require_admin)])
async def update_story(
    story_id: int, body: StoryBody, db: AsyncSession = Depends(get_db)
):
    s = await db.get(Story, story_id)
    if not s:
        raise not_found("story not found")
    _check_module_type(body.module_type)
    _validate_story_content(body.module_type, body.seed, body.content)
    await _check_seed_dup(db, body.module_type, body.seed, story_id)
    for k, v in body.model_dump().items():
        setattr(s, k, v)
    await db.flush()
    return ok(_story_to_dict(s))


class StoryEnabledBody(BaseModel):
    enabled: bool


@router.patch("/stories/{story_id}/enabled", dependencies=[Depends(require_admin)])
async def toggle_story_enabled(
    story_id: int, body: StoryEnabledBody, db: AsyncSession = Depends(get_db)
):
    s = await db.get(Story, story_id)
    if not s:
        raise not_found("story not found")
    s.enabled = body.enabled
    await db.flush()
    return ok(_story_to_dict(s))


@router.delete("/stories/{story_id}", dependencies=[Depends(require_admin)])
async def delete_story(story_id: int, db: AsyncSession = Depends(get_db)):
    s = await db.get(Story, story_id)
    if not s:
        raise not_found("story not found")
    await db.delete(s)
    return ok({"removed": True})
