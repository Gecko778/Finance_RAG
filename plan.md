# 财税企业级 RAG 平台 — 开发计划（plan.md）

> 本计划由市场调研 + 技术选型决策产出，按 milestone 顺序执行。
> 执行约定：每个 milestone 开始前先对照本计划确认范围；**遇到任何不明确的需求必须与负责人沟通，不臆想需求**；每个 milestone 完成需通过验收标准后才进入下一个。

---

## 1. 项目概述

### 1.1 目标（三步走）

1. **内测阶段**：搭建企业级财税 RAG 平台，灌入财税法规、政策文件、内部 SOP 等知识，供本公司财税人员测试使用
2. **接入阶段**：以 API-first 方式对外提供检索/问答能力，接入其他项目（首个目标：`xiaoxin/xiaozhi-esp32-server` 小智语音机器人）
3. **SaaS 阶段**：打包为多租户服务，客户企业上传内部数据，获得定制化知识库问答能力

### 1.2 非目标（v1 明确不做）

- ❌ 金蝶等财务软件对接（结构化数据查询属 Agent 阶段，后续版本规划）
- ❌ 本地大模型部署（LiteLLM 抽象层已预留切换能力，待有硬件/合规需求时切换）
- ❌ 计费系统完整实现（M8 仅做计量钩子）
- ❌ 移动端

### 1.3 已定决策

| 决策项 | 结论 |
|---|---|
| 技术路线 | 纯自研（FastAPI + LangChain），不依赖 Dify/RAGFlow 平台（规避 Dify 多租户 SaaS 协议限制） |
| 代码基础 | 全新开始（`xiaoxin/rag-platform` 骨架仅作设计参考，不复用代码） |
| 向量库 | Qdrant，租户隔离用 payload 中 `tenant_id` 过滤 |
| 模型策略 | 云 API 先行：SiliconFlow（BGE-M3 + bge-reranker-v2-m3）+ LiteLLM（deepseek-chat / qwen 系） |
| 开发顺序 | 数据库 → 后端业务逻辑 → 前端 |

---

## 2. 技术栈清单

| 层 | 选型 | 说明 |
|---|---|---|
| 语言/框架 | Python 3.11+，FastAPI，uv 管理依赖 | monorepo：apps/api、apps/worker、packages/core |
| RAG 编排 | LangChain | 检索管线、混合检索、引用溯源 |
| 业务数据库 | PostgreSQL 16 + asyncpg + SQLAlchemy 2.0（async）+ Alembic | 所有业务表带 tenant_id |
| 向量数据库 | Qdrant | payload：tenant_id / kb_id / doc_id / doc_number / effective_date / expire_date |
| 队列/缓存 | Redis + arq | 摄取任务异步化 |
| 对象存储 | MinIO | 原始文档存储，S3 兼容 |
| 模型接入 | LiteLLM（LLM 抽象）；SiliconFlow API（embedding + rerank） | 环境变量切换供应商，预留本地化 |
| 文档解析 | pypdf / python-docx / unstructured | 财税表格 PDF 解析预留 MinerU 升级位 |
| 前端 | Vue 3 + Element Plus + Vite | 团队已有 Vue 经验（manager-web 为 Vue2） |
| 部署 | docker-compose（开发/内测）| 预留 K8s 化（参考 k8s-migration 笔记） |
| 评估 | RAGAS + 财税人工评测集 | 政策时效性为必测项 |

---

## 3. 系统架构

