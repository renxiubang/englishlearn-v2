"""verify_semantic JSON 解析单测（mock 掉网络调用）。"""

import pytest

from app.core.config import Settings
from app.gateway.mllm import MLLMGateway


def make_gateway(transcription: str, raw_judgement: str) -> MLLMGateway:
    gw = MLLMGateway(Settings())

    async def fake_transcribe(audio_b64, lang):
        return transcription

    async def fake_complete(messages, max_tokens=512):
        return raw_judgement

    gw.transcribe = fake_transcribe  # type: ignore[method-assign]
    gw._complete = fake_complete  # type: ignore[method-assign]
    return gw


@pytest.mark.asyncio
async def test_consistent_json():
    gw = make_gateway("I like apples.", '{"consistent": true, "reason": ""}')
    ok, reason = await gw.verify_semantic("b64", "I like apples.")
    assert ok is True
    assert reason is None


@pytest.mark.asyncio
async def test_inconsistent_json_with_reason():
    gw = make_gateway(
        "I like bananas.",
        '{"consistent": false, "reason": "内容与目标句不符"}',
    )
    ok, reason = await gw.verify_semantic("b64", "I like apples.")
    assert ok is False
    assert reason == "内容与目标句不符"


@pytest.mark.asyncio
async def test_json_wrapped_in_prose():
    """模型输出夹带说明文字时用正则提取 JSON。"""
    gw = make_gateway(
        "I like apples.",
        'Here is my judgement:\n```json\n{"consistent": true}\n```',
    )
    ok, reason = await gw.verify_semantic("b64", "I like apples.")
    assert ok is True
    assert reason is None


@pytest.mark.asyncio
async def test_parse_failure_treated_as_inconsistent():
    gw = make_gateway("I like apples.", "cannot judge, sorry")
    ok, reason = await gw.verify_semantic("b64", "I like apples.")
    assert ok is False
    assert reason  # 有兜底中文原因


@pytest.mark.asyncio
async def test_empty_transcription_short_circuits():
    gw = make_gateway("", "should not be used")
    ok, reason = await gw.verify_semantic("b64", "I like apples.")
    assert ok is False
    assert "未能识别" in reason


@pytest.mark.asyncio
async def test_inconsistent_without_reason_gets_fallback():
    gw = make_gateway("something", '{"consistent": false}')
    ok, reason = await gw.verify_semantic("b64", "target")
    assert ok is False
    assert reason  # 缺 reason 时补兜底文案
