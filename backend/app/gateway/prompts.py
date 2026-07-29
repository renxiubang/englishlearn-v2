"""prompts.yaml 加载器：任务提示词（persona 在 DB contacts.persona_prompt）。"""

from functools import lru_cache
from pathlib import Path

import yaml

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


@lru_cache
def load_prompts() -> dict[str, str]:
    with open(PROMPTS_FILE, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    missing = [k for k in REQUIRED_KEYS if not data.get(k)]
    if missing:
        raise RuntimeError(f"prompts.yaml missing keys: {missing}")
    return {k: str(v).strip() for k, v in data.items()}


def get_prompt(key: str) -> str:
    prompts = load_prompts()
    if key not in prompts:
        raise KeyError(f"prompt key not found: {key}")
    return prompts[key]
