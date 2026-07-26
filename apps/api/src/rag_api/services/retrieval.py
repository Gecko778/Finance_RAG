"""检索服务：候选 → 时效/可见性过滤（Postgres 权威日期）→ rerank → 引用组装。

流程：
1. core.retrieve_candidates：问题向量化 + Qdrant 稠密检索（可见性过滤，over-fetch）
2. 按 doc_id 批量载入 Document（本租户+公共、未软删）→ 剔除失效政策（除非 include_expired）
3. core.rerank：对存活候选按相关度重排，取 top_k
4. 组装带出处的结果（文件名/文号/条款序号/日期/来源）
"""

import uuid
from dataclasses import dataclass
from datetime import date

from rag_core.db.models import Document
from rag_core.rerank import rerank
from rag_core.retrieval import retrieve_candidates
from rag_core.vectors import Candidate
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class DocMeta:
    filename: str
    doc_number: str
    effective_date: date | None
    expire_date: date | None
    source: str
    deleted: bool


@dataclass
class RetrievalResult:
    content: str
    doc_id: uuid.UUID
    seq: int
    score: float  # rerank 相关度

    def citation(self, doc: DocMeta) -> dict:
        return {
            "doc_id": str(self.doc_id),
            "filename": doc.filename,
            "doc_number": doc.doc_number,
            "seq": self.seq,
            "effective_date": doc.effective_date.isoformat() if doc.effective_date else None,
            "expire_date": doc.expire_date.isoformat() if doc.expire_date else None,
            "source": doc.source,
        }


def filter_candidates(
    candidates: list[Candidate],
    docs: dict[uuid.UUID, DocMeta],
    include_expired: bool,
    today: date,
) -> list[Candidate]:
    """剔除文档不可见/已软删、以及失效政策（expire_date < today，除非 include_expired）。

    纯函数，可单测。
    """
    kept: list[Candidate] = []
    for c in candidates:
        doc = docs.get(c.doc_id)
        if doc is None or doc.deleted:
            continue
        if not include_expired and doc.expire_date is not None and doc.expire_date < today:
            continue
        kept.append(c)
    return kept


async def _load_docs(
    db: AsyncSession, tenant_id: uuid.UUID, doc_ids: set[uuid.UUID]
) -> dict[uuid.UUID, DocMeta]:
    if not doc_ids:
        return {}
    stmt = select(Document).where(
        Document.id.in_(doc_ids),
        or_(Document.tenant_id == tenant_id, Document.is_public.is_(True)),
    )
    out: dict[uuid.UUID, DocMeta] = {}
    for d in (await db.scalars(stmt)).all():
        out[d.id] = DocMeta(
            filename=d.filename,
            doc_number=d.doc_number,
            effective_date=d.effective_date,
            expire_date=d.expire_date,
            source=d.source,
            deleted=d.deleted_at is not None,
        )
    return out


async def search(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    query: str,
    kb_ids: list[uuid.UUID] | None = None,
    top_k: int = 5,
    include_expired: bool = False,
) -> tuple[list[RetrievalResult], dict[uuid.UUID, DocMeta]]:
    """返回 (结果列表, doc_id→DocMeta)；结果已按 rerank 相关度降序取 top_k。"""
    fetch_k = max(top_k * 3, 20)
    candidates = await retrieve_candidates(query, tenant_id, kb_ids, fetch_k=fetch_k)
    docs = await _load_docs(db, tenant_id, {c.doc_id for c in candidates})
    survivors = filter_candidates(candidates, docs, include_expired, date.today())
    if not survivors:
        return [], docs

    order = await rerank(query, [c.content for c in survivors])
    results = [
        RetrievalResult(
            content=survivors[idx].content,
            doc_id=survivors[idx].doc_id,
            seq=survivors[idx].seq,
            score=score,
        )
        for idx, score in order[:top_k]
    ]
    return results, docs