```
┌─────────────┐   ┌──────────────────┐   ┌─────────────────────┐
│ 前端管理台    │   │ 小智机器人插件      │   │ 客户系统 (SaaS 阶段)  │
│ (Vue3)      │   │ search_from_     │   │                     │
│             │   │ finance_rag.py   │   │                     │
└──────┬──────┘   └────────┬─────────┘   └──────────┬──────────┘
       │ JWT               │ API Key (Bearer)       │ API Key
       ▼                   ▼                        ▼
┌─────────────────────────────────────────────────────────────┐
│                  FastAPI (apps/api)                          │
│  认证中间件 → 租户上下文中间件 → 审计日志                        │
│  ├─ /api/v1/retrieval   纯检索（小智兼容，返回带出处的片段）      │
│  ├─ /api/v1/chat        RAG 问答（生成 + 引用溯源，SSE 流式）    │
│  └─ /api/v1/admin/*     租户/知识库/文档/用户管理                │
└───────┬──────────────────────────────┬──────────────────────┘
        │ 入库任务入队                    │ 检索
        ▼                              ▼
┌───────────────────┐    ┌─────────────────────────────────┐
│ 摄取 Worker        │    │ 检索管线 (packages/core)          │
│ (apps/worker, arq)│    │ 混合检索(稠密+关键词) → rerank →   │
│ 解析→切块→向量化    │    │ 时效性过滤(expire_date) → 组装     │
└───────┬───────────┘    └────────────┬────────────────────┘
        ▼                             ▼
┌──────────┐  ┌───────┐  ┌────────┐  ┌────────────────────┐
│PostgreSQL │  │ MinIO │  │ Qdrant │  │ LiteLLM/SiliconFlow │
│(业务数据)  │  │(原文件)│  │(向量)   │  │ (LLM/Embed/Rerank) │
└──────────┘  └───────┘  └────────┘  └────────────────────┘
```

**小智集成要点**：`/api/v1/retrieval` 的请求/响应形态对齐 `search_from_ragflow.py` 的调用方式（POST + Bearer 认证 + 返回文本片段列表），使插件改造成本最小。

---

## 4. 数据库设计要点（M1 详细展开）

核心表（均带 `tenant_id`，行级隔离；`created_at`/`updated_at` 齐备）：

| 表 | 关键字段 | 说明 |
|---|---|---|
| `tenants` | name, slug, status, quota_* | 租户（本公司为第一个租户） |
| `users` | tenant_id, email, password_hash, role | 角色：admin / member |
| `api_keys` | tenant_id, key_hash, name, scopes, expires_at | 供小智/客户系统调用 |
| `knowledge_bases` | tenant_id, name, description, embed_model, config | 一租户多知识库 |
| `documents` | tenant_id, kb_id, filename, minio_path, status, error_msg, **doc_number, effective_date, expire_date, source** | 状态机：uploaded→parsing→chunking→embedding→ready / failed；财税元数据为一等公民 |
| `chunks` | tenant_id, kb_id, doc_id, seq, content, qdrant_point_id, token_count | 与 Qdrant point 一一映射，便于溯源与重建索引 |
| `conversations` / `messages` | tenant_id, user_id/api_key_id, role, content, citations(jsonb) | 对话历史 + 引用记录 |
| `audit_logs` | tenant_id, actor, action, resource, detail(jsonb) | 财务合规要求：数据访问留痕 |

---

## 5. Milestones

### M0 项目初始化（0.5 周）

**目标**：可运行的空项目骨架 + 本地基础设施一键启动

**任务**：
- [x] uv workspace monorepo：`apps/api`、`apps/worker`、`packages/core`（schema/检索/模型客户端共享代码）
- [x] `docker-compose.yml`：PostgreSQL 16、Redis、Qdrant、MinIO（含健康检查、数据卷）
- [x] 配置管理：pydantic-settings + `.env.example`（数据库/Redis/Qdrant/MinIO/SiliconFlow/LiteLLM 全量配置项）
- [x] git init + `.gitignore` + 关联远程仓库 `https://github.com/Gecko778/Finance_RAG` + 首次提交推送；ruff + pytest 基础配置
- [x] 创建 `progress.md` 与 `test.md`（见第 7 节工作流约定）
- [x] README：本地启动步骤

**验收**：`docker compose up -d` 四个服务全部 healthy；`uv run` 能启动空的 FastAPI 应用返回 `/healthz` → **✅ 已通过（2026-07-22，详见 test.md）**

**风险**：无重大风险

---

### M1 数据库（1 周）

**目标**：完整多租户 schema 落地，迁移体系可用

**任务**：
- [x] SQLAlchemy 2.0 async 模型：第 4 节全部表
- [x] Alembic 迁移：初始迁移 + 迁移可重放验证
- [x] 多租户约束：外键 + 复合索引（tenant_id 前缀）+ 唯一约束（如 tenant 内 kb 名唯一）
- [x] 种子脚本：创建默认租户（本公司）+ admin 用户 + 示例知识库
- [x] Qdrant collection 初始化脚本（向量维度对齐 BGE-M3 = 1024，payload 索引：tenant_id/kb_id/expire_date）
- [x] 基础 CRUD repository 层 + 单元测试
- [x] （决策后追加）PG RLS 行级安全：非超级用户应用角色 + 8 表策略（默认拒绝 + 公共库只读）

