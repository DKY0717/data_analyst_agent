"""用户认证模块：JWT Token + API Key 双模式支持。"""

from __future__ import annotations

import hashlib
import os
import time
from dataclasses import dataclass, field
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..config import settings
from ..utils.logger import logger

JWT_SECRET = os.getenv("JWT_SECRET", "")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_SECONDS = int(os.getenv("JWT_EXPIRE_SECONDS", "86400"))
API_KEYS_RAW = os.getenv("API_KEYS", "")

_bearer_scheme = HTTPBearer(auto_error=False)


def _hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def _load_api_keys() -> dict[str, str]:
    if not API_KEYS_RAW:
        return {}
    keys = {}
    for raw in API_KEYS_RAW.split(","):
        raw = raw.strip()
        if raw:
            keys[_hash_key(raw)] = raw[:8] + "..."
    return keys


_api_keys: dict[str, str] = {}


def get_api_keys() -> dict[str, str]:
    global _api_keys
    if not _api_keys:
        _api_keys = _load_api_keys()
    return _api_keys


def reload_api_keys() -> None:
    global _api_keys
    _api_keys = _load_api_keys()


def is_auth_enabled() -> bool:
    return bool(JWT_SECRET or get_api_keys())


@dataclass
class AuthUser:
    user_id: str
    auth_method: str  # "jwt" or "api_key"
    roles: list[str] = field(default_factory=lambda: ["user"])


def create_jwt_token(user_id: str, roles: list[str] | None = None) -> dict:
    if not JWT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="JWT_SECRET 未配置，无法生成 Token",
        )
    now = int(time.time())
    payload = {
        "sub": user_id,
        "roles": roles or ["user"],
        "iat": now,
        "exp": now + JWT_EXPIRE_SECONDS,
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return {"access_token": token, "token_type": "bearer", "expires_in": JWT_EXPIRE_SECONDS}


def verify_jwt_token(token: str) -> AuthUser:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return AuthUser(
            user_id=payload["sub"],
            auth_method="jwt",
            roles=payload.get("roles", ["user"]),
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token 已过期")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token 无效")


def verify_api_key(key: str) -> AuthUser:
    keys = get_api_keys()
    hashed = _hash_key(key)
    if hashed in keys:
        return AuthUser(user_id=f"apikey:{keys[hashed]}", auth_method="api_key")
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API Key 无效")


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> AuthUser | None:
    """
    FastAPI 依赖注入：从请求中提取并验证用户身份。

    认证方式（按优先级）：
    1. Authorization: Bearer <jwt_token>
    2. X-API-Key: <api_key>
    3. ?api_key=<query_param>

    如果未启用认证（JWT_SECRET 和 API_KEYS 均未配置），返回 None（放行模式）。
    """
    if not is_auth_enabled():
        return None

    # 方式 1: Bearer Token
    if credentials and credentials.credentials:
        token = credentials.credentials
        if token.count(".") == 2:
            return verify_jwt_token(token)
        return verify_api_key(token)

    # 方式 2: X-API-Key Header
    api_key = request.headers.get("X-API-Key")
    if api_key:
        return verify_api_key(api_key)

    # 方式 3: Query Parameter
    api_key = request.query_params.get("api_key")
    if api_key:
        return verify_api_key(api_key)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="缺少认证凭证。请提供 Authorization Bearer Token 或 X-API-Key。",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_optional_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> AuthUser | None:
    """
    可选认证：有凭证则验证，无凭证则返回 None。
    用于不需要强制认证但支持认证的端点。
    """
    if not is_auth_enabled():
        return None

    try:
        if credentials and credentials.credentials:
            token = credentials.credentials
            if token.count(".") == 2:
                return verify_jwt_token(token)
            return verify_api_key(token)

        api_key = request.headers.get("X-API-Key") or request.query_params.get("api_key")
        if api_key:
            return verify_api_key(api_key)
    except HTTPException:
        return None

    return None
