"""API 依赖：租户会话（由认证 Principal 派生）+ arq 队列。

M4 起租户上下文来自认证（JWT / API Key，见 auth.py），不再用 X-Tenant-Id 头。
"""

from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Annotated

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings
from fastapi import Depends
from rag_core.db.session import get_sessionmaker, set_tenant
from rag_core.settings import get_settings
from sqlalchemy.ext.asyncio import AsyncSession

from rag_api.auth import CurrentPrincipal


async def get_db(principal: CurrentPrincipal) -> AsyncIterator[AsyncSession]:
    """请求作用域会话：注入租户上下文。

    写操作应在处理器内显式 `await db.commit()`，以保证响应返回前落库
    （避免"吊销后立即复用""上传后 worker 抢跑"等读写竞态）。
    未显式提交的读操作由此处兜底提交/回滚。
    """
    async with get_sessionmaker()() as session:
        await set_tenant(session, principal.tenant_id)
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


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
