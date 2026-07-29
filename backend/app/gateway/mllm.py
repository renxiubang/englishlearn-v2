"""多模态大模型网关（OpenAI 兼容 /chat/completions）。

接入方式参考 ai-v2（已验证）：Bearer Key、input_audio content part、
temperature=0.0、chat_template_kwargs 关思考、reasoning_content 回退。
职责拆分重设计：方法默认单一职责、纯文本输出，无格式标记解析
（例外：transcribe_correct 为单次复合指令 + JSON 结构化输出）。

provider 兼容开关（settings.mllm_provider）：
- local：本地 Gemma（默认）；
- dashscope：百炼 Qwen-Omni（compatible-mode），三处差异适配：
  ① input_audio.data 加 data:;base64, 前缀；② 去 chat_template_kwargs 改传
  modalities:["text"]；③ 仅支持流式，非流式方法内部收流聚合，对上层透明。
"""

import json
import logging
import re
from typing import Any, AsyncIterator

import httpx

from app.core.config import Settings
from app.gateway.prompts import get_prompt

logger = logging.getLogger(__name__)

# 上下文消息（来自 messages 表）：{"role": "user"|"assistant", "content": str}
Context = list[dict[str, str]]


def parse_transcribe_correct(raw_output: str) -> tuple[str, str]:
    """解析 transcribe_correct 的 JSON 输出，返回 (raw, en)。

    复用 verify_semantic 模式：正则取首个 {...} + json.loads。
    两类降级分开处理：
    - JSON 结构损坏（无 {...} 或 json.loads 失败）：打 "parse failed"，
      raw = en = 模型原文（strip 后），保留可读信息交下游兜底；
    - JSON 正常但 raw/en 为空（模型没听清）：打 "empty transcription"，
      返回 ("", "")，不把带围栏的 JSON 原文透传给下游。
    """
    text = (raw_output or "").strip()
    try:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        data = json.loads(m.group(0) if m else text)
    except (json.JSONDecodeError, AttributeError):
        logger.warning(f"transcribe_correct JSON parse failed: {text[:200]!r}")
        return text, text
    raw = str(data.get("raw") or "").strip()
    en = str(data.get("en") or "").strip()
    if not en:
        logger.warning(f"transcribe_correct empty transcription: {text[:200]!r}")
        return "", ""
    return raw or en, en


def _audio_part(audio_b64: str, provider: str = "local") -> dict[str, Any]:
    # dashscope（百炼 Qwen-Omni）要求 base64 带 data URI 前缀
    data = f"data:;base64,{audio_b64}" if provider == "dashscope" else audio_b64
    return {
        "type": "input_audio",
        "input_audio": {"data": data, "format": "wav"},
    }


def _dump_messages(messages: list[dict]) -> str:
    """DEBUG 用：序列化送模型的完整 messages，音频 base64 替换为占位符。"""
    safe: list[dict] = []
    for msg in messages:
        content = msg.get("content")
        if isinstance(content, list):
            parts = []
            for part in content:
                if part.get("type") == "input_audio":
                    data = part.get("input_audio", {}).get("data", "")
                    parts.append({"type": "input_audio",
                                  "data": f"<base64 {len(data)} chars>"})
                else:
                    parts.append(part)
            safe.append({"role": msg.get("role"), "content": parts})
        else:
            safe.append(msg)
    return json.dumps(safe, ensure_ascii=False, indent=2)


