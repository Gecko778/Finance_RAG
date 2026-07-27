# 财税 RAG API 镜像（供 M8 K8s / compose 部署）。构建上下文 = 仓库根目录：
#   docker build -f apps/api/Dockerfile -t finance-rag-api .
FROM python:3.13-slim
RUN pip install --no-cache-dir uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

# 先复制依赖清单以利缓存
COPY pyproject.toml uv.lock ./
COPY packages/core/pyproject.toml packages/core/
COPY apps/api/pyproject.toml apps/api/
COPY apps/worker/pyproject.toml apps/worker/

# 再复制源码并安装工作区（api + 其依赖 rag-core）
COPY packages/core/ packages/core/
COPY apps/api/ apps/api/
RUN uv sync --package rag-api --no-dev

EXPOSE 8000
CMD ["uv", "run", "--no-sync", "uvicorn", "rag_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
