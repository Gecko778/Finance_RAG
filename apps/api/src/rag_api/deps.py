"""API 依赖：租户上下文 + 数据库会话 + arq 队列。

⚠️ M2 临时方案：租户从 X-Tenant-Id 请求头读取（仅开发环境）。
M4 将替换为 JWT / API Key 正式认证。
"""

import uuid
from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Annotated

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings
from fastapi import Depends, Header, HTTPException
from rag_core.db.session import tenant_session
from rag_core.settings import get_settings
from sqlalchemy.ext.asyncio import AsyncSession


async def get_tenant_id(x_tenant_id: Annotated[str, Header()]) -> uuid.UUID:
    try:
        return uuid.UUID(x_tenant_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="X-Tenant-Id 必须是 UUID") from None


TenantId = Annotated[uuid.UUID, Depends(get_tenant_id)]


async def get_db(tenant_id: TenantId) -> AsyncIterator[AsyncSession]:
    async with tenant_session(tenant_id) as session:
        yield session


Db = Annotated[AsyncSession, Depends(get_db)]


@lru_cache
def _redis_settings() -> RedisSettings:
    return RedisSettings.from_dsn(get_settings().redis_url)


_pool: ArqRedis | None = None


async def get_queue() -> ArqRedis:
    global _pool
    if _pool is None:
        _pool = await create_pool(_redis_settings())
    return _pool


Queue = Annotated[ArqRedis, Depends(get_queue)]
