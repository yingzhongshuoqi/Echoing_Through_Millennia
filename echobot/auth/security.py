from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime


PBKDF2_ITERATIONS = 120_000


def normalize_username(username: str) -> tuple[str, str]:
    """清洗用户名，并生成用于唯一校验的规范化键。"""

    normalized = username.strip()
    if len(normalized) < 2 or len(normalized) > 32:
        raise ValueError("用户名长度需要在 2 到 32 个字符之间")
    return normalized, normalized.casefold()


def validate_password(password: str) -> str:
    """做最小密码校验，避免空密码或过短密码。"""

    normalized = password.strip()
    if len(normalized) < 6:
        raise ValueError("密码长度不能少于 6 位")
    return normalized


def hash_password(password: str) -> str:
    """使用 PBKDF2 生成可长期存储的密码摘要。"""

    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PBKDF2_ITERATIONS,
    )
    return (
        f"pbkdf2_sha256"
        f"${PBKDF2_ITERATIONS}"
        f"${salt}"
        f"${digest.hex()}"
    )


def verify_password(password: str, stored_hash: str) -> bool:
    """校验用户输入密码与数据库摘要是否一致。"""

    try:
        algorithm, iterations_text, salt, digest_hex = stored_hash.split("$", 3)
    except ValueError:
        return False

    if algorithm != "pbkdf2_sha256":
        return False

    try:
        iterations = int(iterations_text)
    except ValueError:
        return False

    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations,
    ).hex()
    return hmac.compare_digest(digest, digest_hex)


def generate_session_token() -> str:
    """生成发送给浏览器的原始会话令牌。"""

    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    """数据库仅保存令牌哈希，避免明文会话泄露。"""

    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def utc_now() -> datetime:
    """统一返回 UTC 时间，避免时区比较问题。"""

    return datetime.now(UTC)
