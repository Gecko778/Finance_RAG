# 进展记录（progress.md）

> 倒序追加：最新记录在最上面。每次代码生成完成后写一条。详细测试见 test.md。

---

## 2026-07-23 · M1 数据库 ✅

**设计决策（用户确认后冻结）**：公共政策库 v1 就建（is_public 标记）；应用层过滤 + PG RLS 双保险；文档软删除；角色两级 admin/member。

**本次生成的文件/模块**：

| 文件 | 作用 |
|---|---|
| `packages/core/src/rag_core/db/base.py` | 声明基类 + UUID 主键 / 时间戳 mixin |
| `packages/core/src/rag_core/db/models.py` | 9 张表：tenants / users / api_keys / knowledge_bases / documents / chunks / conversations / messages / audit_logs。documents 带财税元数据（文号/生效/失效/来源）+ 软删除；kb/documents/chunks 带 is_public |
| `packages/core/src/rag_core/db/session.py` | 引擎/会话工厂 + `tenant_session()`（事务内 set_config 注入租户上下文，RLS 前提） |
| `packages/core/src/rag_core/db/repos.py` | KnowledgeBaseRepo / DocumentRepo：应用层强制 tenant_id 过滤（第一道防线），公共库合并可见、仅归属租户可写 |
| `alembic/` + `versions/11fb1533c938_initial_schema.py` | 初始迁移：9 表全量 DDL + 创建非超级用户角色 finance_rag_app + 8 张业务表启用 RLS（tenant_all 策略 + 公共三表 public_read 策略） |
| `scripts/seed.py` | 幂等种子：平台租户 + admin 用户（bcrypt）+ 公共政策库 + 私有 SOP 库 |
| `scripts/init_qdrant.py` | 幂等创建 chunks collection（1024 维 cosine）+ 5 个 payload 索引（tenant_id/kb_id/doc_id/is_public/expire_date） |
| `packages/core/tests/` | 6 项集成测试（真实 PG）：迁移可重放、repo 隔离、RLS 裸查拦截、默认拒绝、软删除 |

**关键设计决策**：
- 双数据库角色：应用连非超级用户 `finance_rag_app`（受 RLS 约束），迁移/种子用 compose 超级用户——避免"超级用户绕过 RLS 导致防线形同虚设"的坑
- RLS 默认拒绝：未注入 app.tenant_id 时私有行全部不可见；公共行（is_public）按设计对所有租户只读
- tenants 表不启用 RLS（注册流程需在无租户上下文时访问，且无跨租户敏感字段）

---

## 2026-07-22 · M0 项目初始化 ✅

**本次生成的文件/模块**：

| 文件 | 作用 |
|---|---|
| `pyproject.toml` | uv workspace 根：成员 apps/* + packages/*，dev 依赖（ruff/pytest/pytest-asyncio/httpx），ruff + pytest 配置 |
| `packages/core/`（rag-core 包） | 共享核心包骨架；`src/rag_core/settings.py` 用 pydantic-settings 集中管理全部配置（PG/Redis/Qdrant/MinIO/SiliconFlow/LiteLLM），`get_settings()` 带 lru_cache |
| `apps/api/`（rag-api 包） | FastAPI 服务骨架；`src/rag_api/main.py` 提供 `GET /healthz`；`tests/test_healthz.py` 单测 |
| `apps/worker/`（rag-worker 包） | 摄取 worker 占位包（arq 依赖按计划 M2 才引入，避免提前引入未用依赖） |
| `docker-compose.yml` | PostgreSQL 16 / Redis 7 / Qdrant / MinIO 四服务，均带 healthcheck 与数据卷 |
| `.env.example` | 全量配置模板，键与 settings.py 一一对应 |
| `.gitignore` / `README.md` | 常规忽略项（.env 不入库、uv.lock 入库）；README 写明本地启动五步 |

**关键设计决策**：
- monorepo 用 uv workspace 虚拟根（根目录不是包，只做 workspace + dev 工具声明）
- 各子包 hatchling 构建 + src 布局；apps 通过 `[tool.uv.sources] workspace = true` 依赖 rag-core
- worker 在 M0 只占位不引入 arq——不写用不到的依赖和代码
- Qdrant healthcheck 用 `/dev/tcp` 探测（镜像内无 curl）

**环境事项**（本机首次搭建）：
- 安装了 uv 0.11.31（brew 因 ghcr.io 网络失败，改用 astral.sh 官方脚本，装于 `~/.local/bin`）
- 远程仓库 Gecko778/Finance_RAG 已有 GitHub 初始 commit（仅 README），已 pull 合并后在其上重写 README
