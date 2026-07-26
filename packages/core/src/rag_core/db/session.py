"""数据库会话管理。

租户上下文：tenant_session() 在事务内通过 set_config('app.tenant_id', ...) 注入
当前租户，供 RLS 策略读取。应用连接使用非超级用户（finance_rag_app），
未注入租户上下文时 RLS 默认拒绝所有行（default-deny）。
"""

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import lru_cache

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from rag_core.settings import get_settings


@lru_cache
def get_engine() -> AsyncEngine:
    return create_async_engine(get_settings().database_url)


@lru_cache
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False)


async def set_tenant(session: AsyncSession, tenant_id: uuid.UUID) -> None:
    """在当前事务注入租户上下文（RLS 读取 app.tenant_id）。事务级（true），提交后失效。"""
    await session.execute(
        text("SELECT set_config('app.tenant_id', :tid, true)"),
        {"tid": str(tenant_id)},
    )


@asynccontextmanager
async def tenant_session(tenant_id: uuid.UUID) -> AsyncIterator[AsyncSession]:
    """打开一个绑定租户上下文的事务会话（RLS 生效的前提），退出时提交。"""
    async with get_sessionmaker()() as session:
        async with session.begin():
            await set_tenant(session, tenant_id)
            yield session


@lru_cache
def get_admin_engine() -> AsyncEngine:
    return create_async_engine(get_settings().database_admin_url)


@asynccontextmanager
async def admin_session() -> AsyncIterator[AsyncSession]:
    """超级用户会话（绕过 RLS），仅用于登录前的跨租户查找等受控场景。"""
    async with async_sessionmaker(get_admin_engine(), expire_on_commit=False)() as session:
        async with session.begin():
            yield session