**验收**：`alembic upgrade head` / `downgrade base` 可重放；种子数据可查；跨租户查询在 repository 层被 tenant_id 强制过滤（有测试覆盖）→ **✅ 已通过（2026-07-23，11 项测试详见 test.md）**

**已冻结决策**：公共政策库 v1 就建（is_public）；应用层+RLS 双保险；软删除；角色 admin/member

**风险**：schema 后期变更成本高 → 本 milestone 结束前与负责人过一遍字段清单再冻结

---

### M2 摄取管线（1.5 周）

**目标**：上传文档 → 自动解析切块向量化 → 可检索

**任务**：
- [x] 上传 API：多格式（PDF/DOCX/TXT/MD）→ MinIO，创建 document 记录（含财税元数据表单字段）
- [x] arq worker：解析（pypdf/python-docx，经用户确认精简掉 unstructured）→ 切块 → 向量化（SiliconFlow BGE-M3，批量+重试）→ 写入 Qdrant + chunks 表
- [x] 财税切块策略：政策法规按条款边界切块（正则识别"第 X 条"），普通文档按语义段落 + overlap；块内附加元数据头（文号/标题）
- [x] 状态机流转 + 失败回写（任务级不重试，HTTP 层重试覆盖临时故障——实测修正了 arq 重试假设）；文档删除时级联清理 Qdrant points/MinIO/chunks
- [x] 摄取进度查询 API
- [x] **ready 路径端到端验收**（2026-07-27，key 就绪后完成）：3 份真实政策全部 ready，Qdrant 140 向量，docx 表格解析端到端验证通过

**验收**：上传真实财税政策 PDF/DOCX → ready；Qdrant 可查向量；删除级联清理 → **✅ 全部通过（失败路径/MinIO/删除级联 + ready 路径 + 表格解析，见 test.md 端到端汇总）**

**风险**：**表格类财税 PDF 解析质量**是本项目最大技术风险 → 验收时用真实政策附表测试，若解析效果不足，触发 MinerU 升级评估（与负责人确认后再引入）

---

### M3 检索与生成 API（1.5 周）

**目标**：核心问答能力上线，引用可溯源

**任务**：
- [x] 检索管线（packages/core）：Qdrant 稠密检索 + bge-reranker-v2-m3 重排 → **时效性过滤（expire_date 早于当前日期的政策默认剔除，`include_expired` 放开）**。关键词/混合检索经用户确认收缩到 M3.5（避免现在加中文分词/稀疏向量组件）
- [x] `POST /api/v1/retrieval`：纯检索端点，返回带出处片段（供小智等调用；Bearer API Key 认证留待 M4）
- [x] `POST /api/v1/chat`：RAG 问答，LiteLLM 调用 LLM，SSE 流式输出；回答附引用（文件名+文号+条款序号）；财税 system prompt（仅依据检索内容、注明出处、不确定明说、提示人工复核）
- [x] 对话历史存储（conversations/messages + citations，流式结束后持久化）
- [x] 检索参数可配置（top_k、include_expired；score 阈值/rerank 开关留待按需加）
- [x] **问答端到端验收**（2026-07-27，key 就绪后完成）：/retrieval 带出处、/chat 流式正确作答+引用、库外拒答均验证

**验收**：问有依据的问题→回答正确且引用指向正确条款；问库外问题→明确"未找到依据"；失效政策默认不引用 → **✅ 全部通过（纯逻辑 6 项 + 端到端问答/拒答，见 test.md 端到端汇总）**

**风险**：幻觉与错引 → system prompt + 引用强制 + M6 评测集把关；检索质量不达标时调整切块/rerank 而非急于换模型

> 📌 **M3.5（延后项）**：关键词/混合检索。待 M3 稠密+rerank 基线质量在 M6 验证后，再决定是否加中文分词（Postgres zhparser）或稀疏向量。

---

### M4 多租户与权限（1 周）

**目标**：安全隔离达到可给第二个租户使用的水平