class MLLMGateway:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None):
        self._settings = settings
        self._model = settings.mllm_model
        self._provider = settings.mllm_provider
        self._client = client or httpx.AsyncClient(
            base_url=settings.mllm_base_url,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {settings.mllm_api_key}",
            },
            timeout=settings.mllm_timeout,
        )

    async def aclose(self):
        await self._client.aclose()

    # ── 底层调用 ─────────────────────────────────────────

    def _payload(self, messages: list[dict], *, stream: bool = False,
                 max_tokens: int = 512) -> dict[str, Any]:
        # 临时排查用：LOG_LEVEL=DEBUG 时输出送模型的完整上下文（音频已脱敏）
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("MLLM request messages:\n%s", _dump_messages(messages))
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.0,
        }
        if self._provider == "dashscope":
            # Qwen-Omni：只要文本输出；无 chat_template_kwargs（本地 Gemma 专用）
            payload["modalities"] = ["text"]
        else:
            # 关闭 Gemma 思考模式（ai-v2 实测必需）
            payload["chat_template_kwargs"] = {"enable_thinking": False}
        if stream:
            payload["stream"] = True
        return payload

    async def _complete(self, messages: list[dict], max_tokens: int = 512) -> str:
        """非流式补全，返回完整文本（reasoning_content 回退）。

        dashscope（Qwen-Omni）仅支持流式：内部收流聚合，对上层透明。
        """
        if self._provider == "dashscope":
            parts = [
                token
                async for token in self._complete_stream(messages, max_tokens)
            ]
            return "".join(parts).strip()
        resp = await self._client.post(
            "/chat/completions", json=self._payload(messages, max_tokens=max_tokens)
        )
        resp.raise_for_status()
        message = resp.json()["choices"][0]["message"]
        content = message.get("content") or message.get("reasoning_content") or ""
        return content.strip()

    async def _complete_stream(
        self, messages: list[dict], max_tokens: int = 512
    ) -> AsyncIterator[str]:
        """流式补全，逐 token 产出（SSE 解析，reasoning_content 回退）。"""
        payload = self._payload(messages, stream=True, max_tokens=max_tokens)
        async with self._client.stream(
            "POST", "/chat/completions", json=payload
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data_str = line[6:]
                if data_str == "[DONE]":
                    break
                try:
                    chunk = json.loads(data_str)
                except json.JSONDecodeError:
                    continue
                choices = chunk.get("choices", [])
                if not choices:
                    continue
                delta = choices[0].get("delta", {})
                token = delta.get("content") or delta.get("reasoning_content") or ""
                if token:
                    yield token

    # ── 业务方法（默认单一职责、纯文本输出）──────────────

    async def reply_stream(
        self, persona_prompt: str, context: Context,
        *, audio_b64: str | None = None, text: str | None = None,
    ) -> AsyncIterator[str]:
        """对话回复（5a/5b 阶段A）：流式输出英文回复文本。

        system = persona（DB） + chat_reply 任务规则（prompts.yaml）。
        语音输入时最后一条 user message 附 input_audio content part。
        """
        system = f"{persona_prompt.strip()}\n\n{get_prompt('chat_reply')}"
        messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
        messages.extend(context)
        if audio_b64 is not None:
            messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": "(voice message)"},
                    _audio_part(audio_b64, self._provider),
                ],
            })
        else:
            messages.append({"role": "user", "content": text or ""})
        async for token in self._complete_stream(messages, max_tokens=256):
            yield token

    async def reply_text(
        self, persona_prompt: str, context: Context, text: str
    ) -> str:
        """对话回复（5a 文本同步）：非流式。"""
        system = f"{persona_prompt.strip()}\n\n{get_prompt('chat_reply')}"
        messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
        messages.extend(context)
        messages.append({"role": "user", "content": text})
        return await self._complete(messages, max_tokens=256)

    async def transcribe(self, audio_b64: str, lang: str) -> str:
        """音频→原文转录（级联阶段一）。lang: 'en' | 'zh'。"""
        system = get_prompt(f"transcribe_{lang}")
        messages = [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Audio Transcription Task:"},
                    _audio_part(audio_b64, self._provider),
                ],
            },
        ]
        return await self._complete(messages, max_tokens=512)

    async def transcribe_correct(self, audio_b64: str) -> tuple[str, str]:
        """转录+语法修正（5b 阶段B）：返回 (raw 原译, en 纠译)。

        单次复合指令 + JSON 结构化输出 {"raw": ..., "en": ...}，是对
        "单一职责纯文本"规范的产品有意例外（见 architecture.md §1.4）。
        解析失败降级：raw = en = 模型原文（strip 后），不向前端抛错。
        """
        system = get_prompt("transcribe_correct")
        messages = [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Audio Transcription Task:"},
                    _audio_part(audio_b64, self._provider),
                ],
            },
        ]
        raw_output = await self._complete(messages, max_tokens=512)
        return parse_transcribe_correct(raw_output)

    async def translate(self, text: str, direction: str) -> str:
        """纯文本翻译（级联阶段二）。direction: 'en_to_zh' | 'zh_to_en'。"""
        system = get_prompt(f"translate_{direction}")
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": text},
        ]
        return await self._complete(messages, max_tokens=512)

    async def verify_semantic(
        self, audio_b64: str, target_en: str
    ) -> tuple[bool, str | None]:
        """复读语义校验（接口 17）：级联转录 + JSON 判定。

        解析失败按不一致处理（api.md：consistent=false + reason）。
        """
        transcription = await self.transcribe(audio_b64, "en")
        if not transcription:
            return False, "未能识别到语音内容，请再试一次"
        system = get_prompt("verify_semantic")
        user = (
            f"Target sentence: {target_en}\n"
            f"Student's transcription: {transcription}"
        )
        raw = await self._complete(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=128,
        )
        try:
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            data = json.loads(m.group(0) if m else raw)
            consistent = bool(data.get("consistent"))
            reason = data.get("reason") or None
            if not consistent and not reason:
                reason = "复读内容与目标句语义不符，请再试一次"
            return consistent, None if consistent else reason
        except (json.JSONDecodeError, AttributeError):
            logger.warning(f"verify_semantic JSON parse failed: {raw[:200]!r}")
            return False, "复读内容与目标句语义不符，请再试一次"

    async def ping(self) -> bool:
        """连通性探测（/models）。"""
        try:
            resp = await self._client.get("/models")
            resp.raise_for_status()
            return True
        except httpx.HTTPError as e:
            logger.warning(f"MLLM not reachable: {e}")
            return False
