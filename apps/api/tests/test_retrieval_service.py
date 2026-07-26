"""检索服务纯逻辑单测：时效/可见性过滤 + 引用组装（无网络、无 DB）。"""

import uuid
from datetime import date

from rag_api.services.retrieval import DocMeta, RetrievalResult, filter_candidates
from rag_core.vectors import Candidate

TODAY = date(2026, 7, 26)


def _cand(doc_id: uuid.UUID, seq: int = 0) -> Candidate:
    return Candidate(content=f"内容{seq}", doc_id=doc_id, seq=seq, dense_score=0.9)


def _doc(expire: date | None = None, deleted: bool = False) -> DocMeta:
    return DocMeta(
        filename="政策.pdf", doc_number="财税〔2026〕1号", effective_date=date(2026, 1, 1),
        expire_date=expire, source="财政部", deleted=deleted,
    )


def test_expired_policy_dropped_by_default():
    d = uuid.uuid4()
    cands = [_cand(d)]
    docs = {d: _doc(expire=date(2026, 1, 1))}  # 已失效
    assert filter_candidates(cands, docs, include_expired=False, today=TODAY) == []


def test_expired_kept_when_include_expired():
    d = uuid.uuid4()
    cands = [_cand(d)]
    docs = {d: _doc(expire=date(2026, 1, 1))}
    assert len(filter_candidates(cands, docs, include_expired=True, today=TODAY)) == 1


def test_null_expire_always_kept():
    d = uuid.uuid4()
    assert len(filter_candidates([_cand(d)], {d: _doc(expire=None)}, False, TODAY)) == 1


def test_future_expire_kept():
    d = uuid.uuid4()
    docs = {d: _doc(expire=date(2027, 12, 31))}
    assert len(filter_candidates([_cand(d)], docs, False, TODAY)) == 1


def test_deleted_doc_dropped():
    d = uuid.uuid4()
    assert filter_candidates([_cand(d)], {d: _doc(deleted=True)}, True, TODAY) == []


def test_missing_doc_dropped():
    # 候选的 doc 未在可见文档集中（跨租户/不可见）→ 剔除
    assert filter_candidates([_cand(uuid.uuid4())], {}, True, TODAY) == []


def test_citation_shape():
    d = uuid.uuid4()
    r = RetrievalResult(content="第一条 ...", doc_id=d, seq=3, score=0.87)
    cite = r.citation(_doc(expire=date(2027, 1, 1)))
    assert cite["doc_id"] == str(d)
    assert cite["doc_number"] == "财税〔2026〕1号"
    assert cite["seq"] == 3
    assert cite["expire_date"] == "2027-01-01"
    assert cite["source"] == "财政部"
