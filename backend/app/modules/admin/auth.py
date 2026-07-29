"""管理后台鉴权：单管理员密码 → HMAC token（无第三方依赖）。

token 形如 "{expires_ts}.{hex_sig}"，签名密钥由 ADMIN_PASSWORD 派生；
改密码即令所有已签发 token 失效。单管理员方案，不做多账号/角色。
"""

import hashlib
import hmac
import time

from fastapi import Request

from app.core.config import get_settings
from app.core.errors import AppError


def _secret() -> bytes:
    settings = get_settings()
    return hashlib.sha256(
        f"englishlearn-admin:{settings.admin_password}".encode()
    ).digest()


def issue_token() -> str:
    settings = get_settings()
    expires = int(time.time()) + settings.admin_token_ttl
    sig = hmac.new(_secret(), str(expires).encode(), hashlib.sha256).hexdigest()
    return f"{expires}.{sig}"


def verify_token(token: str) -> bool:
    try:
        expires_str, sig = token.split(".", 1)
        expires = int(expires_str)
    except ValueError:
        return False
    if expires < time.time():
        return False
    expected = hmac.new(_secret(), expires_str.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(sig, expected)


def unauthorized(msg: str = "unauthorized") -> AppError:
    return AppError(401, msg)


async def require_admin(request: Request) -> None:
    """FastAPI 依赖：校验 Authorization: Bearer {token}，失败 401。"""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise unauthorized("missing bearer token")
    if not verify_token(auth[7:].strip()):
        raise unauthorized("invalid or expired token")
