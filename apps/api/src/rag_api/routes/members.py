"""成员管理（仅管理员）：列表、创建、启用/停用。"""

import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from rag_core.db.models import USER_ROLES, User
from rag_core.security import hash_password
from sqlalchemy import select

from rag_api.auth import AdminPrincipal
from rag_api.deps import Db
from rag_api.services import audit

router = APIRouter(prefix="/api/v1/members", tags=["members"])


class MemberOut(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str
    role: str
    is_active: bool
    created_at: datetime

    @classmethod
    def from_model(cls, u: User) -> "MemberOut":
        return cls(
            id=u.id, email=u.email, display_name=u.display_name,
            role=u.role, is_active=u.is_active, created_at=u.created_at,
        )


class CreateMemberRequest(BaseModel):
    email: str = Field(min_length=1, max_length=255)
    display_name: str = ""
    role: str = "member"
    password: str = Field(min_length=6, max_length=128)


class SetStatusRequest(BaseModel):
    is_active: bool


@router.get("")
async def list_members(principal: AdminPrincipal, db: Db) -> list[MemberOut]:
    rows = (await db.scalars(select(User).where(User.tenant_id == principal.tenant_id))).all()
    return [MemberOut.from_model(u) for u in rows]


@router.post("", status_code=201)
async def create_member(req: CreateMemberRequest, principal: AdminPrincipal, db: Db) -> MemberOut:
    if req.role not in USER_ROLES:
        raise HTTPException(422, f"无效角色 {req.role}，可选：{USER_ROLES}")
    existing = await db.scalar(
        select(User).where(User.tenant_id == principal.tenant_id, User.email == req.email)
    )
    if existing is not None:
        raise HTTPException(409, "该邮箱已存在")
    user = User(
        tenant_id=principal.tenant_id, email=req.email, display_name=req.display_name,
        role=req.role, password_hash=hash_password(req.password),
    )
    db.add(user)
    await db.flush()
    audit.record(db, principal, "member.create", "user", user.id, {"email": req.email})
    await db.commit()
    return MemberOut.from_model(user)


@router.post("/{user_id}/status")
async def set_member_status(
    user_id: uuid.UUID, req: SetStatusRequest, principal: AdminPrincipal, db: Db
) -> MemberOut:
    if user_id == principal.actor_id:
        raise HTTPException(400, "不能停用自己的账号")
    user = await db.get(User, user_id)
    if user is None or user.tenant_id != principal.tenant_id:
        raise HTTPException(404, "成员不存在")
    user.is_active = req.is_active
    action = "member.activate" if req.is_active else "member.deactivate"
    audit.record(db, principal, action, "user", user_id)
    await db.commit()
    return MemberOut.from_model(user)
