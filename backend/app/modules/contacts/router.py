"""联系人模块（api.md 接口 3）。"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.errors import ok
from app.modules.chat import repository as repo

router = APIRouter(prefix="/api", tags=["contacts"])


def _contact_to_dict(c) -> dict:
    d: dict = {"id": c.id, "type": c.type, "name": c.name, "sub": c.sub}
    if c.tag:
        d["tag"] = c.tag
    if c.avatar:
        d["avatar"] = c.avatar
    if c.emoji:
        d["emoji"] = c.emoji
    if c.avatar_bg:
        d["avatarBg"] = c.avatar_bg
    return d


@router.get("/contacts")
async def list_contacts(db: AsyncSession = Depends(get_db)):
    contacts = await repo.list_contacts(db)
    return ok([_contact_to_dict(c) for c in contacts])
