"""SiliconFlow 向量化客户端（OpenAI 兼容 /embeddings），批量 + 重试。"""

import asyncio

import httpx

from rag_core.settings import get_settings

BATCH_SIZE = 32
MAX_RETRIES = 3


class EmbeddingError(RuntimeError):
    pass


async def _embed_batch(client: httpx.AsyncClient, texts: list[str]) -> list[list[float]]:
    s = get_settings()
    for attempt in range(1, MAX_RETRIES + 1):
        resp = await client.post(
            f"{s.siliconflow_base_url}/embeddings",
            headers={"Authorization": f"Bearer {s.siliconflow_api_key}"},
            json={"model": s.embedding_model, "input": texts},
            timeout=60,
        )
        if resp.status_code == 200:
            data = sorted(resp.json()["data"], key=lambda d: d["index"])
            return [d["embedding"] for d in data]
        if resp.status_code in (429, 500, 502, 503) and attempt < MAX_RETRIES:
            await asyncio.sleep(2**attempt)
            continue
        raise EmbeddingError(f"embedding 失败 HTTP {resp.status_code}: {resp.text[:200]}")
    raise EmbeddingError("embedding 重试耗尽")  # pragma: no cover


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """批量向量化，保持输入顺序。"""
    if not get_settings().siliconflow_api_key:
        raise EmbeddingError("SILICONFLOW_API_KEY 未配置")
    vectors: list[list[float]] = []
    async with httpx.AsyncClient() as client:
        for i in range(0, len(texts), BATCH_SIZE):
            vectors.extend(await _embed_batch(client, texts[i : i + BATCH_SIZE]))
    return vectors
