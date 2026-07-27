# 测试记录（test.md）

> 倒序追加：最新记录在最上面。所有测试均为真实执行，附命令与实际输出。

---

## 2026-07-27 · 🎯 端到端全链路实测（关闭 M2/M3/M5/M6 所有 ⏳）

key 就绪（SiliconFlow .cn + DeepSeek）后一次性真实跑通。**以下取代此前各里程碑标记的"待补"项**：

| 关联 | 测试项 | 预期 | 实际 | 结论 |
|---|---|---|---|---|
| M2 #9 | 上传真实政策→ready→Qdrant 有向量 | 3 份 ready + 向量入库 | 3 份 ready（9/40/91 块），Qdrant 140 向量 | ✅ |
| M2 风险 | **docx 表格解析端到端** | 表格行可被检索引用 | /chat 回答引用了"一个季度｜季度30万元"表格行 | ✅ |
| M3 #7 | /retrieval 带出处 | 命中相关片段 | 起征点问题命中公告(score .997)+增值税法 | ✅ |
| M3 #7 | /chat 流式带引用 | 正确答案+出处+复核提示 | "季度30万元[1]"+引用+复核提示；SSE citations→token→done | ✅ |
| M3 验收 | 库外问题拒答 | 明确"未找到依据"不编造 | 企业所得税问题正确拒答 | ✅ |
| M5 #15 | 前端对话 E2E | 浏览器提问→流式回答+引用 | 浏览器实操成功，回答+表格引用+复核提示 | ✅ |
| M6 #11 | run_eval 真跑分 | 出基线 | /chat 级评测：自动 5/8；人工核验 8/8 实质正确（3 假阴性为子串判据，答案实际正确，见 eval_result.json） | ✅ |
| M6 #13 | 前端反馈按钮 E2E | 点击→入库 | 点"有帮助"→后端 feedback 表出现该条(up+真实问答) | ✅ |

**评测器说明**：run_eval 从 /retrieval 级升级为 /chat 级（更贴近真实系统）；refusal 改判"答案是否拒答"、召回改判"答案是否含要点"。3 条 cross_article/freshness 自动判 False 均为精确子串假阴性（答案逐字正确，仅标点/措辞差异）——如实记 5/8，不调判据凑分；精确评分升级项=接入 LLM-judge。

**仍待非软件条件**：M6 财税人员真人内测（需组织测试人员）、M7 语音（需小智机器人硬件）。

---

## 2026-07-27 · M8 部署基础设施：api/worker 容器化 ✅

| # | 测试项 | 预期 | 实际 | 结论 |
|---|---|---|---|---|
| 1 | 构建 API 镜像 | docker build 成功 | `naming to finance-rag-api` 成功（uv 改 pip 后）| ✅ |
| 2 | API 镜像内导入 | rag_api.main 可导入 | `rag_api import OK` | ✅ |
| 3 | 构建 worker 镜像 | docker build 成功 | BUILD OK | ✅ |
| 4 | worker 镜像内导入 | rag_worker.main 可导入 | `rag_worker import OK` | ✅ |

**过程问题**：`COPY --from=ghcr.io/astral-sh/uv` 拉取失败（ghcr.io 短读 EOF，本环境网络不稳）→ 改 `pip install uv`，构建通过。

**M8 结论**：api/worker/web 三镜像齐备并验证可构建/可导入。M8 其余（K8s 编排、计费、自助开通、交付形态）属产品/架构决策，待与负责人沟通后再规划实施。

| # | 测试项 | 预期 | 实际 | 结论 |
|---|---|---|---|---|
| 1 | lint + 全套单测 | 0 错误 / 全过 | All checks passed；`40 passed`（+3 插件测试） | ✅ |
| 2 | build_context 带引用 | 生成 `[序号] 来源：文号 文件名` + 要点 | 断言通过 | ✅ |
| 3 | build_context 空结果 | 返回"没有找到相关政策依据" | 通过 | ✅ |
| 4 | build_context 上限 5 条 | 最多取前 5 | 通过 | ✅ |
| 5 | 插件契约（X-API-Key+query） | 越过认证/scope/校验直达检索 | HTTP 500（仅 embedding 因 key 失败） | ✅ |
| 6 | 契约对照：缺 query | 422 | 422 | ✅ |
| 7 | 契约对照：Bearer 传 apikey | 401（须用 X-API-Key） | 401 | ✅ |
| 8 | **语音问答端到端** | 对小智提问→知识库作答 | **待补**：需 SiliconFlow key + 灌库 + 小智 server 启动 | ⏳ 待补 |

**M7 结论**：插件、安装文档、纯逻辑单测完成；插件与本平台 API 的契约（请求形态/认证头/错误处理）实测正确（7 项）；语音端到端待 key + 机器人环境（#8）。

