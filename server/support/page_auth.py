"""
support/page_auth.py

页面访问 AK/SK 登录校验与短期 token 生成。
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass

from server.config import get_data_dir
from server.infra.store.workspace_json import load_global_settings

DEFAULT_TOKEN_TTL_SECONDS = 24 * 60 * 60


@dataclass(frozen=True)
class AuthSettings:
    enabled: bool
    access_key: str
    secret_key: str
    token_ttl_seconds: int


def load_auth_settings() -> AuthSettings:
    page_auth = load_global_settings(get_data_dir()).page_auth
    access_key = page_auth.access_key.strip()
    secret_key = page_auth.secret_key.strip()
    token_ttl_seconds = page_auth.token_ttl_seconds or DEFAULT_TOKEN_TTL_SECONDS
    return AuthSettings(
        enabled=bool(page_auth.enabled and access_key and secret_key),
        access_key=access_key,
        secret_key=secret_key,
        token_ttl_seconds=token_ttl_seconds if token_ttl_seconds > 0 else DEFAULT_TOKEN_TTL_SECONDS,
    )


def login_with_aksk(access_key: str, secret_key: str, now: int | None = None) -> dict:
    settings = load_auth_settings()
    if not settings.enabled:
        return {"token": "", "expires_at": 0, "enabled": False}
    if not _constant_time_equal(access_key, settings.access_key) or not _constant_time_equal(secret_key, settings.secret_key):
        raise ValueError("Access Key 或 Secret Key 不正确")
    issued_at = int(now if now is not None else time.time())
    expires_at = issued_at + settings.token_ttl_seconds
    return {
        "token": create_token(settings.access_key, settings.secret_key, expires_at),
        "expires_at": expires_at,
        "enabled": True,
    }


def create_token(access_key: str, secret_key: str, expires_at: int) -> str:
    payload = _b64_json({"ak": access_key, "exp": int(expires_at)})
    signature = _sign(payload, secret_key)
    return f"{payload}.{signature}"


def verify_token(token: str, now: int | None = None) -> bool:
    settings = load_auth_settings()
    if not settings.enabled:
        return True
    payload, sep, signature = token.partition(".")
    if not payload or sep != "." or not signature:
        return False
    expected = _sign(payload, settings.secret_key)
    if not _constant_time_equal(signature, expected):
        return False
    try:
        data = json.loads(_b64_decode(payload).decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return False
    expires_at = int(data.get("exp", 0) or 0)
    access_key = str(data.get("ak", ""))
    current = int(now if now is not None else time.time())
    return _constant_time_equal(access_key, settings.access_key) and expires_at > current


def extract_bearer_token(authorization: str) -> str:
    prefix = "Bearer "
    if not authorization.startswith(prefix):
        return ""
    return authorization[len(prefix):].strip()


def _sign(payload: str, secret_key: str) -> str:
    digest = hmac.new(secret_key.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).digest()
    return _b64_encode(digest)


def _b64_json(data: dict) -> str:
    return _b64_encode(json.dumps(data, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))


def _b64_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))


def _constant_time_equal(left: str, right: str) -> bool:
    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))
