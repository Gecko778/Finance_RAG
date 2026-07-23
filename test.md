# 测试记录（test.md）

> 倒序追加：最新记录在最上面。所有测试均为真实执行，附命令与实际输出。

---

## 2026-07-23 · M1 数据库

| # | 测试项 | 执行命令 | 预期 | 实际 | 结论 |
|---|---|---|---|---|---|
| 1 | Lint | `uv run ruff check .` | 0 错误 | 首轮 21 处（多为 import 排序，11 处自动修复；生成的迁移文件行宽加 per-file 豁免；repos.py 1 处手工换行）→ 0 错误 | ✅（修复后） |
| 2 | 迁移可重放 | pytest `test_migration_replayable`（独立测试库 upgrade→downgrade→upgrade） | 全程无错 | 通过 | ✅ |
| 3 | repo 层隔离 + 公共库 | pytest `test_repo_isolation_and_public_kb` | 租户 B 可见自有库+公共库，不可见 A 私有库，公共库不可改写 | 通过 | ✅ |
| 4 | RLS 兜底 | pytest `test_rls_blocks_cross_tenant_without_app_filter`（绕过 repo 裸 SQL） | 数据库层拦截跨租户行 | 通过 | ✅ |
| 5 | RLS 默认拒绝 | pytest `test_rls_default_deny` | 无租户上下文时私有行不可见、users 表全不可见 | **首轮失败**（断言写错，见下）→ 修正后通过 | ✅（修复后） |
| 6 | 软删除 | pytest `test_document_soft_delete` | 删除后列表不可见，重复删除返回 False | 通过 | ✅ |
| 7 | 全套回归 | `uv run pytest -q` | 全部通过 | `6 passed` | ✅ |
| 8 | 开发库迁移 | `uv run alembic upgrade head` | 迁移成功 | `Running upgrade -> 11fb1533c938` | ✅ |
| 9 | 种子 + 幂等 | `uv run python scripts/seed.py`（连跑两次） | 首次创建、二次跳过 | 首次输出 tenant id + admin；二次输出"已存在，跳过" | ✅ |
| 10 | 种子数据核验 | psql 查 tenants/users/knowledge_bases | 平台租户 + admin + 公共库/私有库 | slug=platform、admin@finance-rag.local(admin)、公共库 is_public=t | ✅ |
| 11 | Qdrant 初始化 | `uv run python scripts/init_qdrant.py` + REST 核验 | 1024 维 cosine + 5 个 payload 索引 | `size:1024 Cosine`，索引 doc_id/expire_date/is_public/kb_id/tenant_id 全部就绪 | ✅ |

**过程中发现并修复的问题**：
1. **测试断言错误（#5 首轮失败）**：断言"无上下文时 count==0"，实际返回 3。经 psql 逐层排查（pg_policies 表达式、角色属性、GUC 状态）确认 **RLS 工作正常**——可见的 3 行全部是 is_public 公共行，本就该可见。修正断言为"私有行 0 + users 表 0"后通过。此排查同时实证了策略表达式和角色配置的正确性
2. 测试相对导入报错（tests 目录非包）→ 改为顶层导入 conftest
3. 生成的迁移文件 E501 行宽 → per-file 豁免（不手改自动生成代码）

**M1 验收结论**：迁移可重放 ✅、种子可查 ✅、跨租户强制过滤双层验证 ✅。全部达成。


| # | 测试项 | 执行命令 | 预期 | 实际 | 结论 |
|---|---|---|---|---|---|
| 1 | 依赖安装 | `uv sync --all-packages` | 全部 workspace 成员 + dev 组安装成功 | 安装成功（fastapi/uvicorn/pydantic-settings/pytest/ruff 等） | ✅ |
| 2 | Lint | `uv run ruff check .` | 0 错误 | 首跑报 1 个 import 排序（I001），`--fix` 修复后 0 错误 | ✅（修复后） |
| 3 | 单元测试 | `uv run pytest -q` | test_healthz 通过 | `1 passed, 1 warning in 0.61s`（warning 为 starlette testclient 弃用提示，无碍） | ✅ |
| 4 | 基础设施启动 | `docker compose up -d` + `docker compose ps` | 4 容器全部 healthy | postgres / redis / qdrant / minio 均 `Up (healthy)` | ✅ |
| 5 | API 端到端 | `uv run uvicorn rag_api.main:app` + `curl http://localhost:8000/healthz` | 返回 `{"status":"ok"}` | 返回 `{"status":"ok"}` | ✅ |
| 6 | 配置加载 | `python -c "from rag_core.settings import get_settings; ..."` | Settings 正常实例化并读取默认值 | 输出 `settings ok: http://localhost:6333 BAAI/bge-m3` | ✅ |

**过程中遇到并解决的问题**：
1. uv 未安装 → brew 安装因 ghcr.io SSL 失败 → 改用 astral.sh 官方脚本安装成功（uv 0.11.31）
2. Docker daemon 未运行 → `open -a Docker` 启动 Docker Desktop 后恢复
3. ruff I001 import 排序 → `ruff check --fix` 自动修复

**M0 验收结论**：全部验收标准达成（compose 四服务 healthy；/healthz 返回 ok）。✅
