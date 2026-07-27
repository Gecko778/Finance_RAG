# 财税 RAG 摄取 worker 镜像（arq）。构建上下文 = 仓库根目录：
#   docker build -f apps/worker/Dockerfile -t finance-rag-worker .
FROM python:3.13-slim
RUN pip install --no-cache-dir uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

COPY pyproject.toml uv.lock ./
COPY packages/core/pyproject.toml packages/core/
COPY apps/api/pyproject.toml apps/api/
COPY apps/worker/pyproject.toml apps/worker/

COPY packages/core/ packages/core/
COPY apps/worker/ apps/worker/
RUN uv sync --package rag-worker --no-dev

CMD ["uv", "run", "--no-sync", "arq", "rag_worker.main.WorkerSettings"]
