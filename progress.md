# 进展记录（progress.md）

> 倒序追加：最新记录在最上面。每次代码生成完成后写一条。详细测试见 test.md。

---

## 2026-07-27 · M8 部署基础设施：api/worker 容器化 ✅（M8 其余=产品决策，待沟通）

**说明**：M8 SaaS 化整体是产品决策（计费/交付形态/自助开通/K8s 架构），plan 标注"另行详细规划"。本次只做**决策无关、任何部署都需要**的一块——api/worker 容器化（前端 M5 已有 Dockerfile）。

**本次生成的文件**：

| 文件 | 作用 |
|---|---|
| `apps/api/Dockerfile` | python:3.13-slim + uv，构建上下文=仓库根，`uv sync --package rag-api`，CMD uvicorn |
| `apps/worker/Dockerfile` | 同上，`uv sync --package rag-worker`，CMD arq |

**关键点**：
- uv 改用 `pip install uv`（ghcr.io/astral-sh/uv 在本环境拉取不稳定，短读 EOF；pip 更稳）
- 分层复制（先 pyproject 后源码）利用构建缓存
- 三份镜像（api/worker/web）齐备，为 M8 K8s 编排就位

**M8 待沟通的产品/架构决策**（不臆想）：K8s 部署架构（有状态服务 PG/Qdrant/MinIO/Redis 是集群内 StatefulSet 还是托管）、租户自助开通流程、用量计费模型、交付形态（多租户共享 vs 私有化包）、数据合规文档。

**本次生成的文件**（放本仓库 `integrations/xiaozhi/`，不改动机器人独立仓库）：

| 文件 | 作用 |
|---|---|
| `integrations/xiaozhi/search_from_finance_rag.py` | 小智 function-call 插件：`@register_function` + POST `/api/v1/retrieval`（X-API-Key）+ `Action.REQLLM`；把 results 组织成带 `[序号] 来源` 的引用文本 |
| `integrations/xiaozhi/README.md` | 安装步骤 + config.yaml 配置片段 + 端到端联调说明 |
| `integrations/xiaozhi/test_plugin.py` | build_context 纯逻辑单测（stub 机器人依赖后导入真实插件文件） |

**关键点（与 search_from_ragflow 的适配差异）**：
- 响应结构按本项目形态 `{results:[{content,score,citation}]}` 解析（非 RAGFlow 的 `{code,data.chunks}`）
- 认证用 `X-API-Key` 头（本项目 API Key 走此头；Bearer 会被当 JWT 解析失败——已实测印证）
- 401/403/网络异常返回友好话术，不中断语音对话
- 插件放本仓库版本化交付，安装=复制到机器人 functions 目录 + 配 config.yaml（不 commit 进机器人仓库）

**契约验证（不依赖 key）**：用插件确切请求形态打真实 /retrieval——retrieval-key+payload 越过认证/scope/校验直达 embedding（500，仅因 key），缺 query 422，Bearer+apikey 401。证明插件契约正确，key 就绪即可用。

**待 key+机器人**：语音问答端到端（需 SiliconFlow key + 灌库 + 小智 server 按 README 配置启动）。

**说明**：M6 本质是"财税人员真实问答内测 + RAGAS 评分"，真人测试与跑分依赖 key + 测试人员，属自然汇合点。本次交付**不依赖 key 的基础设施**。

**本次生成的文件**：

| 文件 | 作用 |
|---|---|
| `rag_core/db/models.py`（+Feedback） | 反馈模型：rating(up/down)+query/answer/comment，租户隔离 |
| `alembic/versions/a1b2c3d4e5f6_add_feedback.py`（新） | feedback 表迁移：新表授权 finance_rag_app + RLS 租户策略（可 down/up 回放） |
| `rag_api/routes/feedback.py`（新） | POST 提交（用户，rating 正则校验）/ GET 查看（管理员，rating 过滤） |
| `scripts/eval/dataset.yaml`（新） | 评测集 8 例：factual3/cross_article2/refusal2/freshness1，基于 testdata 真实政策 |
| `scripts/eval/run_eval.py`（新） | 评测运行器：跑 dataset 过 /retrieval 轻量判分（引用命中+要点召回+拒答），导出明细 |
| `apps/web/src/views/ChatView.vue`（改） | 回答区加"有帮助/不准确"反馈按钮 → POST /feedback |

