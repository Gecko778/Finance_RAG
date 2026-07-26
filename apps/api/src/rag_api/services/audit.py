"""审计日志：敏感操作留痕（财务合规要求）。"""

import uuid

from rag_core.db.models import AuditLog
from sqlalchemy.ext.asyncio import AsyncSession

from rag_api.auth import Principal


def record(
    session: AsyncSession,
    principal: Principal,
    action: str,
    resource_type: str = "",
    resource_id: uuid.UUID | None = None,
    detail: dict | None = None,
) -> None:
    """写一条审计记录（随当前事务提交）。action 形如 document.upload / apikey.revoke。"""
    session.add(
        AuditLog(
            tenant_id=principal.tenant_id,
            actor_type=principal.actor_type,
            actor_id=principal.actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            detail=detail or {},
        )
    )
