"""arq 摄取 worker。

任务：ingest_document(tenant_id, doc_id)
流程：parsing → chunking → embedding → ready；失败回写 status=failed + error_msg
（临时性故障由 embeddings HTTP 层重试覆盖，任务级不重试，重新上传即重跑）。
重跑幂等：写入前清理该文档旧数据。

启动：uv run arq rag_worker.main.WorkerSettings
"""

import uuid

from arq.connections import RedisSettings
from rag_core.db.models import Chunk, Document
from rag_core.db.session import tenant_session
from rag_core.ingestion.chunking import chunk_text
from rag_core.ingestion.embeddings import embed_texts
from rag_core.settings import get_settings
from rag_core.storage import download_bytes
from rag_core.vectors import ChunkPoint, delete_by_doc, upsert_chunks
from sqlalchemy import delete

from rag_worker.parsers import parse_bytes


async def _set_status(tenant_id: uuid.UUID, doc_id: uuid.UUID, status: str, error: str = ""):
    async with tenant_session(tenant_id) as session:
        doc = await session.get(Document, doc_id)
        doc.status = status
        doc.error_msg = error


async def ingest_document(ctx: dict, tenant_id_s: str, doc_id_s: str) -> str:
    tenant_id, doc_id = uuid.UUID(tenant_id_s), uuid.UUID(doc_id_s)
    try:
        # 1. 读取文档记录与原始文件
        async with tenant_session(tenant_id) as session:
            doc = await session.get(Document, doc_id)
            if doc is None or doc.deleted_at is not None:
                return "skipped: 文档不存在或已删除"
            doc.status = "parsing"
            filename, minio_path = doc.filename, doc.minio_path
            kb_id, is_public = doc.kb_id, doc.is_public
            doc_title = filename.rsplit(".", 1)[0]
            doc_number = doc.doc_number
            expire = doc.expire_date.isoformat() if doc.expire_date else None

        text = parse_bytes(filename, download_bytes(minio_path))

        # 2. 切块
        await _set_status(tenant_id, doc_id, "chunking")
        chunks = chunk_text(text, doc_title=doc_title, doc_number=doc_number)

        # 3. 向量化 + 写入（幂等：先清理旧数据）
        await _set_status(tenant_id, doc_id, "embedding")
        vectors = await embed_texts([c.content for c in chunks])

        await delete_by_doc(doc_id)
        points = [
            ChunkPoint(
                point_id=uuid.uuid4(),
                vector=vec,
                content=c.content,
                tenant_id=tenant_id,
                kb_id=kb_id,
                doc_id=doc_id,
                seq=c.seq,
                is_public=is_public,
                expire_date=expire,
            )
            for c, vec in zip(chunks, vectors, strict=True)
        ]
        await upsert_chunks(points)

        async with tenant_session(tenant_id) as session:
            await session.execute(delete(Chunk).where(Chunk.doc_id == doc_id))
            session.add_all(
                Chunk(
                    tenant_id=tenant_id,
                    kb_id=kb_id,
                    doc_id=doc_id,
                    seq=p.seq,
                    content=p.content,
                    qdrant_point_id=p.point_id,
                    token_count=int(len(p.content) / 1.6),
                    is_public=is_public,
                )
                for p in points
            )
            doc = await session.get(Document, doc_id)
            doc.status = "ready"
            doc.error_msg = ""
        return f"ready: {len(points)} chunks"

    except Exception as exc:
        # 任务级不重试：临时性故障已由 embeddings 的 HTTP 层重试覆盖；
        # 解析类错误重试无意义。任何异常直接回写 failed，重新上传即重跑。
        await _set_status(tenant_id, doc_id, "failed", error=str(exc)[:2000])
        raise


class WorkerSettings:
    functions = [ingest_document]
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    job_timeout = 600
