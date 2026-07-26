"""API Key 管理（仅管理员）：创建（明文仅显示一次）、列表、吊销。"""

import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from rag_core.db.models import ApiKey
from rag_core.security import generate_api_key
from sqlalchemy import select

from rag_api.auth import AdminPrincipal
from rag_api.deps import Db
from rag_api.services import audit

router = APIRouter(prefix="/api/v1/apikeys", tags=["apikeys"])

VALID_SCOPES = {"retrieval", "chat"}


class CreateApiKeyRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    scopes: list[str] = Field(default_factory=lambda: ["retrieval"])


class ApiKeyOut(BaseModel):
    id: uuid.UUID
    name: str
    scopes: list[str]
    created_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None


class CreateApiKeyResponse(BaseModel):
    id: uuid.UUID
    name: str
    scopes: list[str]
    api_key: str  # 明文，仅此一次返回


@router.post("", status_code=201)
async def create_api_key(
    req: CreateApiKeyRequest, principal: AdminPrincipal, db: Db
) -> CreateApiKeyResponse:
    invalid = set(req.scopes) - VALID_SCOPES
    if invalid:
        raise HTTPException(422, f"无效的 scope：{invalid}，可选：{VALID_SCOPES}")
    plaintext, key_hash = generate_api_key()
    row = ApiKey(
        tenant_id=principal.tenant_id, key_hash=key_hash, name=req.name, scopes=req.scopes
    )
    db.add(row)
    await db.flush()
    audit.record(db, principal, "apikey.create", "api_key", row.id, {"name": req.name})
    await db.commit()
    return CreateApiKeyResponse(id=row.id, name=row.name, scopes=row.scopes, api_key=plaintext)


@router.get("")
async def list_api_keys(principal: AdminPrincipal, db: Db) -> list[ApiKeyOut]:
    rows = (await db.scalars(select(ApiKey).where(ApiKey.tenant_id == principal.tenant_id))).all()
    return [
        ApiKeyOut(
            id=r.id, name=r.name, scopes=r.scopes, created_at=r.created_at,
            last_used_at=r.last_used_at, revoked_at=r.revoked_at,
        )
        for r in rows
    ]


@router.delete("/{key_id}", status_code=204)
async def revoke_api_key(key_id: uuid.UUID, principal: AdminPrincipal, db: Db) -> None:
    row = await db.get(ApiKey, key_id)
    if row is None or row.tenant_id != principal.tenant_id:
        raise HTTPException(404, "API Key 不存在")
    if row.revoked_at is None:
        row.revoked_at = datetime.now()
        audit.record(db, principal, "apikey.revoke", "api_key", key_id)
        await db.commit()  # 吊销须在返回前落库，杜绝"吊销后立即复用"竞态
