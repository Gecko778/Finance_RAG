"""知识库管理：列表（本租户+公共）、创建、删除。"""

import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from rag_core.db.models import Document, KnowledgeBase
from rag_core.db.repos import KnowledgeBaseRepo
from sqlalchemy import func, select

from rag_api.auth import AdminPrincipal, UserPrincipal
from rag_api.deps import Db
from rag_api.services import audit

router = APIRouter(prefix="/api/v1/kbs", tags=["knowledge_bases"])


class KnowledgeBaseOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str
    is_public: bool
    created_at: datetime

    @classmethod
    def from_model(cls, kb: KnowledgeBase) -> "KnowledgeBaseOut":
        return cls(
            id=kb.id, name=kb.name, description=kb.description,
            is_public=kb.is_public, created_at=kb.created_at,
        )


class CreateKnowledgeBaseRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str = ""


@router.get("")
async def list_kbs(principal: UserPrincipal, db: Db) -> list[KnowledgeBaseOut]:
    kbs = await KnowledgeBaseRepo(db, principal.tenant_id).list_visible()
    return [KnowledgeBaseOut.from_model(kb) for kb in kbs]


@router.post("", status_code=201)
async def create_kb(
    req: CreateKnowledgeBaseRequest, principal: UserPrincipal, db: Db
) -> KnowledgeBaseOut:
    repo = KnowledgeBaseRepo(db, principal.tenant_id)
    # 同租户内知识库名唯一（DB 有唯一约束，这里提前给友好报错）
    existing = await db.scalar(
        select(KnowledgeBase).where(
            KnowledgeBase.tenant_id == principal.tenant_id, KnowledgeBase.name == req.name
        )
    )
    if existing is not None:
        raise HTTPException(409, "同名知识库已存在")
    kb = await repo.create(name=req.name, description=req.description)
    audit.record(db, principal, "kb.create", "knowledge_base", kb.id, {"name": req.name})
    await db.commit()
    return KnowledgeBaseOut.from_model(kb)


@router.delete("/{kb_id}", status_code=204)
async def delete_kb(kb_id: uuid.UUID, principal: AdminPrincipal, db: Db) -> None:
    """删除本租户自有知识库；要求库内无未删除文档（先删文档再删库）。"""
    kb = await KnowledgeBaseRepo(db, principal.tenant_id).get_own(kb_id)
    if kb is None:
        raise HTTPException(404, "知识库不存在或无权限")
    doc_count = await db.scalar(
        select(func.count(Document.id)).where(
            Document.kb_id == kb_id, Document.deleted_at.is_(None)
        )
    )
    if doc_count:
        raise HTTPException(409, f"知识库内还有 {doc_count} 个文档，请先删除文档")
    await db.delete(kb)
    audit.record(db, principal, "kb.delete", "knowledge_base", kb_id)
    await db.commit()
