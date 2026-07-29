"""transcribe_correct JSON 解析 + provider 兼容开关单测（不真调模型）。"""

from app.core.config import Settings
from app.gateway.mllm import MLLMGateway, _audio_part, parse_transcribe_correct

# ── parse_transcribe_correct ─────────────────────────


def test_normal_json():
    raw, en = parse_transcribe_correct(
        '{"raw": "I go to school yesterday", "en": "I went to school yesterday."}'
    )
    assert raw == "I go to school yesterday"
    assert en == "I went to school yesterday."


def test_json_wrapped_in_prose():
    """模型输出夹带说明文字/代码块时用正则提取 JSON。"""
    raw, en = parse_transcribe_correct(
        'Here is the result:\n```json\n{"raw": "he like cat", "en": "He likes cats."}\n```'
    )
    assert raw == "he like cat"
    assert en == "He likes cats."


def test_parse_failure_degrades_to_plain_text():
    """解析失败降级：raw = en = 模型原文（strip 后）。"""
    raw, en = parse_transcribe_correct("  I went to school yesterday.  ")
    assert raw == en == "I went to school yesterday."


def test_empty_en_degrades():
    """JSON 合法但 en 为空同样走降级。"""
    text = '{"raw": "something", "en": ""}'
    raw, en = parse_transcribe_correct(text)
    assert raw == en == text


def test_missing_raw_falls_back_to_en():
    raw, en = parse_transcribe_correct('{"en": "He likes cats."}')
    assert raw == en == "He likes cats."


# ── provider 兼容开关（payload / audio_part 形态）────


def test_audio_part_local_plain_base64():
    part = _audio_part("abc123", "local")
    assert part["input_audio"]["data"] == "abc123"
    assert part["input_audio"]["format"] == "wav"


def test_audio_part_dashscope_data_uri_prefix():
    part = _audio_part("abc123", "dashscope")
    assert part["input_audio"]["data"] == "data:;base64,abc123"


def make_gateway(provider: str) -> MLLMGateway:
    return MLLMGateway(Settings(mllm_provider=provider))


def test_payload_local_has_chat_template_kwargs():
    gw = make_gateway("local")
    payload = gw._payload([{"role": "user", "content": "hi"}])
    assert payload["chat_template_kwargs"] == {"enable_thinking": False}
    assert "modalities" not in payload


def test_payload_dashscope_has_modalities_text():
    gw = make_gateway("dashscope")
    payload = gw._payload([{"role": "user", "content": "hi"}])
    assert payload["modalities"] == ["text"]
    assert "chat_template_kwargs" not in payload


def test_payload_stream_flag():
    gw = make_gateway("dashscope")
    payload = gw._payload([{"role": "user", "content": "hi"}], stream=True)
    assert payload["stream"] is True
