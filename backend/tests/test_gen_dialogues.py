"""gen_dialogues.parse_dialogue 纯函数测试（不调模型）。"""

import json

from seeds.gen_dialogues import parse_dialogue

VALID = {
    "title": "超市购物",
    "turns": [
        {"role": "A", "en": "Can I help you?", "zh": "需要帮忙吗？"},
        {"role": "B", "en": "Yes, where are the apples?", "zh": "是的，苹果在哪里？"},
        {"role": "A", "en": "They are over there.", "zh": "在那边。"},
        {"role": "B", "en": "Thank you!", "zh": "谢谢！"},
    ],
}


def test_valid_json():
    parsed = parse_dialogue(json.dumps(VALID, ensure_ascii=False))
    assert parsed is not None
    assert parsed["title"] == "超市购物"
    assert len(parsed["turns"]) == 4
    assert parsed["turns"][0] == {"role": "A", "en": "Can I help you?", "zh": "需要帮忙吗？"}


def test_markdown_fenced_json():
    raw = "```json\n" + json.dumps(VALID, ensure_ascii=False) + "\n```"
    parsed = parse_dialogue(raw)
    assert parsed is not None
    assert parsed["title"] == "超市购物"


def test_invalid_role_rejected():
    bad = json.loads(json.dumps(VALID))
    bad["turns"][1]["role"] = "C"
    assert parse_dialogue(json.dumps(bad, ensure_ascii=False)) is None


def test_turns_count_out_of_range():
    bad = json.loads(json.dumps(VALID))
    bad["turns"] = bad["turns"][:2]  # 少于 3 轮
    assert parse_dialogue(json.dumps(bad, ensure_ascii=False)) is None
    bad["turns"] = VALID["turns"] * 3  # 超过 8 轮
    assert parse_dialogue(json.dumps(bad, ensure_ascii=False)) is None


def test_not_json():
    assert parse_dialogue("Sorry, I cannot do that.") is None
    assert parse_dialogue("") is None
