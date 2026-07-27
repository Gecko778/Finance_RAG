"""内测反馈：用户对问答评价（好评/差评+备注）；管理员查看用于 badcase 收集。"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from rag_core.db.models import FEEDBACK_RATINGS, Feedback
from sqlalchemy import select

from rag_api.auth import AdminPrincipal, UserPrincipal
from rag_api.deps import Db

router = APIRouter(prefix="/api/v1/feedback", tags=["feedback"])


class FeedbackRequest(BaseModel):
    query: str = Field(min_length=1)
    answer: str = ""
    rating: str = Field(pattern="^(up|down)$")
    comment: str = ""


class FeedbackOut(BaseModel):
    id: uuid.UUID
    query: str
    answer: str
    rating: str
    comment: str
    created_at: datetime


@router.post("", status_code=201)
async def submit_feedback(req: FeedbackRequest, principal: UserPrincipal, db: Db) -> FeedbackOut:
    fb = Feedback(
        tenant_id=principal.tenant_id, created_by=principal.actor_id,
        query=req.query, answer=req.answer, rating=req.rating, comment=req.comment,
    )
    db.add(fb)
    await db.flush()
    await db.commit()
    return FeedbackOut(
        id=fb.id, query=fb.query, answer=fb.answer, rating=fb.rating,
        comment=fb.comment, created_at=fb.created_at,
    )


@router.get("")
async def list_feedback(
    principal: AdminPrincipal,
    db: Db,
    rating: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[FeedbackOut]:
    stmt = select(Feedback).where(Feedback.tenant_id == principal.tenant_id)
    if rating in FEEDBACK_RATINGS:
        stmt = stmt.where(Feedback.rating == rating)
    stmt = stmt.order_by(Feedback.created_at.desc()).limit(limit)
    rows = (await db.scalars(stmt)).all()
    return [
        FeedbackOut(
            id=r.id, query=r.query, answer=r.answer, rating=r.rating,
            comment=r.comment, created_at=r.created_at,
        )
        for r in rows
    ]
