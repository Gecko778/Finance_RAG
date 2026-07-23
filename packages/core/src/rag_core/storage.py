"""MinIO 对象存储：原始文档的存取与删除。"""

from functools import lru_cache
from io import BytesIO

from minio import Minio

from rag_core.settings import get_settings


@lru_cache
def get_minio() -> Minio:
    s = get_settings()
    client = Minio(
        s.minio_endpoint,
        access_key=s.minio_access_key,
        secret_key=s.minio_secret_key,
        secure=s.minio_secure,
    )
    if not client.bucket_exists(s.minio_bucket):
        client.make_bucket(s.minio_bucket)
    return client


def upload_bytes(object_path: str, data: bytes, content_type: str = "") -> None:
    get_minio().put_object(
        get_settings().minio_bucket,
        object_path,
        BytesIO(data),
        length=len(data),
        content_type=content_type or "application/octet-stream",
    )


def download_bytes(object_path: str) -> bytes:
    resp = get_minio().get_object(get_settings().minio_bucket, object_path)
    try:
        return resp.read()
    finally:
        resp.close()
        resp.release_conn()


def delete_object(object_path: str) -> None:
    get_minio().remove_object(get_settings().minio_bucket, object_path)