**任务**：
- [x] JWT 认证（前端用户）+ API Key 认证（机器调用）双通道 → 统一 Principal
- [x] 租户上下文：get_db 由 Principal 派生 tenant_id 注入 RLS（弃用 X-Tenant-Id）
- [x] RBAC：admin（API Key 管理等）vs member（上传/问答）；API Key 仅 retrieval/chat scope、文档管理限用户
- [x] 配额：文档数/存储量（Postgres 实时，413）/日调用次数（Redis，429）
- [x] 审计日志：登录、上传、删除、建/吊销 key 留痕（record helper）
- [x] API Key 管理 API：创建（明文仅显示一次）/列表（不含明文哈希）/吊销/scope

**验收**：租户 A 令牌访问租户 B 数据被 RLS 隔离；配额超限被拒；scope/角色越权 403；吊销后复用 401 → **✅ 已通过（2026-07-26）：单元 37 + 集成 14 全过（test.md）**

**风险**：无重大风险，属工程严谨性
> ⚠️ 修复中发现并解决一处读写竞态（写操作提交时机），顺带修掉 M2 上传-enqueue 抢跑隐患，详见 progress.md。

---

### M5 前端管理台（2 周）

**目标**：财税人员无需技术背景即可使用

**任务**（范围经用户确认=核心操作台；成员/API Key/审计管理页归 M5.5）：
- [x] Vue 3 + Element Plus + Vite 工程；登录/JWT 会话（Pinia + 路由守卫 + axios 拦截）
- [x] 知识库管理：列表/新建/删除（+补齐后端 KB 路由；公共库无删除按钮 RBAC UI）
- [x] 文档管理：上传（财税元数据表单：文号/生效/失效/来源）、状态展示（含失败原因 tooltip、处理中轮询）、删除
- [x] 对话测试页：SSE 流式回答、引用出处卡片、人工复核提示
- [x] docker-compose/部署：前端 Dockerfile + nginx（SPA 回退 + /api 反代 + SSE 关缓冲），供 M8 K8s
- [→] 管理页（成员/API Key/审计查看）：移至 **M5.5**（后端成员 CRUD/审计查询接口也需新建）
- [x] **对话问答 E2E**（2026-07-27）：浏览器实操 登录→提问→流式回答+表格引用+复核提示；反馈按钮→入库

**验收**：登录→建库→上传（表单）→提问→带出处回答 → **✅ 全部通过（浏览器端到端验证，见 test.md 端到端汇总）**

**风险**：无重大风险；UI 细节以内测反馈迭代为准
> 📌 **M5.5（延后）**：成员管理、API Key 管理页、审计日志查看（含对应后端接口）。

---

### M5.5 管理页（成员 / API Key / 审计）✅

**目标**：补齐 M5 延后的管理员功能，全部不依赖 key

**任务**：
- [x] 后端：成员管理路由（列表/创建/启用停用，禁停用自己）、审计日志查询路由（倒序+过滤）
- [x] 前端：成员管理页、API Key 管理页（明文一次性展示）、审计日志页；侧栏管理员条件渲染
- [x] 双重把关：前端 isAdmin 条件渲染 + 后端 AdminPrincipal

**验收**：管理员可增/停用成员、建/吊销 API Key、查审计链；停用成员即时无法登录 → **✅ 已通过（2026-07-27）：后端 6 项 + 前端 6 项实测（test.md）**

---

### M6 内测与评估（1 周 + 持续）

**目标**：质量基线量化，进入反馈迭代循环

**任务**：
- [x] 评测集构建：`scripts/eval/dataset.yaml`（8 例，含时效性/跨条款/拒答；基于 testdata 真实政策。可后续扩到 ≥50）
- [x] 评测运行器 `scripts/eval/run_eval.py`（引用命中+要点召回+拒答判分；RAGAS 升级位已注明）
- [x] 内测反馈渠道：feedback 表 + POST/GET 接口 + 前端"有帮助/不准确"按钮（前端→DB E2E 已验证）
- [x] 评测集跑通并出基线（2026-07-27）：/chat 级 run_eval，自动 5/8、人工核验 8/8 实质正确
- [ ] 组织财税人员真人内测 + LLM-judge 精确评分（**待测试人员**，非软件阻塞）

