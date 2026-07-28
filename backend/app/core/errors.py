"""统一业务异常与响应包裹。

api.md 约定：统一响应 { code, data, message }，HTTP 状态码与 code 同步；
SSE 接口（5b/16）建流前错误仍走 JSON 统一包裹，建流后以 error 事件下发。
"""

from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    """业务异常：code 即 HTTP 状态码，与统一响应体 code 同步。"""

    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


# 便捷构造器
def bad_request(msg: str) -> AppError:
    return AppError(400, msg)


def not_found(msg: str = "not found") -> AppError:
    return AppError(404, msg)


def conflict(msg: str) -> AppError:
    return AppError(409, msg)


def payload_too_large(msg: str = "audio too large") -> AppError:
    return AppError(413, msg)


def ok(data: Any = None, message: str = "ok") -> dict:
    return {"code": 0, "data": data, "message": message}


def _envelope(code: int, message: str, data: Any = None) -> JSONResponse:
    return JSONResponse(
        status_code=code if code >= 400 else 200,
        content={"code": code, "data": data, "message": message},
    )


async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    return _envelope(exc.code, exc.message)


async def unhandled_error_handler(_: Request, exc: Exception) -> JSONResponse:
    return _envelope(500, f"internal error: {exc}")
