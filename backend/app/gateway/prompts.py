"""任务提示词加载器：DB prompts 表为准（persona 在 DB contacts.persona_prompt）。

- 启动时（main.py lifespan）若表为空，从 prompts.yaml 导入种子后加载进内存缓存；
- 管理后台更新提示词后调 refresh_prompts_cache() 即时生效（单 worker 前提）；
- get_prompt() 保持同步签名，调用方（mllm.py 等）零改动；
- 缓存未就绪时回落 YAML 文件（单测 / 离线兜底）。
"""

from pathlib import Path

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

PROMPTS_FILE = Path(__file__).resolve().parent.parent / "prompts.yaml"

REQUIRED_KEYS = [
    "chat_reply",
    "transcribe_en",
    "transcribe_zh",
    "transcribe_correct",
    "translate_en_to_zh",
    "translate_zh_to_en",
    "verify_semantic",
]

# 各 key 的用途备注（导种子时写入 prompts.remark，供管理后台展示）
KEY_REMARKS = {
    "chat_reply": "对话回复（5a/5b 阶段A），与数字人 persona 组合为 system prompt",
    "transcribe_en": "英文语音转录（级联阶段一）",
    "transcribe_zh": "中文语音转录（级联阶段一）",
    "transcribe_correct": "转录+语法修正（5b 阶段B，JSON 输出）",
    "translate_en_to_zh": "英译中（级联阶段二 / 接口 19）",
    "translate_zh_to_en": "中译英（辅助卡片链路）",
    "verify_semantic": "复读语义校验（接口 17，JSON 输出）",
}

# 进程内缓存（单 worker 前提，与 SessionGuard 同思路）
_cache: dict[str, str] | None = None


def _validate(data: dict[str, str], source: str) -> dict[str, str]:
    missing = [k for k in REQUIRED_KEYS if not data.get(k)]
    if missing:
        raise RuntimeError(f"prompts({source}) missing keys: {missing}")
    return {k: str(v).strip() for k, v in data.items()}


def load_yaml_prompts() -> dict[str, str]:
    """读 prompts.yaml（种子来源 / 缓存未就绪时的兜底）。"""
    with open(PROMPTS_FILE, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return _validate(data, "yaml")


async def seed_prompts_if_empty(db: AsyncSession) -> None:
    """表为空时从 prompts.yaml 导入种子（首次启动可用，幂等）。"""
    from app.models.tables import Prompt

    existing = await db.scalar(select(Prompt.key).limit(1))
    if existing is not None:
        return
    for key, content in load_yaml_prompts().items():
        db.add(Prompt(key=key, content=content, remark=KEY_REMARKS.get(key, "")))
    await db.commit()


async def refresh_prompts_cache(db: AsyncSession) -> dict[str, str]:
    """从 DB 全量重载缓存；管理后台保存后调用即时生效。"""
    from app.models.tables import Prompt

    global _cache
    rows = (await db.execute(select(Prompt))).scalars().all()
    _cache = _validate({r.key: r.content for r in rows}, "db")
    return _cache


def invalidate_prompts_cache() -> None:
    """清空缓存（下次 get_prompt 回落 YAML，测试用）。"""
    global _cache
    _cache = None


def load_prompts() -> dict[str, str]:
    """当前生效的提示词集合：优先 DB 缓存，未就绪回落 YAML。"""
    if _cache is not None:
        return _cache
    return load_yaml_prompts()


def get_prompt(key: str) -> str:
    prompts = load_prompts()
    if key not in prompts:
        raise KeyError(f"prompt key not found: {key}")
    return prompts[key]
