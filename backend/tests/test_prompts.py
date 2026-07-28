"""prompts.yaml 加载单测。"""

import pytest

from app.gateway.prompts import REQUIRED_KEYS, get_prompt, load_prompts


def test_all_required_keys_present():
    prompts = load_prompts()
    for key in REQUIRED_KEYS:
        assert prompts[key], f"prompt {key} 为空"


def test_get_prompt_returns_stripped_text():
    text = get_prompt("chat_reply")
    assert text == text.strip()
    assert len(text) > 20


def test_get_prompt_unknown_key_raises():
    with pytest.raises(KeyError):
        get_prompt("no_such_prompt")
