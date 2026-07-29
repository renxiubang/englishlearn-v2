"""AI 生成对话跟读语料：调用本地 MLLM 按主题批量生成对话写入 stories 表。

每主题预置 5 个场景提示，逐场景生成 1 条（4-6 轮 A/B 对话，含中文对照），
JSON 结构校验 + 单场景最多重试 3 次；同名标题跳过，可重复执行。
用法：cd backend && uv run python seeds/gen_dialogues.py [--dry-run]
"""

import argparse
import asyncio
import json
import logging
from typing import Any

from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.gateway.mllm import MLLMGateway
from app.models.tables import Story

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("gen_dialogues")

MODULE_TYPE = "dialogueRead"
MAX_RETRIES = 3

# 每主题 5 个场景提示：数量确定、题材不重复
SCENARIOS: dict[str, list[str]] = {
    "日常对话": ["见面打招呼", "超市购物", "打电话约朋友", "谈论天气", "介绍家人"],
    "旅行出行": ["机场值机", "乘坐公交", "酒店入住", "买火车票", "海边度假计划"],
    "健康生活": ["早晨锻炼", "健康早餐", "看牙医", "按时睡觉", "操场上擦伤处理"],
}

SYSTEM_PROMPT = """\
You create short English dialogues for Chinese children (CEFR A1-A2 level).

Output ONLY a JSON object, no markdown fences, no extra text:
{"title": "中文短标题", "turns": [{"role": "A", "en": "...", "zh": "..."}, ...]}

Rules:
- 4 to 6 turns, roles strictly alternate A, B, A, B...
- "en": one short, simple, natural English sentence per turn
- "zh": natural Simplified Chinese translation of the sentence
- "title": a short Simplified Chinese title (2-8 characters) for the dialogue
"""


def parse_dialogue(raw: str) -> dict[str, Any] | None:
    """解析并校验模型输出，返回 {"title", "turns"} 或 None（供重试）。"""
    text = raw.strip()
    # 剥离可能的 markdown 围栏（```json ... ```）
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
    try:
        data = json.loads(text.strip())
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None

    title = data.get("title")
    turns = data.get("turns")
    if not isinstance(title, str) or not title.strip():
        return None
    if not isinstance(turns, list) or not 3 <= len(turns) <= 8:
        return None

    cleaned: list[dict[str, str]] = []
    for turn in turns:
        if not isinstance(turn, dict):
            return None
        role, en = turn.get("role"), turn.get("en")
        if role not in ("A", "B"):
            return None
        if not isinstance(en, str) or not en.strip():
            return None
        zh = turn.get("zh")
        cleaned.append({
            "role": role,
            "en": en.strip(),
            "zh": zh.strip() if isinstance(zh, str) else "",
        })
    return {"title": title.strip()[:64], "turns": cleaned}


async def generate_one(
    gateway: MLLMGateway, theme: str, scenario: str, existing_titles: set[str]
) -> dict[str, Any] | None:
    """单场景生成（最多重试 MAX_RETRIES 次），失败返回 None。"""
    user_prompt = (
        f"Theme: {theme}\nScenario: {scenario}\n"
        f"Existing titles (do NOT reuse): {', '.join(sorted(existing_titles)) or 'none'}\n"
        "Generate one dialogue now."
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            raw = await gateway._complete(messages, max_tokens=768)
        except Exception as e:  # noqa: BLE001 — 网络/模型错误按一次失败重试
            logger.warning("[%s/%s] 第 %d 次调用异常: %s", theme, scenario, attempt, e)
            continue
        parsed = parse_dialogue(raw)
        if parsed and parsed["title"] not in existing_titles:
            return parsed
        logger.warning(
            "[%s/%s] 第 %d 次输出无效%s，重试",
            theme, scenario, attempt,
            "（标题重复）" if parsed else "（结构校验失败）",
        )
    logger.warning("[%s/%s] 重试 %d 次仍失败，跳过", theme, scenario, MAX_RETRIES)
    return None


async def main() -> None:
    parser = argparse.ArgumentParser(description="AI 生成对话跟读语料")
    parser.add_argument("--dry-run", action="store_true", help="只打印生成结果，不写库")
    args = parser.parse_args()

    gateway = MLLMGateway(get_settings())
    try:
        if not await gateway.ping():
            raise SystemExit("模型服务不可达，请先启动本地 MLLM（见 .env mllm_base_url）")

        async with SessionLocal() as session:
            existing_titles = set(
                (await session.scalars(
                    select(Story.title).where(Story.module_type == MODULE_TYPE)
                )).all()
            )
            next_order = (
                await session.scalar(
                    select(func.max(Story.sort_order)).where(Story.module_type == MODULE_TYPE)
                ) or 0
            ) + 1

            created = 0
            for theme, scenarios in SCENARIOS.items():
                for scenario in scenarios:
                    dialogue = await generate_one(gateway, theme, scenario, existing_titles)
                    if dialogue is None:
                        continue
                    existing_titles.add(dialogue["title"])
                    logger.info(
                        "[%s/%s] %s（%d 轮）%s",
                        theme, scenario, dialogue["title"], len(dialogue["turns"]),
                        " [dry-run]" if args.dry_run else "",
                    )
                    if args.dry_run:
                        print(json.dumps(dialogue, ensure_ascii=False, indent=2))
                        continue
                    session.add(Story(
                        module_type=MODULE_TYPE,
                        title=dialogue["title"],
                        seed=None,
                        cat=theme,
                        content={"turns": dialogue["turns"]},
                        sort_order=next_order,
                        enabled=True,
                    ))
                    next_order += 1
                    created += 1

            if not args.dry_run:
                await session.commit()
                logger.info("完成：新写入 %d 条对话", created)
    finally:
        await gateway.aclose()


if __name__ == "__main__":
    asyncio.run(main())
