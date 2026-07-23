"""Qdrant 向量库读写（collection 由 scripts/init_qdrant.py 创建）。"""

import uuid
from dataclasses import dataclass
from functools import lru_cache

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue, PointStruct

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
