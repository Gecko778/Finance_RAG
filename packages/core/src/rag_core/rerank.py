"""SiliconFlow 重排（bge-reranker-v2-m3），对候选按与 query 的相关度重排。"""

import asyncio

import httpx

from rag_core.settings import get_settings

MAX_RETRIES = 3


class RerankError(RuntimeError):
    pass


async def rerank(query: str, documents: list[str]) -> list[tuple[int, float]]:
    """返回 [(原始下标, 相关度分), ...]，按分数降序。documents 为空时返回空。"""
    if not documents:
        return []
    s = get_settings()
    if not s.siliconflow_api_key:
        raise RerankError("SILICONFLOW_API_KEY 未配置")

    payload = {"model": s.rerank_model, "query": query, "documents": documents}
    async with httpx.AsyncClient() as client:
        for attempt in range(1, MAX_RETRIES + 1):
            resp = await client.post(
                f"{s.siliconflow_base_url}/rerank",
                headers={"Authorization": f"Bearer {s.siliconflow_api_key}"},
                json=payload,
                timeout=60,
            )
            if resp.status_code == 200:
                results = resp.json()["results"]
                pairs = [(r["index"], r["relevance_score"]) for r in results]
                return sorted(pairs, key=lambda x: x[1], reverse=True)
            if resp.status_code in (429, 500, 502, 503) and attempt < MAX_RETRIES:
                await asyncio.sleep(2**attempt)
                continue
            raise RerankError(f"rerank 失败 HTTP {resp.status_code}: {resp.text[:200]}")
    raise RerankError("rerank 重试耗尽")  # pragma: no cover
