"""认证纯逻辑单测：JWT 往返、Principal 权限判定、守卫依赖（无 DB、无网络）。"""

import uuid

import pytest
from fastapi import HTTPException
from rag_api.auth import (
    Principal,
    _principal_from_jwt,
    issue_jwt,
    require_admin,
    require_scope,
    require_user,
)


def test_jwt_roundtrip():
    tid, uid = uuid.uuid4(), uuid.uuid4()
    token = issue_jwt(tid, uid, "admin")
    p = _principal_from_jwt(token)
    assert p.tenant_id == tid
    assert p.actor_id == uid
    assert p.actor_type == "user"
    assert p.role == "admin"


def test_jwt_invalid_raises_401():
    with pytest.raises(HTTPException) as exc:
        _principal_from_jwt("not.a.jwt")
    assert exc.value.status_code == 401


def _user(role="member"):
    return Principal(uuid.uuid4(), "user", uuid.uuid4(), role=role)


def _api_key(scopes):
    return Principal(uuid.uuid4(), "api_key", uuid.uuid4(), scopes=scopes)


def test_is_admin():
    assert _user("admin").is_admin
    assert not _user("member").is_admin
    assert not _api_key(["retrieval"]).is_admin  # api_key 永不是 admin


def test_has_scope_user_has_all():
    # 用户令牌拥有全部范围
    assert _user().has_scope("retrieval")
    assert _user().has_scope("chat")


def test_has_scope_api_key_limited():
    k = _api_key(["retrieval"])
    assert k.has_scope("retrieval")
    assert not k.has_scope("chat")


async def test_require_admin():
    assert (await require_admin(_user("admin"))).is_admin
    with pytest.raises(HTTPException) as exc:
        await require_admin(_user("member"))
    assert exc.value.status_code == 403


async def test_require_user_rejects_api_key():
    assert await require_user(_user()) is not None
    with pytest.raises(HTTPException) as exc:
        await require_user(_api_key(["retrieval"]))
    assert exc.value.status_code == 403


async def test_require_scope():
    dep = require_scope("chat")
    assert await dep(_user()) is not None  # 用户放行
    assert await dep(_api_key(["chat"])) is not None
    with pytest.raises(HTTPException) as exc:
        await dep(_api_key(["retrieval"]))
    assert exc.value.status_code == 403