| # | 测试项 | 预期 | 实际 | 结论 |
|---|---|---|---|---|
| 1 | lint + 单测 | 0 错误 / 全过 | All checks passed；`37 passed` | ✅ |
| 2 | feedback 迁移 upgrade | 建表 + 授权 + RLS | 表创建成功 | ✅ |
| 3 | 迁移 down/up 回放 | 可逆 | downgrade -1 → upgrade head 成功 | ✅ |
| 4 | 评测集加载 | 8 例 4 类别 | factual3/cross_article2/refusal2/freshness1 | ✅ |
| 5 | 提交反馈（好评） | 201 | 201 + 返回记录 | ✅ |
| 6 | 提交反馈（差评） | 201 | 201 | ✅ |
| 7 | 无效 rating | 422 | 422 | ✅ |
| 8 | 管理员查看反馈 | 倒序列出 | 2 条（down/up）正确 | ✅ |
| 9 | rating 过滤 | 仅返回该类 | down=1 | ✅ |
| 10 | 前端构建（反馈按钮） | 通过 | `✓ built` | ✅ |
| 11 | **run_eval 真实跑分** | 引用/召回/拒答判分 | **待补**：需检索可用（SiliconFlow key + 灌库） | ⏳ 待补 |
| 12 | **财税人员真人内测** | badcase 收集 + RAGAS 基线 | **待补**：需 key + 测试人员 | ⏳ 待补 |
| 13 | **前端反馈按钮 E2E** | 对真实回答评价 | **待补**：需 chat 可用（key） | ⏳ 待补 |

**M6 结论**：评测集、评测运行器、反馈表/接口、前端反馈按钮全部建成，反馈链路 + 迁移 + 评测集加载实测通过（10 项）；真实跑分/真人内测/前端反馈 E2E 待 key 与测试人员（#11-13）。

**后端（对真实后端实测）**

| # | 测试项 | 预期 | 实际 | 结论 |
|---|---|---|---|---|
| 1 | lint + 单测 | 0 错误 / 全过 | All checks passed；`37 passed` | ✅ |
| 2 | 成员列表 | 返回本租户成员 | admin 正确返回 | ✅ |
| 3 | 创建成员 | 201 | tester 创建成功 | ✅ |
| 4 | 停用成员 | is_active=false | 停用成功 | ✅ |
| 5 | **停用后登录** | 401（即时生效） | 401 | ✅ |
| 6 | 审计查询 | 时间倒序含各操作 | member.create/deactivate/auth.login/kb.delete 齐全 | ✅ |

**前端（构建 + 浏览器渲染，真实后端数据）**

| # | 测试项 | 预期 | 实际 | 结论 |
|---|---|---|---|---|
| 7 | Vite 构建 | 通过 | `✓ built`（1686 模块） | ✅ |
| 8 | 管理员侧栏 | 显示成员/API Key/审计三项 | 三项均显示（isAdmin 条件渲染） | ✅ |
| 9 | 成员管理页 | 表格显示真实成员+角色标签 | admin(管理员/admin 标签) + tester(测试员/member) | ✅ |
| 10 | 审计日志页 | 完整操作链倒序 + 过滤框 | member/kb/apikey/auth 全操作链渲染 | ✅ |
| 11 | API Key 创建流程 | 明文仅一次绿条展示 + 列表状态 | 明文 `fr_VGwc...` 绿条展示，列表有效/已吊销正确 | ✅ |
| 12 | 控制台错误 | 无 | 无 | ✅ |

**M5.5 验收结论**：成员/API Key/审计后端 + 前端管理页全部实测通过（含停用即时生效、明文一次性展示、完整审计链）。✅ 全部不依赖 key。

**后端补齐验证（对真实后端）**

| # | 测试项 | 预期 | 实际 | 结论 |
|---|---|---|---|---|
| 1 | Python lint + 单测 | 0 错误 / 全过 | ruff All checks passed；`37 passed` | ✅ |
| 2 | GET /auth/me | 返回 tenant/user/role | role=admin 正确 | ✅ |
| 3 | GET /kbs | 列出本租户+公共库 | 公共库+私有库均返回 | ✅ |
| 4 | POST /kbs 建库 | 201 | 201 + 返回库对象 | ✅ |
| 5 | DELETE /kbs | 204（空库） | 204 | ✅ |

**前端构建 + 浏览器渲染验证（内置浏览器，真实后端数据）**

