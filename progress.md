# 进展记录（progress.md）

> 倒序追加：最新记录在最上面。每次代码生成完成后写一条。详细测试见 test.md。

---

## 2026-07-26 · M3 检索与生成 API ⏳（代码完成，端到端问答待有效 SiliconFlow + DeepSeek key 后补验）

**设计决策（用户确认后冻结）**：检索策略 v1 = **稠密检索 + bge-reranker 重排 + 时效过滤**；关键词/混合检索延后到 M3.5（避免现在给 Postgres 加中文分词扩展或引入稀疏向量）。这是对 plan 原「混合检索」任务的有意收缩，已与用户确认。

**本次生成的文件/模块**：

| 文件 | 作用 |
|---|---|
| `packages/core/src/rag_core/vectors.py`（+search_chunks） | Qdrant 稠密检索：可见性过滤（本租户 OR 公共库，可选限定 kb）+ over-fetch 候选。**时效过滤刻意不放 Qdrant**，改由检索后用 Postgres 权威日期处理（避免 Qdrant 存日期字符串无法范围过滤的坑，也不改 M2 payload） |
| `packages/core/src/rag_core/rerank.py` | SiliconFlow bge-reranker-v2-m3 重排客户端（429/5xx 退避重试） |
| `packages/core/src/rag_core/retrieval.py` | 候选检索编排：问题向量化 + 稠密检索（纯逻辑，无 DB） |
| `apps/api/src/rag_api/prompts.py` | 财税系统提示词：只依据检索资料、[序号]标注出处、不足则明说未找到、金额税率逐字引用、结尾提示人工复核 |
| `apps/api/src/rag_api/llm.py` | LiteLLM 流式生成（默认 deepseek-chat，预留切本地） |
| `apps/api/src/rag_api/services/retrieval.py` | 检索服务：候选→载入 Document 元数据→**时效/可见性过滤（filter_candidates 纯函数）**→rerank 取 top_k→引用组装 |
| `apps/api/src/rag_api/routes/retrieval.py` | `/api/v1/retrieval`（纯检索，小智兼容）+ `/api/v1/chat`（SSE 流式：citations 事件→token 增量→done；结束后另开会话持久化对话+引用） |
| `apps/api/tests/test_retrieval_service.py`、`test_prompts.py` | 9 项纯逻辑单测 |

**关键设计决策**：
- 时效过滤下沉到检索后 + Postgres 日期：M2 的 Qdrant payload 未改（surgical），失效政策用权威 DB 日期剔除，`include_expired` 可放开
- 检索原语在 core（可复用），LLM/prompt/编排在 api（litellm 不进 core/worker，保持 core 轻量）
- SSE 对话持久化在流式生成器内**另开** tenant_session（请求作用域会话此时已关闭）
- 跨租户/软删文档在 filter_candidates 二次兜底剔除（防御式）

**设计决策（用户确认后冻结）**：SiliconFlow Key 用户稍后填 .env；测试文档用户提供（放 `testdata/`）；解析器精简为 pypdf+python-docx（放弃 unstructured，表格差时走既定 MinerU 评估）。

**本次生成的文件/模块**：

| 文件 | 作用 |
|---|---|
| `packages/core/src/rag_core/storage.py` | MinIO 存取删（bucket 自动创建） |
| `packages/core/src/rag_core/vectors.py` | Qdrant 异步读写：upsert_chunks / delete_by_doc / count_by_doc |
| `packages/core/src/rag_core/ingestion/chunking.py` | 切块策略：政策按「第X条」条款切（≥3 条触发），超长条款段落细分；普通文档段落聚合 800 字符 + 120 字符重叠；块头注入【文号 标题】 |
| `packages/core/src/rag_core/ingestion/embeddings.py` | SiliconFlow 批量向量化（批 32，429/5xx 指数退避重试 3 次） |
| `apps/worker/src/rag_worker/parsers.py` | PDF/DOCX/TXT/MD 解析（docx 含表格行；txt gbk 回退；空结果显式报错提示扫描件） |
| `apps/worker/src/rag_worker/main.py` | arq 任务 ingest_document：状态机 parsing→chunking→embedding→ready，失败回写 failed+error_msg，重跑幂等（先清旧数据） |
| `apps/api/src/rag_api/deps.py` | 租户头（X-Tenant-Id，M4 前临时方案）、租户会话、arq 队列依赖 |
| `apps/api/src/rag_api/routes/documents.py` | 上传（multipart+财税元数据表单，格式/大小校验）、列表/单条进度查询、删除（软删记录+真删 chunks/Qdrant/MinIO） |
| `packages/core/tests/test_chunking.py`、`apps/worker/tests/test_parsers.py` | 10 项单元测试 |

**关键设计决策与修正**：
- **修正了一个真实 bug（靠真实测试发现）**：原以为 arq 对异常自动重试 3 次，实测 arq 仅在显式抛 `Retry` 时重试——导致失败状态永远不回写、文档卡死。修正为任务级不重试（HTTP 层已有重试覆盖临时故障），任何异常直接回写 failed。**此前声明的"arq 重试 3 次"假设作废**
- embedding 客户端放 core（M3 检索查询向量化复用）；解析器放 worker（唯一使用方）
- 未配置 API Key 时显式报错"SILICONFLOW_API_KEY 未配置"，不静默跳过

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
