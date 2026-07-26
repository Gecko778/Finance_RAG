"""登录：租户标识 + email + 密码 → JWT。"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from rag_core.db.models import AuditLog, Tenant, User
from rag_core.db.session import admin_session
from rag_core.security import verify_password
from sqlalchemy import select

from rag_api.auth import CurrentPrincipal, issue_jwt

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class LoginRequest(BaseModel):
    tenant_slug: str = Field(min_length=1)
    email: str = Field(min_length=1)
    password: str = Field(min_length=1)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str


@router.post("/login")
async def login(req: LoginRequest) -> LoginResponse:
    # 登录前无租户上下文，用管理会话跨租户按 slug→email 定位用户
    async with admin_session() as session:
        tenant = await session.scalar(select(Tenant).where(Tenant.slug == req.tenant_slug))
        user = None
        if tenant is not None:
            user = await session.scalar(
                select(User).where(User.tenant_id == tenant.id, User.email == req.email)
            )
        # 统一失败信息，避免枚举租户/邮箱
        if (
            user is None
            or not user.is_active
            or not verify_password(req.password, user.password_hash)
        ):
            raise HTTPException(401, "租户、邮箱或密码错误")

        session.add(
            AuditLog(
                tenant_id=tenant.id,
                actor_type="user",
                actor_id=user.id,
                action="auth.login",
            )
        )
        return LoginResponse(access_token=issue_jwt(tenant.id, user.id, user.role), role=user.role)


class MeResponse(BaseModel):
    tenant_id: str
    user_id: str
    role: str


@router.get("/me")
async def me(principal: CurrentPrincipal) -> MeResponse:
    """校验当前令牌并返回身份（前端刷新后恢复会话用）。"""
    return MeResponse(
        tenant_id=str(principal.tenant_id),
        user_id=str(principal.actor_id),
        role=principal.role,
    )
