"""文档摄取 API：上传、进度查询、删除。"""

import uuid
from datetime import date

from fastapi import APIRouter, Form, HTTPException, UploadFile
from pydantic import BaseModel
from rag_core.db.models import Chunk, Document
from rag_core.db.repos import DocumentRepo, KnowledgeBaseRepo
from rag_core.storage import delete_object, upload_bytes
from rag_core.vectors import delete_by_doc
from sqlalchemy import delete as sa_delete

from rag_api.deps import Db, Queue, TenantId

router = APIRouter(prefix="/api/v1", tags=["documents"])

ALLOWED_SUFFIXES = {".pdf", ".docx", ".txt", ".md"}
MAX_SIZE = 50 * 1024 * 1024  # 50MB


class DocumentOut(BaseModel):
    id: uuid.UUID
    filename: str
    status: str
    error_msg: str
    doc_number: str
    effective_date: date | None
    expire_date: date | None
    source: str

    @classmethod
    def from_model(cls, d: Document) -> "DocumentOut":
        return cls(
            id=d.id,
            filename=d.filename,
            status=d.status,
            error_msg=d.error_msg,
            doc_number=d.doc_number,
            effective_date=d.effective_date,
            expire_date=d.expire_date,
            source=d.source,
        )


@router.post("/kbs/{kb_id}/documents", status_code=201)
async def upload_document(
    kb_id: uuid.UUID,
    file: UploadFile,
    tenant_id: TenantId,
    db: Db,
    queue: Queue,
    doc_number: str = Form(""),
    effective_date: date | None = Form(None),
    expire_date: date | None = Form(None),
    source: str = Form(""),
) -> DocumentOut:
    kb = await KnowledgeBaseRepo(db, tenant_id).get_own(kb_id)
    if kb is None:
        raise HTTPException(404, "知识库不存在或无权限")

    filename = file.filename or "unnamed"
    suffix = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if suffix not in ALLOWED_SUFFIXES:
        allowed = ", ".join(sorted(ALLOWED_SUFFIXES))
        raise HTTPException(422, f"不支持的格式 {suffix}，支持：{allowed}")
    data = await file.read()
    if len(data) > MAX_SIZE:
        raise HTTPException(413, "文件超过 50MB 限制")

    doc = await DocumentRepo(db, tenant_id).create(
        kb,
        filename=filename,
        minio_path="",  # 先占位，拿到 doc.id 后写入
        content_type=file.content_type or "",
        size_bytes=len(data),
        doc_number=doc_number,
        effective_date=effective_date,
        expire_date=expire_date,
        source=source,
    )
    doc.minio_path = f"{tenant_id}/{doc.id}/{filename}"
    upload_bytes(doc.minio_path, data, doc.content_type)

    await queue.enqueue_job("ingest_document", str(tenant_id), str(doc.id))
    return DocumentOut.from_model(doc)


@router.get("/kbs/{kb_id}/documents")
async def list_documents(kb_id: uuid.UUID, tenant_id: TenantId, db: Db) -> list[DocumentOut]:
    docs = await DocumentRepo(db, tenant_id).list_in_kb(kb_id)
    return [DocumentOut.from_model(d) for d in docs]


@router.get("/documents/{doc_id}")
async def get_document(doc_id: uuid.UUID, tenant_id: TenantId, db: Db) -> DocumentOut:
    doc = await db.get(Document, doc_id)
    if doc is None or doc.deleted_at is not None or doc.tenant_id != tenant_id:
        raise HTTPException(404, "文档不存在")
    return DocumentOut.from_model(doc)


@router.delete("/documents/{doc_id}", status_code=204)
async def delete_document(doc_id: uuid.UUID, tenant_id: TenantId, db: Db) -> None:
    """软删除业务记录；级联真删 chunks 行、Qdrant 向量、MinIO 文件。"""
    repo = DocumentRepo(db, tenant_id)
    doc = await db.get(Document, doc_id)
    if doc is None or doc.deleted_at is not None or doc.tenant_id != tenant_id:
        raise HTTPException(404, "文档不存在")
    minio_path = doc.minio_path

    await repo.soft_delete(doc_id)
    await db.execute(sa_delete(Chunk).where(Chunk.doc_id == doc_id))
    await delete_by_doc(doc_id)
    if minio_path:
        delete_object(minio_path)