**验收**：评测集跑通并有基线报告；高频 badcase 有归因 → **✅ 基础设施+基线跑通（自动 5/8、人工 8/8 正确，eval_result.json）；真人内测待组织测试人员**

**风险**：财税人员时间投入 → 提前与负责人排期；**内测结论用于公司内部，任何对外输出需人工复核**（写入使用规范）

---

### M7 小智机器人集成（0.5 周）

**目标**：语音问财税问题，机器人从知识库取答案

**任务**：
- [x] 插件 `search_from_finance_rag.py`（放本仓库 `integrations/xiaozhi/`）：`@register_function` + POST `/api/v1/retrieval` + **X-API-Key**（非 Bearer，已实测印证）+ `Action.REQLLM`
- [x] 安装文档 README（config.yaml 配置片段 + Intent.function_call 加入说明）+ 纯逻辑单测
- [x] 插件↔平台 API 契约实测（认证头/请求形态/错误处理正确）
- [ ] 为小智创建 retrieval API Key + config 配置 + 语音联调（**待 key + 机器人环境**）

**验收**：对小智提财税问题，机器人基于知识库作答 → **⏳ 插件+契约就绪（2026-07-27，7 项通过）；语音端到端待 key+机器人（test.md #8）**

**风险**：语音场景回答需短 → retrieval 已支持 top_k 控制；如需更短可后续加精简模式参数

---

### M8 SaaS 化（后续，另行详细规划）

**目标**：可对外交付

**任务方向**：
- [x] 部署基础设施：api / worker 容器化（Dockerfile），配合前端 Dockerfile → 三镜像齐备（2026-07-27，已验证可构建可导入）
- [ ] 租户自助开通流程（注册→建租户→初始配额）— **待产品决策**
- [ ] 用量计量钩子（调用次数/token 消耗/存储，按租户聚合报表）— **待计费模型决策**
- [ ] 两种交付形态：多租户共享部署 / 独立部署包（届时评估本地模型切换）— **待决策**
- [ ] 数据合规文档：客户数据流向说明 — **待决策**
- [ ] K8s 编排（Deployment/Service/Ingress/Secret；有状态服务集群内 vs 托管）— **待架构决策**

**说明**：M8 整体在 plan 内即定为"另行详细规划"。除决策无关的容器化已完成外，其余均为产品/架构决策，需与负责人沟通后细化，不臆想。

---

## 6. 风险与约定（全程有效）

1. **政策时效性**：expire_date 过滤是硬性要求，失效政策被引用属 P0 bug
2. **表格解析质量**：财税 PDF 表格多，M2 验收必须用真实附表测试；不达标时评估 MinerU
3. **AI 结论人工复核**：任何面向客户的税务结论必须人工确认后输出——写入产品使用规范
4. **数据合规**：云 API 阶段向量化/生成会将文本发送至第三方 API；客户敏感数据接入前必须与负责人确认合规口径，必要时切本地模型（LiteLLM 已预留）
5. **沟通约定**：需求不明确、方案有分歧、验收有争议时，停下来沟通，不臆想
6. **排期**：M0–M7 合计约 8 周（单人全职估算），实际以每个 milestone 验收为准滚动调整

---

## 7. 开发工作流约定（每次代码生成必须执行）

每完成一次代码生成（一个功能/任务单元），按以下顺序闭环，**缺一不可**：

1. **写 progress.md**：在 `progress.md` 中追加一条记录（倒序，最新在上），包含：日期、所属 milestone、本次生成了哪些文件/模块、实现了什么功能、关键设计决策。让负责人能逐条看懂"每一步生成了什么代码、做了什么"
2. **真实测试并写 test.md**：对本次生成的功能进行实际测试（运行代码/单元测试/接口调用，**必须真实执行，严禁只看代码就宣称通过**）。测试过程与结果（含失败项和修复情况）明确记录到 `test.md`（倒序追加）：测试项、执行命令、预期结果、实际结果、结论（✅通过 / ❌失败+原因）
3. **汇总回 plan.md**：将本次工作的一句话总结 + 测试结论写入本文件第 8 节"进展与测试汇总"，并勾选对应 milestone 任务清单中已完成的任务项
4. **提交 GitHub**：`git add` → 规范化 commit message（`feat(M2): xxx` / `fix(M3): xxx`）→ push 到 `https://github.com/Gecko778/Finance_RAG`。测试不通过的代码不推送（先修复）

