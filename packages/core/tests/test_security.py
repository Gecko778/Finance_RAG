"""安全原语单测：密码哈希、API Key 生成与哈希。"""

from rag_core.security import (
    generate_api_key,
    hash_api_key,
    hash_password,
    verify_password,
)


def test_password_hash_roundtrip():
    h = hash_password("admin123")
    assert h != "admin123"  # 不是明文
    assert verify_password("admin123", h)
    assert not verify_password("wrong", h)


def test_password_hash_is_salted():
    # 同一密码两次哈希不同（bcrypt 自带随机盐）
    assert hash_password("x") != hash_password("x")


def test_generate_api_key_prefix_and_hash():
    plaintext, key_hash = generate_api_key()
    assert plaintext.startswith("fr_")
    assert key_hash == hash_api_key(plaintext)
    assert key_hash != plaintext
    assert len(key_hash) == 64  # sha256 hex


def test_api_keys_are_unique():
    assert generate_api_key()[0] != generate_api_key()[0]
