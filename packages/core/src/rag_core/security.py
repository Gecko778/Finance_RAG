"""安全原语：密码哈希（bcrypt）、API Key 生成与哈希（sha256）。

- 密码：bcrypt（慢哈希，抗暴力破解）
- API Key：高熵随机串，用 sha256 快哈希存储（高熵无需慢哈希，且每请求校验需快）
"""

import hashlib
import secrets

import bcrypt

from rag_core.settings import get_settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def generate_api_key() -> tuple[str, str]:
    """返回 (明文, 哈希)。明文仅在创建时返回一次，库中只存哈希。"""
    plaintext = f"{get_settings().api_key_prefix}_{secrets.token_urlsafe(32)}"
    return plaintext, hash_api_key(plaintext)


def hash_api_key(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode()).hexdigest()