**部署约定**：内测期用 docker-compose；后期生产部署使用 **K8s**（M8 落地，所有服务从 M0 起保持容器化、配置外置，确保可平滑迁移）。

---

## 8. 进展与测试汇总

> 由第 7 节工作流自动维护：每次代码生成后追加一行。详细内容见 `progress.md` / `test.md`。

| 日期 | Milestone | 工作总结 | 测试结论 | Commit |
|---|---|---|---|---|
| 2026-07-27 | 🎯E2E | key 就绪后一次性关闭 M2/M3/M5/M6 端到端：上传→ready(140向量)→检索→DeepSeek 流式作答+表格引用→拒答→前端对话+反馈入库→评测基线 | 全链路真实跑通；评测自动 5/8·人工 8/8 正确；财税防幻觉/表格解析/引用溯源均验证 | chore(e2e) |
| 2026-07-27 | M8(部分) | 部署基础设施：api/worker Dockerfile（三镜像齐备）；M8 其余为产品/架构决策待沟通 | 4 通过（api/worker 镜像可构建+可导入） | feat(M8) |
| 2026-07-27 | M7 | 小智机器人集成插件 search_from_finance_rag.py（X-API-Key+/retrieval+REQLLM）+ 安装文档 + 纯逻辑单测 | 7 通过（build_context 单测 + 插件↔API 契约实测）；语音 E2E 待 key+机器人 | feat(M7) |
| 2026-07-27 | M6 | 评测基础设施+反馈渠道：评测集(8例)+运行器+feedback 表/接口/前端按钮 | 10 通过（迁移回放/反馈链路/评测集加载）；真跑分/真人内测待 key | feat(M6) |
| 2026-07-27 | M5.5 | 管理页：成员管理+API Key 管理+审计日志（后端路由+前端三页+管理员条件渲染） | 12 全过（后端 6：成员CRUD/停用即时生效/审计；前端 6：三页浏览器渲染+API Key 明文一次性展示） | feat(M5.5) |
| 2026-07-27 | M5 | 前端核心操作台（Vue3+Element Plus）：登录/知识库/文档上传/对话页 + 补齐 KB 后端路由+CORS+前端 Dockerfile | 15 项 14 通过（构建+浏览器渲染真实登录/数据/RBAC UI+后端接口）；问答 E2E 待 key | feat(M5) |
| 2026-07-26 | M4 | 多租户与权限：JWT+API Key 双认证、Principal、RBAC/scope、配额(文档/存储/日调用)、审计、API Key CRUD；修复吊销读写竞态 | 51 全过（单元 37 + 集成 14：登录/越权/RLS隔离/吊销复用/配额） | feat(M4) |
| 2026-07-26 | M3 | 检索与生成 API：稠密检索+rerank+时效过滤、/retrieval（小智兼容）、/chat（SSE 流式带引用）、财税提示词、对话持久化；关键词混合收缩到 M3.5 | 6/7 通过（25 单测 + 路由装配 + 请求校验；问答端到端待 key） | feat(M3) |
| 2026-07-23 | M2 | 摄取管线落地：上传 API（元数据表单+校验）、MinIO/Qdrant 客户端、条款切块策略、SiliconFlow 批量向量化、arq worker 状态机、删除级联清理 | 8/9 通过（单测 16、上传/MinIO/失败路径/删除级联实测；修复 arq 重试假设错误的真 bug）；ready 路径待 Key+真实文档补验 | feat(M2) |
| 2026-07-23 | M1 | 数据库落地：9 表 schema（财税元数据+软删除+公共库）、Alembic 迁移、RLS 双保险（非超级用户角色+默认拒绝策略）、repository 层、种子、Qdrant collection | 11/11 通过（迁移可重放、repo/RLS 双层隔离、软删除、种子幂等、Qdrant 索引核验；1 处测试断言错误排查后修正） | feat(M1) |
| 2026-07-22 | M0 | 项目骨架落地：uv workspace（api/worker/core 三包）、docker-compose 四服务、pydantic-settings 配置、/healthz、ruff+pytest | 6/6 通过（lint、单测、四容器 healthy、healthz 端到端、配置加载） | feat(M0) |
