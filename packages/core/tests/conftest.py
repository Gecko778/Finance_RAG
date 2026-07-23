"""集成测试夹具：临时测试库 + 迁移 + 双引擎（admin / app）。

前置：docker compose 的 PostgreSQL 已启动。
"""

import asyncio
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from alembic import command

REPO_ROOT = Path(__file__).resolve().parents[3]

ADMIN_MAINT_URL = "postgresql+asyncpg://finance_rag:finance_rag_dev@localhost:5432/finance_rag"
TEST_DB = "finance_rag_test"
TEST_ADMIN_URL = f"postgresql+asyncpg://finance_rag:finance_rag_dev@localhost:5432/{TEST_DB}"
TEST_APP_URL = (
    f"postgresql+asyncpg://finance_rag_app:finance_rag_app_dev@localhost:5432/{TEST_DB}"
)


def _run_sync(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


async def _recreate_test_db() -> None:
    engine = create_async_engine(ADMIN_MAINT_URL, isolation_level="AUTOCOMMIT")
    async with engine.connect() as conn:
        await conn.execute(text(f"DROP DATABASE IF EXISTS {TEST_DB} WITH (FORCE)"))
        await conn.execute(text(f"CREATE DATABASE {TEST_DB}"))
    await engine.dispose()


def alembic_config(url: str) -> Config:
    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    cfg.cmd_opts = None
    cfg.attributes["configure_logger"] = False
    # env.py 通过 -x db_url 覆盖连接
    cfg.cmd_opts = type("Opts", (), {"x": [f"db_url={url}"]})()
    return cfg


@pytest.fixture(scope="session")
def migrated_db():
    """新建测试库并升级到 head（session 级，跑一次）。"""
    _run_sync(_recreate_test_db())
    command.upgrade(alembic_config(TEST_ADMIN_URL), "head")
    yield TEST_ADMIN_URL


@pytest.fixture()
def admin_sessionmaker(migrated_db):
    engine = create_async_engine(TEST_ADMIN_URL)
    yield async_sessionmaker(engine, expire_on_commit=False)
    _run_sync(engine.dispose())


@pytest.fixture()
def app_sessionmaker(migrated_db):
    """应用角色连接：非超级用户，RLS 生效。"""
    engine = create_async_engine(TEST_APP_URL)
    yield async_sessionmaker(engine, expire_on_commit=False)
    _run_sync(engine.dispose())
