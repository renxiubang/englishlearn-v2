"""内容模块（学生端只读）：api.md 接口 12 / 13 + 通用 stories 读取。

数据来自管理后台维护的 stories / categories 表，仅返回 enabled 内容。
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.errors import bad_request, ok
from app.models.tables import Category, Story

# 与 admin 模块共用同一枚举（api.md 接口 13 type 参数）
MODULE_TYPES = {"picStory", "storyRead", "dialogueRead", "listenStory"}

router = APIRouter(prefix="/api", tags=["content"])


@router.get("/pic-stories")
async def list_pic_stories(db: AsyncSession = Depends(get_db)):
    """接口 12：看图故事列表（响应结构与 api.md 一致）。"""
    rows = (await db.execute(
        select(Story)
        .where(Story.module_type == "picStory", Story.enabled.is_(True))
        .order_by(Story.sort_order, Story.id)
    )).scalars().all()
    return ok([
        {
            "title": s.title,
            "seed": s.seed,
            "cat": s.cat,
            "sentences": (s.content or {}).get("sentences", []),
        }
        for s in rows
    ])


@router.get("/categories")
async def list_categories(
    type: str = Query(default="picStory"),
    db: AsyncSession = Depends(get_db),
):
    """接口 13：分类列表，"全部"固定拼在首位（不入表）。"""
    if type not in MODULE_TYPES:
        raise bad_request(f"invalid type: {type}")
    rows = (await db.execute(
        select(Category.name)
        .where(Category.module_type == type)
        .order_by(Category.sort_order, Category.id)
    )).scalars().all()
    return ok(["全部", *rows])


@router.get("/stories")
async def list_stories(
    type: str = Query(...),
    cat: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """通用内容读取（storyRead / dialogueRead / listenStory，预留给学生端）。"""
    if type not in MODULE_TYPES:
        raise bad_request(f"invalid type: {type}")
    cond = [Story.module_type == type, Story.enabled.is_(True)]
    if cat and cat != "全部":
        cond.append(Story.cat == cat)
    rows = (await db.execute(
        select(Story).where(*cond).order_by(Story.sort_order, Story.id)
    )).scalars().all()
    return ok([
        {
            "id": s.id,
            "title": s.title,
            "seed": s.seed,
            "cat": s.cat,
            "content": s.content or {},
        }
        for s in rows
    ])
