"""SSE 事件格式化（5b/16 共用）。"""

import json
from typing import Any


def sse(event: str, data: dict[str, Any] | None = None) -> str:
    payload = json.dumps(data or {}, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"


def sse_error(code: int, message: str) -> str:
    return sse("error", {"code": code, "message": message})
