"""配额：文档数 / 存储量（Postgres 实时统计）、日调用次数（Redis 计数）。"""

import uuid
from datetime import date

from fastapi import HTTPException
from rag_core.db.models import Document, Tenant
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


async def check_document_quota(db: AsyncSession, tenant_id: uuid.UUID, new_bytes: int) -> None:
    """上传前校验：文档数与存储量不超租户配额。超限抛 413。"""
    tenant = await db.get(Tenant, tenant_id)
    stmt = select(
        func.count(Document.id),
        func.coalesce(func.sum(Document.size_bytes), 0),
    ).where(Document.tenant_id == tenant_id, Document.deleted_at.is_(None))
    count, used_bytes = (await db.execute(stmt)).one()

    if count >= tenant.quota_max_documents:
        raise HTTPException(413, f"文档数已达配额上限（{tenant.quota_max_documents}）")
    if (used_bytes + new_bytes) > tenant.quota_max_storage_mb * 1024 * 1024:
        raise HTTPException(413, f"存储空间超出配额（{tenant.quota_max_storage_mb}MB）")


async def check_and_incr_daily_requests(
    redis: Redis, db: AsyncSession, tenant_id: uuid.UUID
) -> None:
    """检索/问答类请求的日调用计数（按租户按日）。超限抛 429。"""
    tenant = await db.get(Tenant, tenant_id)
    key = f"quota:req:{tenant_id}:{date.today().isoformat()}"
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, 172800)  # 2 天后自动清理
    if count > tenant.quota_daily_requests:
        raise HTTPException(429, f"今日调用次数已达配额上限（{tenant.quota_daily_requests}）")
