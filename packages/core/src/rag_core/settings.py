"""全局配置：从环境变量 / .env 读取，所有服务共享。"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- PostgreSQL（业务库） ---
    # 应用连接：非超级用户 finance_rag_app（由迁移创建），受 RLS 约束
    database_url: str = (
        "postgresql+asyncpg://finance_rag_app:finance_rag_app_dev@localhost:5432/finance_rag"
    )
    # 管理连接：仅用于迁移/种子脚本（compose 的超级用户，绕过 RLS）
    database_admin_url: str = (
        "postgresql+asyncpg://finance_rag:finance_rag_dev@localhost:5432/finance_rag"
    )

    # --- Redis（队列/缓存） ---
    redis_url: str = "redis://localhost:6379/0"

    # --- Qdrant（向量库） ---
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None

    # --- MinIO（原始文档对象存储） ---
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "finance-rag-docs"
    minio_secure: bool = False

    # --- SiliconFlow（embedding + rerank） ---
    siliconflow_api_key: str = ""
    siliconflow_base_url: str = "https://api.siliconflow.cn/v1"
    embedding_model: str = "BAAI/bge-m3"
    embedding_dim: int = 1024
    rerank_model: str = "BAAI/bge-reranker-v2-m3"

    # --- LLM（经 LiteLLM 抽象，后期可切本地模型） ---
    llm_model: str = "deepseek/deepseek-chat"
    deepseek_api_key: str = ""

    # --- 认证与安全 ---
    jwt_secret: str = "dev-insecure-change-in-production"  # 生产必须覆盖
    jwt_expire_minutes: int = 720  # 前端登录令牌有效期（默认 12h）
    api_key_prefix: str = "fr"  # API Key 明文前缀：fr_xxxxx


@lru_cache
def get_settings() -> Settings:
    return Settings()
