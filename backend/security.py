"""密码哈希与会话令牌。

密码用标准库 `hashlib.scrypt`（OpenSSL 实现），不引入原生依赖：
- 每个密码独立 16 字节随机盐
- 参数写进哈希串，将来提高强度时旧哈希仍可校验
- 校验用 `hmac.compare_digest`，避免计时侧信道

会话令牌是 32 字节随机串，**库里只存它的 SHA-256**，
所以数据库泄露也无法直接拿来冒充登录。
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

from config import settings

SCRYPT_N = 2**15  # 32768
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_MAXMEM = 64 * 1024 * 1024  # 32MiB 是 OpenSSL 默认上限，这里显式放宽
KEY_BYTES = 64
SALT_BYTES = 16

SESSION_TOKEN_BYTES = 32


def _b64encode(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def _b64decode(text: str) -> bytes:
    return base64.b64decode(text.encode("ascii"))


def _derive(password: str, salt: bytes, n: int, r: int, p: int, length: int) -> bytes:
    return hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=n,
        r=r,
        p=p,
        dklen=length,
        maxmem=SCRYPT_MAXMEM,
    )


def hash_password(password: str) -> str:
    """返回 `scrypt$n$r$p$salt$key`。"""
    salt = secrets.token_bytes(SALT_BYTES)
    key = _derive(password, salt, SCRYPT_N, SCRYPT_R, SCRYPT_P, KEY_BYTES)
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${_b64encode(salt)}${_b64encode(key)}"


def verify_password(password: str, encoded: str) -> bool:
    """恒定时间校验；任何格式异常都当作校验失败，不抛出。"""
    try:
        algorithm, n, r, p, salt_b64, key_b64 = encoded.split("$")
        if algorithm != "scrypt":
            return False
        salt = _b64decode(salt_b64)
        expected = _b64decode(key_b64)
        candidate = _derive(password, salt, int(n), int(r), int(p), len(expected))
    except (ValueError, TypeError, AttributeError):
        return False
    return hmac.compare_digest(candidate, expected)


def new_session_token() -> str:
    return secrets.token_urlsafe(SESSION_TOKEN_BYTES)


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def password_problem(password: str) -> str | None:
    """返回不合规原因，合规返回 None。"""
    if len(password) < settings.password_min_length:
        return f"密码至少需要 {settings.password_min_length} 位"
    if password.strip() != password:
        return "密码首尾不能是空白字符"
    return None


# 账号不存在时也跑一次同样代价的校验，避免用响应时间判断邮箱是否注册。
DUMMY_HASH = hash_password("timing-equalizer-not-a-real-password")
