"""M4 集成验证（对真实 Postgres/Redis，不触外部模型 API）：登录 + API Key + 认证/授权。

用法：先起 API（uv run uvicorn rag_api.main:app --port 8000），再
     uv run python scripts/m4_integration_check.py
依赖：docker compose 基础设施 + 已执行种子（admin@finance-rag.local / admin123）。
"""

import sys
import uuid

import httpx
import jwt
from rag_api.auth import issue_jwt

BASE = "http://localhost:8000"
c = httpx.Client(base_url=BASE, timeout=30)
PASS, FAIL = [], []


def check(name: str, cond: bool, detail: str = ""):
    (PASS if cond else FAIL).append(name)
    print(f"{'PASS' if cond else 'FAIL'}  {name}{'  ' + detail if detail else ''}")


# 1. 登录：错误凭据 → 401
r = c.post("/api/v1/auth/login", json={
    "tenant_slug": "platform", "email": "admin@finance-rag.local", "password": "wrong"})
check("错误密码登录被拒(401)", r.status_code == 401, f"got {r.status_code}")

# 2. 登录：正确凭据 → 200 + token
r = c.post("/api/v1/auth/login", json={
    "tenant_slug": "platform", "email": "admin@finance-rag.local", "password": "admin123"})
check("正确凭据登录(200)+返回token", r.status_code == 200 and "access_token" in r.json(),
      f"got {r.status_code}")
if r.status_code != 200:
    print("登录失败，后续用例跳过")
    sys.exit(1)
token = r.json()["access_token"]
check("登录角色为 admin", r.json().get("role") == "admin")
auth = {"Authorization": f"Bearer {token}"}

# 3. 无认证访问受保护端点 → 401
check("无认证访问 /apikeys 被拒(401)", c.get("/api/v1/apikeys").status_code == 401)

# 4. 管理员创建 API Key → 201 + 明文仅此一次
r = c.post("/api/v1/apikeys", headers=auth, json={"name": "小智机器人", "scopes": ["retrieval"]})
check("管理员创建 API Key(201)", r.status_code == 201, f"got {r.status_code}")
plaintext = r.json().get("api_key", "")
key_id = r.json().get("id")
check("返回明文 API Key(fr_前缀)", plaintext.startswith("fr_"))

# 5. 列表可见且不含明文/哈希
listed = c.get("/api/v1/apikeys", headers=auth).json()
check("列表可见新建 key 且不含明文/哈希", any(k["id"] == key_id for k in listed)
      and all("api_key" not in k and "key_hash" not in k for k in listed))

# 6. 无效 scope → 422
r = c.post("/api/v1/apikeys", headers=auth, json={"name": "x", "scopes": ["bogus"]})
check("无效 scope 被拒(422)", r.status_code == 422, f"got {r.status_code}")

api_headers = {"X-API-Key": plaintext}

# 7. retrieval-scope key 调 /chat(需 chat) → 403（触及 LLM 前）
r = c.post("/api/v1/chat", headers=api_headers, json={"query": "测试"})
check("retrieval-key 调 /chat 被拒(403)", r.status_code == 403, f"got {r.status_code}")

# 8. API Key 调文档管理（需用户）→ 403
r = c.get(f"/api/v1/kbs/{key_id}/documents", headers=api_headers)
check("API Key 调文档管理被拒(403)", r.status_code == 403, f"got {r.status_code}")

# 9. 吊销 key → 204，随后使用 → 401
check("吊销 API Key(204)", c.delete(f"/api/v1/apikeys/{key_id}", headers=auth).status_code == 204)
r = c.post("/api/v1/retrieval", headers=api_headers, json={"query": "测试"})
check("已吊销 key 使用被拒(401)", r.status_code == 401, f"got {r.status_code}")

# 10. 非管理员令牌无法管理 API Key（伪造同租户 member token）
tid = jwt.decode(token, options={"verify_signature": False})["tid"]
member_token = issue_jwt(uuid.UUID(tid), uuid.uuid4(), "member")
r = c.post("/api/v1/apikeys", headers={"Authorization": f"Bearer {member_token}"},
           json={"name": "x", "scopes": ["retrieval"]})
check("member 令牌管理 API Key 被拒(403)", r.status_code == 403, f"got {r.status_code}")

# 11. 跨租户隔离：伪造他租户 token 访问 → 本租户数据不可见（RLS）
other_token = issue_jwt(uuid.uuid4(), uuid.uuid4(), "admin")
r = c.get("/api/v1/apikeys", headers={"Authorization": f"Bearer {other_token}"})
check("他租户令牌读 API Key 列表为空(RLS隔离)", r.status_code == 200 and r.json() == [],
      f"got {r.status_code} {r.text[:60]}")

print(f"\n结果：{len(PASS)} 通过 / {len(FAIL)} 失败")
sys.exit(1 if FAIL else 0)
