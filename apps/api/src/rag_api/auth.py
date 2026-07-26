"""认证：JWT（前端用户）+ API Key（机器调用）双通道 → 统一 Principal。

- Authorization: Bearer <jwt>  → 用户身份（tenant/user/role）
- X-API-Key: fr_xxx            → 机器身份（tenant/api_key/scopes）
两者取其一即可；都缺则 401。
"""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from fastapi import Depends, Header, HTTPException
from rag_core.db.models import ApiKey
from rag_core.db.session import admin_session
from rag_core.security import hash_api_key
from rag_core.settings import get_settings
from sqlalchemy import select

JWT_ALG = "HS256"


@dataclass
class Principal:
    tenant_id: uuid.UUID
    actor_type: str  # "user" | "api_key"
    actor_id: uuid.UUID
    role: str = "member"  # 用户角色；api_key 恒为 "member"
    scopes: list[str] = field(default_factory=list)  # api_key 授权范围

    @property
    def is_admin(self) -> bool:
        return self.actor_type == "user" and self.role == "admin"

    def has_scope(self, scope: str) -> bool:
        # 用户令牌拥有全部权限；api_key 受 scopes 限制
        return self.actor_type == "user" or scope in self.scopes


def issue_jwt(tenant_id: uuid.UUID, user_id: uuid.UUID, role: str) -> str:
    s = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "tid": str(tenant_id),
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=s.jwt_expire_minutes),
    }
    return jwt.encode(payload, s.jwt_secret, algorithm=JWT_ALG)


def _principal_from_jwt(token: str) -> Principal:
    try:
        payload = jwt.decode(token, get_settings().jwt_secret, algorithms=[JWT_ALG])
    except jwt.PyJWTError:
        raise HTTPException(401, "令牌无效或已过期") from None
    return Principal(
        tenant_id=uuid.UUID(payload["tid"]),
        actor_type="user",
        actor_id=uuid.UUID(payload["sub"]),
        role=payload.get("role", "member"),
    )


async def _principal_from_api_key(plaintext: str) -> Principal:
    key_hash = hash_api_key(plaintext)
    now = datetime.now(UTC)
    async with admin_session() as session:
        row = await session.scalar(select(ApiKey).where(ApiKey.key_hash == key_hash))
        if row is None or row.revoked_at is not None:
            raise HTTPException(401, "API Key 无效或已吊销")
        if row.expires_at is not None and row.expires_at < now.replace(tzinfo=None):
            raise HTTPException(401, "API Key 已过期")
        row.last_used_at = now.replace(tzinfo=None)
        return Principal(
            tenant_id=row.tenant_id,
            actor_type="api_key",
            actor_id=row.id,
            scopes=list(row.scopes or []),
        )


async def get_principal(
    authorization: Annotated[str | None, Header()] = None,
    x_api_key: Annotated[str | None, Header()] = None,
) -> Principal:
    if x_api_key:
        return await _principal_from_api_key(x_api_key)
    if authorization and authorization.startswith("Bearer "):
        return _principal_from_jwt(authorization.removeprefix("Bearer "))
    raise HTTPException(401, "缺少认证：需 Authorization: Bearer <jwt> 或 X-API-Key")


CurrentPrincipal = Annotated[Principal, Depends(get_principal)]


async def require_admin(principal: CurrentPrincipal) -> Principal:
    if not principal.is_admin:
        raise HTTPException(403, "需要管理员权限")
    return principal


AdminPrincipal = Annotated[Principal, Depends(require_admin)]


async def require_user(principal: CurrentPrincipal) -> Principal:
    """限用户令牌（文档管理等前端操作；API Key 仅用于检索/问答）。"""
    if principal.actor_type != "user":
        raise HTTPException(403, "该操作需用户登录，API Key 不可用")
    return principal


UserPrincipal = Annotated[Principal, Depends(require_user)]


def require_scope(scope: str):
    async def _dep(principal: CurrentPrincipal) -> Principal:
        if not principal.has_scope(scope):
            raise HTTPException(403, f"缺少所需权限范围：{scope}")
        return principal

    return _dep
