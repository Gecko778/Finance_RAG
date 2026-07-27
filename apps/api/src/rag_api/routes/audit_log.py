"""审计日志查询（仅管理员）：按时间倒序，可按 action 过滤。"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Query
from pydantic import BaseModel
from rag_core.db.models import AuditLog
from sqlalchemy import select

from rag_api.auth import AdminPrincipal
from rag_api.deps import Db

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])


class AuditLogOut(BaseModel):
    id: uuid.UUID
    actor_type: str
    actor_id: uuid.UUID | None
    action: str
    resource_type: str
    resource_id: uuid.UUID | None
    detail: dict
    created_at: datetime


@router.get("")
async def list_audit_logs(
    principal: AdminPrincipal,
    db: Db,
    limit: int = Query(default=50, ge=1, le=200),
    action: str | None = None,
) -> list[AuditLogOut]:
    stmt = select(AuditLog).where(AuditLog.tenant_id == principal.tenant_id)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    stmt = stmt.order_by(AuditLog.created_at.desc()).limit(limit)
    rows = (await db.scalars(stmt)).all()
    return [
        AuditLogOut(
            id=r.id, actor_type=r.actor_type, actor_id=r.actor_id, action=r.action,
            resource_type=r.resource_type, resource_id=r.resource_id,
            detail=r.detail, created_at=r.created_at,
        )
        for r in rows
    ]
