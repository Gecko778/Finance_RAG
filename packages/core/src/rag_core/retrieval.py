"""检索候选：问题向量化 + Qdrant 稠密检索（时效过滤/重排在 API 服务层完成）。"""

import uuid

from rag_core.ingestion.embeddings import embed_texts
from rag_core.vectors import Candidate, search_chunks


async def retrieve_candidates(
    query: str,
    tenant_id: uuid.UUID,
    kb_ids: list[uuid.UUID] | None = None,
    fetch_k: int = 30,
) -> list[Candidate]:
    query_vector = (await embed_texts([query]))[0]
    return await search_chunks(query_vector, tenant_id, kb_ids, fetch_k)