| # | 测试项 | 预期 | 实际 | 结论 |
|---|---|---|---|---|
| 6 | Vite 构建 | vue-tsc 类型检查 + 打包通过 | `✓ built`（500kB 警告为 Element Plus 体积，非错误） | ✅ |
| 7 | 登录页渲染 | 表单正常 | 标题+租户/邮箱/密码+登录按钮渲染 | ✅ |
| 8 | 真实登录流程 | 输入种子凭据→JWT→跳知识库页 | 登录成功，进入知识库页，顶栏显示"角色：admin" | ✅ |
| 9 | 知识库页真实数据 | 显示后端两个库 | 全国财税政策库（公共，带标签）+ 内部SOP（私有） | ✅ |
| 10 | RBAC UI | 公共库无删除、私有库有删除 | 公共库仅"文档"，私有库有"删除" | ✅ |
| 11 | 文档页 | 表格列齐、空库 No Data | 文件名/状态/文号/生效日期列 + No Data | ✅ |
| 12 | 上传对话框（财税元数据表单） | 文件+文号+生效/失效日期+来源 | 全字段渲染，含"失效政策默认不被检索"提示 | ✅ |
| 13 | 对话页 | 知识库多选+输入+发送+复核提示 | 全部渲染，含"正式对客户输出前请财税人员复核" | ✅ |
| 14 | 控制台错误 | 无 | 无 console error | ✅ |
| 15 | **对话问答 E2E** | 提问→流式带出处回答 | **待补**：依赖 SiliconFlow+DeepSeek key（与 M2/M3 一起） | ⏳ 待补测 |

**过程中发现并解决的问题**：
1. uv workspace `apps/*` 误把 Node 前端 `apps/web` 当 Python 成员 → 后端启动失败 → workspace 加 `exclude`
2. npm peer-dep 冲突（vite@undefined 解析顺序）→ `--legacy-peer-deps`
3. 内置浏览器拦 localhost 直连 → 改用 preview_start；视口尺寸变化致坐标点击失准 → 改用 read_page + form_input 按 ref 精确操作

**M5 验收结论**：核心操作台 4 页全部构建通过并浏览器渲染验证（真实登录+真实数据+RBAC UI），后端补齐接口实测通过；**对话问答 E2E 待 key 后补（#15）**。✅

**单元测试（无基础设施）**

| # | 测试项 | 命令 | 预期 | 实际 | 结论 |
|---|---|---|---|---|---|
| 1 | Lint | `uv run ruff check .` | 0 错误 | 修复若干（B008 scope 依赖提模块级、E702 等）→ All checks passed | ✅ |
| 2 | 安全原语 | pytest `test_security.py`（4 项） | 密码往返/加盐、API Key 前缀+sha256+唯一 | 全过 | ✅ |
| 3 | 认证逻辑 | pytest `test_auth.py`（8 项） | JWT 往返、无效令牌 401、is_admin/has_scope、require_admin/user/scope 守卫 | 全过 | ✅ |
| 4 | 全套回归 | `uv run pytest -q` | 全过 | `37 passed` | ✅ |

**集成测试（对真实 Postgres/Redis，`scripts/m4_integration_check.py`，14 项全过）**

| 用例 | 预期 | 结论 |
|---|---|---|
| 错误密码登录 | 401 | ✅ |
| 正确凭据登录 | 200 + token + role=admin | ✅ |
| 无认证访问受保护端点 | 401 | ✅ |
| 管理员创建 API Key | 201 + 明文(fr_ 前缀)仅返回一次 | ✅ |
| API Key 列表 | 可见且不含明文/哈希 | ✅ |
| 无效 scope 创建 | 422 | ✅ |
| retrieval-scope key 调 /chat | 403（触及 LLM 前拦截） | ✅ |
| API Key 调文档管理 | 403（限用户令牌） | ✅ |
| 吊销 API Key | 204 | ✅ |
| **吊销后立即复用** | 401（不得溜过） | ✅（修复竞态后） |
| member 令牌管理 API Key | 403 | ✅ |
| 他租户令牌读本租户数据 | 200 且为空（RLS 隔离） | ✅ |

**过程中发现并修复的问题**：
1. **TestClient + 异步 SQLAlchemy 事件循环冲突**（"attached to a different loop"）→ 集成脚本改用真 uvicorn + httpx（与 M2/M3 e2e 一致）
2. **读写竞态（真 bug，httpx 背靠背请求暴露）**：吊销 API Key 后立即复用返回 500 而非 401——`get_db` 提交发生在响应之后，下一请求抢在落库前读了旧快照。curl（正常延迟）即时/延迟均正确 401，确认是提交时机问题。根因修复：写路由返回前显式提交。顺带修掉 M2 上传-enqueue 抢跑隐患。

**M4 验收结论**：跨租户访问被拒、认证/授权/配额/审计全部实测通过（单元 37 + 集成 14）。✅

