"""检索与问答 API：/retrieval（纯检索，小智兼容）、/chat（RAG 生成，SSE 流式）。"""

import json
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from rag_core.db.models import Conversation, Message
from rag_core.db.session import tenant_session

from rag_api.deps import Db, TenantId
from rag_api.llm import stream_answer
from rag_api.prompts import build_system_prompt
from rag_api.services import retrieval as svc

router = APIRouter(prefix="/api/v1", tags=["retrieval"])


class RetrieveRequest(BaseModel):
    query: str = Field(min_length=1)
    kb_ids: list[uuid.UUID] | None = None
    top_k: int = Field(default=5, ge=1, le=20)
    include_expired: bool = False


class ResultItem(BaseModel):
    content: str
    score: float
    citation: dict


class RetrieveResponse(BaseModel):
    results: list[ResultItem]


@router.post("/retrieval")
async def retrieve(req: RetrieveRequest, tenant_id: TenantId, db: Db) -> RetrieveResponse:
    """纯检索：返回带出处的相关片段（供小智等外部系统调用）。"""
    results, docs = await svc.search(
        db, tenant_id, req.query, req.kb_ids, req.top_k, req.include_expired
    )
    return RetrieveResponse(
        results=[
            ResultItem(content=r.content, score=r.score, citation=r.citation(docs[r.doc_id]))
            for r in results
        ]
    )


class ChatRequest(BaseModel):
    query: str = Field(min_length=1)
    kb_ids: list[uuid.UUID] | None = None
    conversation_id: uuid.UUID | None = None
    top_k: int = Field(default=5, ge=1, le=20)
    include_expired: bool = False


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _persist(
    tenant_id: uuid.UUID,
    conversation_id: uuid.UUID | None,
    query: str,
    answer: str,
    citations: list[dict],
) -> None:
    """流式结束后另开会话持久化对话（请求作用域会话此时已关闭）。"""
    async with tenant_session(tenant_id) as session:
        if conversation_id is None:
            conv = Conversation(tenant_id=tenant_id, title=query[:50])
            session.add(conv)
            await session.flush()
            conversation_id = conv.id
        session.add(Message(tenant_id=tenant_id, conversation_id=conversation_id, role="user",
                            content=query, citations=[]))
        session.add(Message(tenant_id=tenant_id, conversation_id=conversation_id, role="assistant",
                            content=answer, citations=citations))


@router.post("/chat")
async def chat(req: ChatRequest, tenant_id: TenantId, db: Db) -> StreamingResponse:
    """RAG 问答：检索 → 生成带出处的回答，SSE 流式。

    事件序：citations（引用列表）→ 多个 token（增量文本）→ done。
    """
    results, docs = await svc.search(
        db, tenant_id, req.query, req.kb_ids, req.top_k, req.include_expired
    )
    contexts = [
        f"来源：{docs[r.doc_id].filename}"
        + (f"（{docs[r.doc_id].doc_number}）" if docs[r.doc_id].doc_number else "")
        + f"\n{r.content}"
        for r in results
    ]
    citations = [r.citation(docs[r.doc_id]) for r in results]
    system = build_system_prompt(contexts)

    async def generate() -> AsyncIterator[str]:
        yield _sse("citations", {"citations": citations})
        parts: list[str] = []
        async for token in stream_answer(system, req.query):
            parts.append(token)
            yield _sse("token", {"text": token})
        await _persist(tenant_id, req.conversation_id, req.query, "".join(parts), citations)
        yield _sse("done", {})

    return StreamingResponse(generate(), media_type="text/event-stream")
