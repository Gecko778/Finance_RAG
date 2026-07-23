"""Repository 层：应用侧强制租户过滤（RLS 之上的第一道防线）。

约定：所有查询必须经 repository，构造时传入 tenant_id，查询自动过滤。
"""

import uuid
from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from rag_core.db.models import Document, KnowledgeBase


class KnowledgeBaseRepo:
    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID):
        self.session = session
        self.tenant_id = tenant_id

    async def create(
        self, name: str, description: str = "", is_public: bool = False
    ) -> KnowledgeBase:
        kb = KnowledgeBase(
            tenant_id=self.tenant_id, name=name, description=description, is_public=is_public
        )
        self.session.add(kb)
        await self.session.flush()
        return kb

    async def list_visible(self) -> list[KnowledgeBase]:
        """本租户私有库 + 平台公共库。"""
        stmt = select(KnowledgeBase).where(
            or_(
                KnowledgeBase.tenant_id == self.tenant_id,
                KnowledgeBase.is_public.is_(True),
            )
        )
        return list((await self.session.scalars(stmt)).all())

    async def get_own(self, kb_id: uuid.UUID) -> KnowledgeBase | None:
        """仅本租户自有库（写操作前使用，公共库不可被他租户改写）。"""
        stmt = select(KnowledgeBase).where(
            KnowledgeBase.id == kb_id, KnowledgeBase.tenant_id == self.tenant_id
        )
        return await self.session.scalar(stmt)


class DocumentRepo:
    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID):
        self.session = session
        self.tenant_id = tenant_id

    async def create(self, kb: KnowledgeBase, filename: str, minio_path: str, **fields) -> Document:
        doc = Document(
            tenant_id=self.tenant_id,
            kb_id=kb.id,
            filename=filename,
            minio_path=minio_path,
            is_public=kb.is_public,
            **fields,
        )
        self.session.add(doc)
        await self.session.flush()
        return doc

    async def list_in_kb(self, kb_id: uuid.UUID) -> list[Document]:
        """本租户视角的文档列表：排除软删除；公共库文档全租户可见。"""
        stmt = select(Document).where(
            Document.kb_id == kb_id,
            Document.deleted_at.is_(None),
            or_(Document.tenant_id == self.tenant_id, Document.is_public.is_(True)),
        )
        return list((await self.session.scalars(stmt)).all())

    async def soft_delete(self, doc_id: uuid.UUID) -> bool:
        """软删除：仅本租户自有文档。返回是否删除成功。"""
        stmt = select(Document).where(
            Document.id == doc_id,
            Document.tenant_id == self.tenant_id,
            Document.deleted_at.is_(None),
        )
        doc = await self.session.scalar(stmt)
        if doc is None:
            return False
        doc.deleted_at = datetime.now()
        await self.session.flush()
        return True
