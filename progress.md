# 进展记录（progress.md）

> 倒序追加：最新记录在最上面。每次代码生成完成后写一条。详细测试见 test.md。

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