| # | 测试项 | 执行命令 | 预期 | 实际 | 结论 |
|---|---|---|---|---|---|
| 1 | Lint | `uv run ruff check .` | 0 错误 | 修复 3 处（2 自动 + 1 docstring 换行）→ All checks passed | ✅ |
| 2 | 时效过滤单测 | pytest `test_retrieval_service.py`（7 项） | 失效剔除/include_expired放开/null与未来保留/软删剔除/跨租户剔除/引用组装 | 全过 | ✅ |
| 3 | 提示词单测 | pytest `test_prompts.py`（2 项） | 无资料返回拒答提示；有资料编号+财税规则在位 | 全过 | ✅ |
| 4 | 全套回归 | `uv run pytest -q` | 全过 | `25 passed` | ✅ |
| 5 | App 启动+路由注册 | TestClient 加载 app + 查 OpenAPI | /retrieval、/chat 均注册 | 两路由已注册，app 正常启动 | ✅ |
| 6 | 请求校验 | 空 query / 缺租户头 POST | 均 422（不触外部 API） | 均返回 422 | ✅ |
| 7 | **问答端到端** | 上传→ready→POST /chat 得带出处回答 | — | **待补**：依赖有效 SiliconFlow key（检索/rerank）+ DeepSeek key（生成）+ Qdrant 有向量（即 M2 ready 路径先通） | ⏳ 待补测 |

**M2/M3 端到端阻塞点（同一根因）**：SiliconFlow key `sk-zux...dxxf` 被官方 embeddings 与 user/info 端点均判 `401 Token is invalid`（已直连验证，非代码问题）。M3 检索/rerank 用同一 key，生成还需 DeepSeek key。三者就绪后，M2 ready 路径与 M3 问答一并补测。

**M3 验收结论**：检索/生成代码 + 纯逻辑（时效过滤、提示词、引用组装）+ 路由装配 6 项实测通过；**问答端到端待 key 后补验（#7）**。

| # | 测试项 | 执行命令 | 预期 | 实际 | 结论 |
|---|---|---|---|---|---|
| 1 | Lint | `uv run ruff check .` | 0 错误 | 首轮 8 处（5 自动修复；FastAPI Form 默认值 B008 误报加白名单；1 处手工换行）→ 0 | ✅（修复后） |
| 2 | 切块单测 | pytest `test_chunking.py`（4 项） | 条款切分/元数据头/重叠/回退全对 | 通过 | ✅ |
| 3 | 解析器单测 | pytest `test_parsers.py`（6 项：txt utf8/gbk、md、docx 段落+表格、不支持格式、空结果） | 全对 | 通过 | ✅ |
| 4 | 全套回归 | `uv run pytest -q` | 全过 | `16 passed` | ✅ |
| 5 | 上传 API 端到端 | curl POST 上传 txt（带 X-Tenant-Id + doc_number 表单） | 201 + status=uploaded | 返回文档 JSON，status=uploaded | ✅ |
| 6 | MinIO 落盘 | `mc ls` 桶内路径 | 对象存在于 tenant/{doc_id}/ 路径 | 239B 对象在正确路径 | ✅ |
| 7 | 状态机失败路径 | 无 API Key 上传→worker 消费 | 走到 embedding 后 failed + 明确错误 | **首轮 bug**：状态卡 embedding 永不回写（见下）→ 修复后 status=failed, error="SILICONFLOW_API_KEY 未配置" | ✅（修复后） |
| 8 | 删除级联清理 | DELETE 文档 → 查 MinIO/PG/API | 204；MinIO 对象删除；GET 404；PG 记录保留+deleted_at | 全部符合 | ✅ |
| 9 | **ready 路径端到端** | 上传真实政策 PDF/DOCX → ready → Qdrant 可查 | — | **待补**：需 SILICONFLOW_API_KEY（用户填 .env）+ 真实文档（用户放 testdata/） | ⏳ 待补测 |

**过程中发现并修复的问题**：
1. **arq 重试机制理解错误（#7 首轮失败，真 bug）**：arq 对普通异常不自动重试（仅显式 `Retry` 才重试），原代码 `job_try>=3 才回写 failed` 的条件永远不满足，文档状态卡死在 embedding。实测日志确认单次失败即终结后，修正为：任务级不重试、异常即回写 failed（临时故障已由 embedding HTTP 层 3 次重试覆盖）。重新实测：failed 状态与错误信息正确回写
2. FastAPI `Form()` 默认值触发 ruff B008 误报 → flake8-bugbear extend-immutable-calls 白名单

**M2 验收结论**：管线代码与失败路径、删除级联全部实测通过；**ready 路径（真实向量化入 Qdrant）待用户提供 API Key 与真实文档后补验，届时补录 #9**。

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
