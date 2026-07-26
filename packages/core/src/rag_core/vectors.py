"""Qdrant 向量库读写（collection 由 scripts/init_qdrant.py 创建）。"""

import uuid
from dataclasses import dataclass
from functools import lru_cache

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    FieldCondition,
    Filter,
    MatchAny,
    MatchValue,
    PointStruct,
)

from rag_core.settings import get_settings

COLLECTION = "chunks"


@lru_cache
def get_qdrant() -> AsyncQdrantClient:
    s = get_settings()
    return AsyncQdrantClient(url=s.qdrant_url, api_key=s.qdrant_api_key)


@dataclass
class ChunkPoint:
    point_id: uuid.UUID
    vector: list[float]
    content: str
    tenant_id: uuid.UUID
    kb_id: uuid.UUID
    doc_id: uuid.UUID
    seq: int
    is_public: bool
    expire_date: str | None  # ISO 日期，None 表示长期有效


async def upsert_chunks(points: list[ChunkPoint]) -> None:
    await get_qdrant().upsert(
        collection_name=COLLECTION,
        points=[
            PointStruct(
                id=str(p.point_id),
                vector=p.vector,
                payload={
                    "content": p.content,
                    "tenant_id": str(p.tenant_id),
                    "kb_id": str(p.kb_id),
                    "doc_id": str(p.doc_id),
                    "seq": p.seq,
                    "is_public": p.is_public,
                    "expire_date": p.expire_date,
                },
            )
            for p in points
        ],
    )


async def delete_by_doc(doc_id: uuid.UUID) -> None:
    await get_qdrant().delete(
        collection_name=COLLECTION,
        points_selector=Filter(
            must=[FieldCondition(key="doc_id", match=MatchValue(value=str(doc_id)))]
        ),
    )


async def count_by_doc(doc_id: uuid.UUID) -> int:
    result = await get_qdrant().count(
        collection_name=COLLECTION,
        count_filter=Filter(
            must=[FieldCondition(key="doc_id", match=MatchValue(value=str(doc_id)))]
        ),
    )
    return result.count


@dataclass
class Candidate:
    content: str
    doc_id: uuid.UUID
    seq: int
    dense_score: float


def _visibility_filter(tenant_id: uuid.UUID, kb_ids: list[uuid.UUID] | None) -> Filter:
    """可见性：本租户 chunk 或公共库 chunk；可选限定知识库。

    时效性（expire_date）过滤放在检索后由 Postgres 权威日期处理，
    Qdrant 只做已建索引的 tenant_id/kb_id/is_public 过滤。
    """
    must: list = []
    if kb_ids:
        must.append(FieldCondition(key="kb_id", match=MatchAny(any=[str(k) for k in kb_ids])))
    return Filter(
        must=must or None,
        should=[
            FieldCondition(key="tenant_id", match=MatchValue(value=str(tenant_id))),
            FieldCondition(key="is_public", match=MatchValue(value=True)),
        ],
    )


async def search_chunks(
    query_vector: list[float],
    tenant_id: uuid.UUID,
    kb_ids: list[uuid.UUID] | None = None,
    fetch_k: int = 30,
) -> list[Candidate]:
    """稠密检索，返回候选（供检索后做时效过滤 + rerank）。"""
    resp = await get_qdrant().query_points(
        collection_name=COLLECTION,
        query=query_vector,
        query_filter=_visibility_filter(tenant_id, kb_ids),
        limit=fetch_k,
        with_payload=True,
    )
    return [
        Candidate(
            content=p.payload["content"],
            doc_id=uuid.UUID(p.payload["doc_id"]),
            seq=p.payload["seq"],
            dense_score=p.score,
        )
        for p in resp.points
    ]
