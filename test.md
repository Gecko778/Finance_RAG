# 测试记录（test.md）

> 倒序追加：最新记录在最上面。所有测试均为真实执行，附命令与实际输出。

---

## 2026-07-22 · M0 项目初始化

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