**关键点**：
- feedback 为新增表（不改 M1 冻结的核心表），迁移中单独 GRANT + RLS，已验证 down/up 回放
- 评测运行器不引第三方评测库，先用"引用命中+要点召回"给可离线复核的基线；RAGAS 升级位已注明
- **待 key/测试人员**：run_eval.py 真实跑分（需检索可用=key+灌库）、财税人员真人内测、RAGAS 指标、前端反馈按钮 E2E（需真实回答可评）

**本次生成的文件**：

| 文件 | 作用 |
|---|---|
| `rag_api/routes/members.py`（新） | 成员管理（仅管理员）：列表/创建（bcrypt 密码、邮箱租户内唯一 409）/启用停用（禁停用自己） |
| `rag_api/routes/audit_log.py`（新） | 审计日志查询（仅管理员）：时间倒序、可按 action 过滤、limit 1-200 |
| `rag_api/main.py`（+2 路由） | 注册 members / audit |
| `apps/web/src/views/MembersView.vue`（新） | 成员表格 + 新建对话框 + 启用/停用切换 |
| `apps/web/src/views/ApiKeysView.vue`（新） | API Key 表格 + 新建（明文一次性绿条展示）+ 吊销 |
| `apps/web/src/views/AuditView.vue`（新） | 审计日志只读表格 + action 过滤 |
| `apps/web/src/router/index.ts`、`layouts/MainLayout.vue`（改） | 加 /members /apikeys /audit 路由；侧栏管理员三项（isAdmin 条件渲染） |

**关键点**：
- 管理页仅管理员可见（前端 isAdmin 条件渲染 + 后端 AdminPrincipal 双重把关）
- API Key 创建明文仅一次性返回并在前端绿色提示条展示
- 停用成员即时生效（登录校验 is_active，实测停用后登录 401）

**设计决策（用户确认后冻结）**：范围=**核心操作台**（登录+知识库+文档+对话测试），成员/API Key/审计管理页归 M5.5；测试=**构建 + 浏览器渲染验证**（对话问答 E2E 与 M2/M3 一起等 key）。

**后端补齐（前端所需，此前缺失）**：
| 文件 | 作用 |
|---|---|
| `rag_api/routes/kbs.py`（新） | 知识库 GET 列表（本租户+公共）/POST 创建（同名 409）/DELETE 删除（管理员、非空 409、审计） |
| `rag_api/routes/auth.py`（+/me） | GET /auth/me 校验令牌返回身份（前端刷新恢复会话） |
| `rag_api/main.py`（+CORS） | CORSMiddleware 放行 Vite dev（localhost:5173）；注册 kbs 路由 |
| `rag_core/settings.py`（+cors_origins） | 前端跨域来源配置 |
| `pyproject.toml`（+exclude apps/web） | uv workspace 排除 Node 前端目录 |

**前端（apps/web，Vue 3 + Element Plus + Vite + TS + Pinia + Vue Router）**：
| 文件 | 作用 |
|---|---|
| `package.json`/`vite.config.ts`/`tsconfig.json`/`index.html`/`env.d.ts` | 工程配置 |
| `src/main.ts`/`App.vue` | 入口，挂载 ElementPlus/Pinia/Router |
| `src/api/client.ts` | axios 实例：请求注入 JWT、401 自动跳登录；localStorage 存 token |
| `src/stores/auth.ts` | Pinia 认证 store：login/fetchMe/logout |
| `src/router/index.ts` | 路由 + 守卫（未登录跳 /login） |
| `src/layouts/MainLayout.vue` | 顶栏（角色/退出）+ 侧栏导航 |
| `src/views/LoginView.vue` | 登录（租户 slug+邮箱+密码） |
| `src/views/KnowledgeBasesView.vue` | 知识库列表/新建/删除；公共库无删除按钮（RBAC UI） |
| `src/views/DocumentsView.vue` | 文档列表（状态标签+失败 tooltip）、上传（财税元数据表单）、删除、处理中轮询刷新 |
| `src/views/ChatView.vue` | 对话：知识库多选、SSE 流式（fetch 解析 event/data）、引用出处卡片、人工复核提示 |
| `Dockerfile`/`nginx.conf` | 多阶段构建 + nginx 托管（SPA 回退 + /api 反代，SSE 关缓冲）；供 M8 K8s |

