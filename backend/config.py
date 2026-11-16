"""集中读取环境变量。

密钥只从环境变量 / backend/.env 读取，不写死、不返回给前端。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ENV_FILE = Path(__file__).with_name(".env")
load_dotenv(ENV_FILE)

DEFAULT_LLM_BASE_URL = "https://api.deepseek.com/v1"
DEFAULT_VISION_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"


def _text(name: str, default: str) -> str:
    return (os.getenv(name) or default).strip()


def _optional(name: str) -> str | None:
    value = (os.getenv(name) or "").strip()
    return value or None


def _number(name: str, default: float, cast=float):
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return cast(raw)
    except (TypeError, ValueError):
        return default


def _flag(name: str, default: bool) -> bool:
    raw = (os.getenv(name) or "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def _origins(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    items = tuple(item.strip().rstrip("/") for item in raw.split(",") if item.strip())
    return items or default


DEFAULT_ORIGINS = ("http://localhost:5173", "http://127.0.0.1:5173")


@dataclass(frozen=True)
class Settings:
    llm_api_key: str | None
    llm_base_url: str
    llm_model: str
    vision_api_key: str | None
    vision_base_url: str
    vision_model: str
    request_timeout: float
    max_upload_mb: int
    max_frames: int
    frame_min_interval: float
    # --- 认证与持久化 ---
    db_url: str
    session_cookie: str
    session_ttl_hours: int
    session_remember_days: int
    session_sliding: bool
    cookie_secure: bool
    cookie_samesite: str
    max_login_attempts: int
    lockout_minutes: int
    password_min_length: int
    allowed_origins: tuple[str, ...]

    @property
    def llm_ready(self) -> bool:
        return bool(self.llm_api_key)

    @property
    def vision_ready(self) -> bool:
        return bool(self.vision_api_key)


def load_settings() -> Settings:
    llm_key = _optional("LLM_API_KEY")
    llm_base = _text("LLM_BASE_URL", DEFAULT_LLM_BASE_URL).rstrip("/")
    # 视觉能力默认复用文本服务的 Key，但允许单独指向另一家（例如文本用 DeepSeek、看图用 Qwen-VL）。
    vision_key = _optional("VISION_API_KEY") or llm_key
    vision_base = (os.getenv("VISION_BASE_URL") or "").strip().rstrip("/") or (
        llm_base if _optional("VISION_API_KEY") is None else DEFAULT_VISION_BASE_URL
    )
    return Settings(
        llm_api_key=llm_key,
        llm_base_url=llm_base,
        llm_model=_text("LLM_MODEL", "deepseek-chat"),
        vision_api_key=vision_key,
        vision_base_url=vision_base,
        vision_model=_text("VISION_MODEL", "qwen-vl-max"),
        request_timeout=_number("LLM_TIMEOUT", 90.0),
        max_upload_mb=_number("MAX_UPLOAD_MB", 50, int),
        max_frames=_number("MAX_FRAMES", 6, int),
        frame_min_interval=_number("FRAME_MIN_INTERVAL", 1.0),
        db_url=_text("APP_DB_URL", "sqlite:///./recut.db"),
        session_cookie=_text("APP_SESSION_COOKIE", "recut_session"),
        session_ttl_hours=_number("APP_SESSION_TTL_HOURS", 12, int),
        session_remember_days=_number("APP_SESSION_REMEMBER_DAYS", 30, int),
        session_sliding=_flag("APP_SESSION_SLIDING", True),
        cookie_secure=_flag("APP_COOKIE_SECURE", False),
        cookie_samesite=_text("APP_COOKIE_SAMESITE", "lax"),
        max_login_attempts=_number("APP_MAX_LOGIN_ATTEMPTS", 5, int),
        lockout_minutes=_number("APP_LOCKOUT_MINUTES", 15, int),
        password_min_length=_number("APP_PASSWORD_MIN_LENGTH", 10, int),
        allowed_origins=_origins("APP_ALLOWED_ORIGINS", DEFAULT_ORIGINS),
    )


settings = load_settings()
