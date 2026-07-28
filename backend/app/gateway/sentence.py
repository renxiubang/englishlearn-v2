"""按句断句：供流式文本增量边生成边驱动 TTS。"""

import re

# 句末标点后接空白处切分（对齐 ai-v2 _split_sentences）
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
MIN_SENTENCE_LEN = 8


class SentenceAccumulator:
    """累积流式 token，吐出完整句子；剩余不足一句的留在缓冲区。

    过短的句子（如 "OK."）不单独发射，与后续句子合并，避免碎片化 TTS 调用。
    """

    def __init__(self, min_len: int = MIN_SENTENCE_LEN):
        self._buf = ""
        self._min_len = min_len

    def push(self, delta: str) -> list[str]:
        """喂入文本增量，返回本次可发射的完整句子列表。"""
        self._buf += delta
        parts = _SENTENCE_END.split(self._buf)
        remainder = parts.pop()  # 最后一段未见句末+空白，视为未完成
        out: list[str] = []
        acc = ""
        for p in parts:
            acc = f"{acc} {p}".strip() if acc else p.strip()
            if len(acc) >= self._min_len:
                out.append(acc)
                acc = ""
        # 不足最小长度的完整短句回填缓冲区，与后续增量继续合并
        # （保留句后空格作分隔，避免与后续 token 粘连）
        self._buf = f"{acc} {remainder}" if acc else remainder
        return out

    def flush(self) -> str | None:
        """流结束时取出缓冲区剩余文本（若有）。"""
        tail = self._buf.strip()
        self._buf = ""
        return tail or None