**关键点**：
- SSE 用 fetch + ReadableStream 解析（EventSource 不支持 POST+Header）
- 上传用原生 fetch 传 multipart（带 JWT）；文档处理中每 3s 轮询状态
- uv workspace `apps/*` 会误吞 Node 前端，已 exclude
- npm peer-dep 冲突（vite/plugin-vue 解析顺序）用 `--legacy-peer-deps` 解开

**设计决策（用户确认后冻结）**：登录用 **租户标识(slug) + email + 密码**，不改 User 表结构（保留租户内 email 唯一）。

**本次生成/改造的文件**：

| 文件 | 作用 |
|---|---|
| `rag_core/security.py`（新） | 密码 bcrypt 哈希/校验；API Key 生成（fr_ 前缀）+ sha256 哈希 |
| `rag_core/settings.py`（+认证段） | jwt_secret / jwt_expire_minutes / api_key_prefix |
| `rag_core/db/session.py`（+admin_session、set_tenant） | 超级用户会话（登录前跨租户查找）；提取 set_tenant 供请求会话复用 |
| `rag_api/auth.py`（新） | 双通道认证→统一 Principal：JWT（Authorization: Bearer）/ API Key（X-API-Key）；is_admin/has_scope；require_admin/require_user/require_scope 守卫 |
| `rag_api/deps.py`（重写） | get_db 由 Principal 派生租户上下文（弃用 X-Tenant-Id）；**写操作显式提交模型**（见下） |
| `rag_api/routes/auth.py`（新） | POST /auth/login：验证→签发 JWT，审计 auth.login |
| `rag_api/routes/apikeys.py`（新） | API Key CRUD（仅管理员）：创建（明文仅返回一次）/列表（不含明文哈希）/吊销 |
| `rag_api/services/audit.py`（新） | 审计日志 helper，登录/上传/删除/建吊销 key 均留痕 |
| `rag_api/services/quota.py`（新） | 文档数+存储量配额（Postgres 实时统计，413）；日调用次数（Redis 计数，429） |
| `rag_api/routes/documents.py`、`retrieval.py`（改造） | 用 Principal 替换 X-Tenant-Id；文档管理限用户；检索需 retrieval scope、问答需 chat scope；上传接配额、检索/问答接日配额；写操作审计 |
| `scripts/m4_integration_check.py`（新） | 对真实 PG/Redis 的认证/授权集成验证脚本 |

**关键设计决策与修正**：
- **API Key 哈希用 sha256**（高熵随机串，无需慢哈希且每请求校验要快）；密码用 bcrypt（慢哈希抗爆破）
- 登录跨租户查找用 admin_session（绕 RLS 的受控场景）；管理操作走租户会话（RLS 生效）
- **修复真实读写竞态（靠 httpx 背靠背请求发现）**：原 `get_db` 在 `session.begin()` 里，提交发生在响应送达之后，导致"吊销 API Key 后立即复用"能在提交落库前的毫秒窗口内溜过（500 而非 401）。根因修复：**写路由在返回前显式 `await db.commit()`**（吊销/建 key/上传/删除），get_db 保留兜底提交/回滚。**顺带修掉 M2 隐患**：上传后 `enqueue` 改到提交之后，杜绝 worker 读到未提交文档。
- API Key 只用于检索/问答（scopes: retrieval/chat）；文档管理限用户令牌（require_user）

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
