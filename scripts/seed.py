"""种子数据：平台租户 + 管理员 + 公共政策库 + 示例私有库。

使用管理连接（绕过 RLS）。幂等：按 slug 判断，已存在则跳过。
用法：uv run python scripts/seed.py
"""

import asyncio
import os

import bcrypt
from rag_core.db.models import KnowledgeBase, Tenant, User
from rag_core.settings import get_settings
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

PLATFORM_SLUG = "platform"
ADMIN_EMAIL = os.environ.get("SEED_ADMIN_EMAIL", "admin@finance-rag.local")
ADMIN_PASSWORD = os.environ.get("SEED_ADMIN_PASSWORD", "admin123")


async def main() -> None:
    engine = create_async_engine(get_settings().database_admin_url)
    async with async_sessionmaker(engine)() as session, session.begin():
        existing = await session.scalar(select(Tenant).where(Tenant.slug == PLATFORM_SLUG))
        if existing is not None:
            print(f"种子已存在（tenant slug={PLATFORM_SLUG}），跳过")
            return

        tenant = Tenant(name="平台租户（本公司）", slug=PLATFORM_SLUG)
        session.add(tenant)
        await session.flush()

        session.add(
            User(
                tenant_id=tenant.id,
                email=ADMIN_EMAIL,
                password_hash=bcrypt.hashpw(
                    ADMIN_PASSWORD.encode(), bcrypt.gensalt()
                ).decode(),
                display_name="管理员",
                role="admin",
            )
        )
        session.add(
            KnowledgeBase(
                tenant_id=tenant.id,
                name="全国财税政策库（公共）",
                description="平台维护的权威财税政策库，所有租户可检索",
                is_public=True,
            )
        )
        session.add(
            KnowledgeBase(
                tenant_id=tenant.id,
                name="内部SOP（私有）",
                description="本公司内部流程文档，仅平台租户可见",
            )
        )
        print(f"种子完成：tenant={tenant.id} admin={ADMIN_EMAIL}")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
