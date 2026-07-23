"""业务表模型。

多租户约定：
- 除 tenants 外，所有表带 tenant_id，复合索引以 tenant_id 为前缀
- 应用层 repository 强制过滤 + PostgreSQL RLS 兜底（策略见 alembic 迁移）
- knowledge_bases/documents/chunks 带 is_public：平台公共政策库对所有租户可读
- documents 软删除（deleted_at），业务记录留痕；向量与 MinIO 文件真删
"""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from rag_core.db.base import Base, TimestampMixin, UUIDPkMixin

# --- 字段取值约定（应用层校验，DB 层 check 兜底） ---
TENANT_STATUSES = ("active", "suspended")
USER_ROLES = ("admin", "member")
DOCUMENT_STATUSES = ("uploaded", "parsing", "chunking", "embedding", "ready", "failed")
MESSAGE_ROLES = ("user", "assistant", "system")


class Tenant(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "tenants"
    __table_args__ = (CheckConstraint(f"status IN {TENANT_STATUSES}", name="ck_tenant_status"),)

    name: Mapped[str] = mapped_column(String(128))
    slug: Mapped[str] = mapped_column(String(64), unique=True)
    status: Mapped[str] = mapped_column(String(16), default="active")
    quota_max_documents: Mapped[int] = mapped_column(default=1000)
    quota_max_storage_mb: Mapped[int] = mapped_column(default=2048)
    quota_daily_requests: Mapped[int] = mapped_column(default=10000)


class User(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="uq_user_tenant_email"),
        CheckConstraint(f"role IN {USER_ROLES}", name="ck_user_role"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    email: Mapped[str] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(String(128))
    display_name: Mapped[str] = mapped_column(String(64), default="")
    role: Mapped[str] = mapped_column(String(16), default="member")
    is_active: Mapped[bool] = mapped_column(default=True)


class ApiKey(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "api_keys"

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    key_hash: Mapped[str] = mapped_column(String(128), unique=True)
    name: Mapped[str] = mapped_column(String(64))
    scopes: Mapped[list] = mapped_column(JSONB, default=list)  # 如 ["retrieval", "chat"]
    expires_at: Mapped[datetime | None] = mapped_column(default=None)
    revoked_at: Mapped[datetime | None] = mapped_column(default=None)
    last_used_at: Mapped[datetime | None] = mapped_column(default=None)


class KnowledgeBase(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_bases"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_kb_tenant_name"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text, default="")
    is_public: Mapped[bool] = mapped_column(default=False, index=True)
    embed_model: Mapped[str] = mapped_column(String(64), default="BAAI/bge-m3")
    config: Mapped[dict] = mapped_column(JSONB, default=dict)


class Document(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint(f"status IN {DOCUMENT_STATUSES}", name="ck_document_status"),
        Index("ix_documents_tenant_kb_status", "tenant_id", "kb_id", "status"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    kb_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("knowledge_bases.id"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    minio_path: Mapped[str] = mapped_column(String(512))
    content_type: Mapped[str] = mapped_column(String(128), default="")
    size_bytes: Mapped[int] = mapped_column(default=0)
    status: Mapped[str] = mapped_column(String(16), default="uploaded")
    error_msg: Mapped[str] = mapped_column(Text, default="")
    # 财税元数据
    doc_number: Mapped[str] = mapped_column(String(128), default="")  # 文号
    effective_date: Mapped[date | None] = mapped_column(Date, default=None)
    expire_date: Mapped[date | None] = mapped_column(Date, default=None)
    source: Mapped[str] = mapped_column(String(128), default="")  # 来源机关
    # 公共库冗余标记（与所属 kb.is_public 一致，便于 RLS 与向量过滤）
    is_public: Mapped[bool] = mapped_column(default=False, index=True)
    # 软删除
    deleted_at: Mapped[datetime | None] = mapped_column(default=None)
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, default=None)


class Chunk(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "chunks"
    __table_args__ = (Index("ix_chunks_tenant_doc", "tenant_id", "doc_id"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    kb_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("knowledge_bases.id"), index=True)
    doc_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"), index=True)
    seq: Mapped[int] = mapped_column()
    content: Mapped[str] = mapped_column(Text)
    qdrant_point_id: Mapped[uuid.UUID] = mapped_column(Uuid, unique=True)
    token_count: Mapped[int] = mapped_column(default=0)
    is_public: Mapped[bool] = mapped_column(default=False, index=True)


class Conversation(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "conversations"

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), default=None)
    api_key_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("api_keys.id"), default=None)
    title: Mapped[str] = mapped_column(String(255), default="")


class Message(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint(f"role IN {MESSAGE_ROLES}", name="ck_message_role"),
        Index("ix_messages_tenant_conversation", "tenant_id", "conversation_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversations.id"), index=True)
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    citations: Mapped[list] = mapped_column(JSONB, default=list)


class AuditLog(UUIDPkMixin, Base):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_tenant_created", "tenant_id", "created_at"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    actor_type: Mapped[str] = mapped_column(String(16))  # user / api_key / system
    actor_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, default=None)
    action: Mapped[str] = mapped_column(String(64))  # 如 document.upload / kb.delete
    resource_type: Mapped[str] = mapped_column(String(32), default="")
    resource_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, default=None)
    detail: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
