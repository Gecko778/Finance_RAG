# Finance RAG — 财税企业级 RAG 平台

财税知识库检索增强生成（RAG）平台：内测 → 接入（小智机器人等）→ 多租户 SaaS 三步走。
总体规划见 [plan.md](plan.md)，进展见 [progress.md](progress.md)，测试记录见 [test.md](test.md)。

## 技术栈

Python 3.11+ / FastAPI / LangChain / PostgreSQL / Qdrant / Redis / MinIO / SiliconFlow(BGE-M3) / LiteLLM

## 本地启动

前置：安装 [uv](https://docs.astral.sh/uv/) 与 Docker。

```bash
# 1. 启动基础设施（PostgreSQL / Redis / Qdrant / MinIO）
docker compose up -d

# 2. 安装依赖（全部 workspace 成员 + dev 工具）
uv sync --all-packages

# 3. 配置环境变量
cp .env.example .env   # 填入 SILICONFLOW_API_KEY / DEEPSEEK_API_KEY

# 4. 启动 API
uv run uvicorn rag_api.main:app --reload

# 5. 验证
curl http://localhost:8000/healthz   # -> {"status":"ok"}
```

## 开发命令

```bash
uv run pytest          # 测试
uv run ruff check .    # lint
```

## 目录结构

```
apps/api/        FastAPI HTTP 服务
apps/worker/     摄取 worker（M2 起启用 arq）
packages/core/   共享核心：配置 / schema / 检索 / 模型客户端
```
