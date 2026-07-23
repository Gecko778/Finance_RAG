"""初始化 Qdrant collection 与 payload 索引。

幂等：collection 已存在则跳过创建。
用法：uv run python scripts/init_qdrant.py
"""

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PayloadSchemaType, VectorParams
from rag_core.settings import get_settings

COLLECTION = "chunks"

PAYLOAD_INDEXES = {
    "tenant_id": PayloadSchemaType.KEYWORD,
    "kb_id": PayloadSchemaType.KEYWORD,
    "doc_id": PayloadSchemaType.KEYWORD,
    "is_public": PayloadSchemaType.BOOL,
    "expire_date": PayloadSchemaType.DATETIME,
}


def main() -> None:
    s = get_settings()
    client = QdrantClient(url=s.qdrant_url, api_key=s.qdrant_api_key)

    if client.collection_exists(COLLECTION):
        print(f"collection '{COLLECTION}' 已存在，跳过创建")
    else:
        client.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=s.embedding_dim, distance=Distance.COSINE),
        )
        print(f"collection '{COLLECTION}' 创建完成（dim={s.embedding_dim}, cosine）")

    for field, schema in PAYLOAD_INDEXES.items():
        client.create_payload_index(
            collection_name=COLLECTION, field_name=field, field_schema=schema
        )
    print(f"payload 索引就绪：{', '.join(PAYLOAD_INDEXES)}")


if __name__ == "__main__":
    main()
