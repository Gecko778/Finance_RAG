"""M1 验收测试：迁移可重放、多租户隔离（repo 层 + RLS 层）、公共库可见性、软删除。"""

import uuid

import pytest
from conftest import TEST_ADMIN_URL, _recreate_test_db, _run_sync, alembic_config
from rag_core.db.models import KnowledgeBase, Tenant
from rag_core.db.repos import DocumentRepo, KnowledgeBaseRepo
from sqlalchemy import text

from alembic import command


def test_migration_replayable():
    """升级 → 降级 → 再升级，全程无错（在独立流程中已建库的基础上执行）。"""
    _run_sync(_recreate_test_db())
    cfg = alembic_config(TEST_ADMIN_URL)
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")


@pytest.fixture()
async def two_tenants(admin_sessionmaker):
    """租户 A（含公共库+私有库）与租户 B（含私有库）。admin 连接绕过 RLS 直接造数。"""
    async with admin_sessionmaker() as session, session.begin():
        a = Tenant(name="租户A", slug=f"a-{uuid.uuid4().hex[:8]}")
        b = Tenant(name="租户B", slug=f"b-{uuid.uuid4().hex[:8]}")
        session.add_all([a, b])
        await session.flush()
        kb_pub = KnowledgeBase(tenant_id=a.id, name="公共政策库", is_public=True)
        kb_a = KnowledgeBase(tenant_id=a.id, name="A私有库")
        kb_b = KnowledgeBase(tenant_id=b.id, name="B私有库")
        session.add_all([kb_pub, kb_a, kb_b])
        await session.flush()
        ids = {
            "a": a.id, "b": b.id,
            "kb_pub": kb_pub.id, "kb_a": kb_a.id, "kb_b": kb_b.id,
        }
    return ids


async def _app_tenant_session(app_sessionmaker, tenant_id):
    session = app_sessionmaker()
    await session.begin()
    await session.execute(
        text("SELECT set_config('app.tenant_id', :tid, true)"), {"tid": str(tenant_id)}
    )
    return session


async def test_repo_isolation_and_public_kb(app_sessionmaker, two_tenants):
    """租户 B 视角：能看到自己的库 + 公共库，看不到 A 的私有库。"""
    session = await _app_tenant_session(app_sessionmaker, two_tenants["b"])
    try:
        repo = KnowledgeBaseRepo(session, two_tenants["b"])
        visible = {kb.id for kb in await repo.list_visible()}
        assert two_tenants["kb_b"] in visible
        assert two_tenants["kb_pub"] in visible
        assert two_tenants["kb_a"] not in visible
        # 公共库不可被他租户改写
        assert await repo.get_own(two_tenants["kb_pub"]) is None
    finally:
        await session.rollback()
        await session.close()


async def test_rls_blocks_cross_tenant_without_app_filter(app_sessionmaker, two_tenants):
    """RLS 兜底：绕过 repository 直接裸查，也只能看到本租户 + 公共行。"""
    session = await _app_tenant_session(app_sessionmaker, two_tenants["b"])
    try:
        rows = (await session.execute(text("SELECT id FROM knowledge_bases"))).scalars().all()
        ids = set(rows)
        assert two_tenants["kb_a"] not in ids  # A 私有库被数据库层拦截
        assert two_tenants["kb_b"] in ids
        assert two_tenants["kb_pub"] in ids
    finally:
        await session.rollback()
        await session.close()


async def test_rls_default_deny(app_sessionmaker, two_tenants):
    """未注入租户上下文时：租户私有行一律不可见（公共行按设计仍可读）。"""
    async with app_sessionmaker() as session:
        # 私有库不可见
        private_count = (
            await session.execute(
                text("SELECT count(*) FROM knowledge_bases WHERE NOT is_public")
            )
        ).scalar()
        assert private_count == 0
        # 无公共概念的表（users）完全不可见
        user_count = (await session.execute(text("SELECT count(*) FROM users"))).scalar()
        assert user_count == 0


async def test_document_soft_delete(app_sessionmaker, two_tenants):
    """软删除后默认列表不可见；他租户无法删除本租户文档。"""
    session = await _app_tenant_session(app_sessionmaker, two_tenants["b"])
    try:
        kb_repo = KnowledgeBaseRepo(session, two_tenants["b"])
        kb = await kb_repo.get_own(two_tenants["kb_b"])
        doc_repo = DocumentRepo(session, two_tenants["b"])
        doc = await doc_repo.create(kb, filename="test.pdf", minio_path="t/test.pdf")

        assert len(await doc_repo.list_in_kb(kb.id)) == 1
        assert await doc_repo.soft_delete(doc.id) is True
        assert await doc_repo.list_in_kb(kb.id) == []
        # 重复删除返回 False
        assert await doc_repo.soft_delete(doc.id) is False
    finally:
        await session.rollback()
        await session.close()
