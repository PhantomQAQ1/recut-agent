"""SQLite 访问层：连接、建表、时间工具。

刻意不引入 ORM：本项目读模式很简单（按 id / email / user_id 取行），
标准库 sqlite3 足够，少一个依赖就少一处升级负担。

约定：
- 时间统一存 **naive UTC 的 ISO 字符串**（"YYYY-MM-DDTHH:MM:SS.ffffff"），
  这样字符串比较等价于时间比较，跨时区也不会错。
- 事务用 `with connect() as conn:`，成功提交、异常回滚。
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

from config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    email           TEXT    NOT NULL UNIQUE,
    password_hash   TEXT    NOT NULL,
    display_name    TEXT    NOT NULL,
    role            TEXT    NOT NULL DEFAULT 'member' CHECK (role IN ('member', 'admin')),
    status          TEXT    NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'disabled')),
    failed_attempts INTEGER NOT NULL DEFAULT 0,
    locked_until    TEXT,
    last_login_at   TEXT,
    created_at      TEXT    NOT NULL,
    updated_at      TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    id           TEXT    PRIMARY KEY,
    user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    remember     INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT    NOT NULL,
    expires_at   TEXT    NOT NULL,
    last_seen_at TEXT    NOT NULL,
    ip           TEXT,
    user_agent   TEXT,
    revoked_at   TEXT
);

CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at);

CREATE TABLE IF NOT EXISTS login_attempts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    email      TEXT,
    ip         TEXT,
    success    INTEGER NOT NULL,
    reason     TEXT    NOT NULL,
    created_at TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_attempts_email ON login_attempts(email, created_at);

CREATE TABLE IF NOT EXISTS projects (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name       TEXT    NOT NULL,
    storyboard TEXT    NOT NULL DEFAULT '{}',
    version    INTEGER NOT NULL DEFAULT 1,
    created_at TEXT    NOT NULL,
    updated_at TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_projects_user ON projects(user_id, updated_at);

CREATE TABLE IF NOT EXISTS characters (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name          TEXT    NOT NULL,
    name_key      TEXT    NOT NULL,
    role_label    TEXT    NOT NULL DEFAULT '',
    description   TEXT    NOT NULL DEFAULT '',
    consistency   REAL,
    prompt_anchor TEXT    NOT NULL DEFAULT '',
    tone          TEXT    NOT NULL DEFAULT 'amber'
                          CHECK (tone IN ('amber', 'violet', 'rose', 'indigo', 'neutral')),
    version       INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT    NOT NULL,
    updated_at    TEXT    NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_characters_name ON characters(user_id, name_key);
CREATE INDEX IF NOT EXISTS idx_characters_user ON characters(user_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS tags (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name       TEXT    NOT NULL,
    name_key   TEXT    NOT NULL,
    category   TEXT    NOT NULL
                       CHECK (category IN ('character', 'emotion', 'palette', 'lighting', 'appearance')),
    tone       TEXT    NOT NULL DEFAULT 'neutral'
                       CHECK (tone IN ('amber', 'violet', 'rose', 'indigo', 'neutral')),
    created_at TEXT    NOT NULL,
    updated_at TEXT    NOT NULL
);

-- 标签名在"同一用户内全局唯一"：跨分组也不允许重名，避免打标签时出现歧义。
CREATE UNIQUE INDEX IF NOT EXISTS idx_tags_name ON tags(user_id, name_key);
CREATE INDEX IF NOT EXISTS idx_tags_category ON tags(user_id, category, name);

CREATE TABLE IF NOT EXISTS character_tags (
    character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    tag_id       INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    created_at   TEXT    NOT NULL,
    PRIMARY KEY (character_id, tag_id)
);

-- 反查"哪些角色用了这个标签"，删除标签与引用提示都依赖它。
CREATE INDEX IF NOT EXISTS idx_character_tags_tag ON character_tags(tag_id);

CREATE TABLE IF NOT EXISTS uploads (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    sha256     TEXT    NOT NULL,
    mime       TEXT    NOT NULL,
    bytes      INTEGER NOT NULL,
    width      INTEGER,
    height     INTEGER,
    created_at TEXT    NOT NULL
);

-- 同一用户重复上传同一张图只存一份
CREATE UNIQUE INDEX IF NOT EXISTS idx_uploads_user_hash ON uploads(user_id, sha256);
"""


def database_path() -> str:
    """把 APP_DB_URL 解析成 sqlite 文件路径。"""
    url = settings.db_url
    if url.startswith("sqlite:///"):
        raw = url[len("sqlite:///") :]
    elif url.startswith("sqlite://"):
        raw = url[len("sqlite://") :]
    else:
        raise ValueError(f"只支持 sqlite:// 形式的数据库地址，收到：{url}")
    if raw in {":memory:", ""}:
        return ":memory:"
    path = Path(raw)
    if not path.is_absolute():
        # 相对路径固定相对 backend/ 目录，避免受启动时工作目录影响。
        path = Path(__file__).with_name(raw) if "/" not in raw and "\\" not in raw else Path(__file__).parent / raw
    path.parent.mkdir(parents=True, exist_ok=True)
    return str(path)


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(database_path(), timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


@contextmanager
def transaction() -> Iterator[sqlite3.Connection]:
    """写事务：先取写锁（BEGIN IMMEDIATE）。

    多语句改写（例如"迁移标签关联再删标签"）必须整体成功或整体回滚；
    延迟事务在并发下升级写锁可能失败，直接取写锁更稳。
    """
    conn = sqlite3.connect(database_path(), timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """幂等建表 + 前向迁移（SQLite 没有 ADD COLUMN IF NOT EXISTS）。"""
    with connect() as conn:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.executescript(SCHEMA)
    _migrate()


def _migrate() -> None:
    with connect() as conn:
        user_columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)")}
        if "assets_seeded_at" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN assets_seeded_at TEXT")

        project_columns = {row["name"] for row in conn.execute("PRAGMA table_info(projects)")}
        if "version" not in project_columns:
            # 老库补 version 列；ADD COLUMN 的常量默认值会把已有行一起填成 1
            conn.execute("ALTER TABLE projects ADD COLUMN version INTEGER NOT NULL DEFAULT 1")


# --------------------------------------------------------------------------- #
# 时间工具
# --------------------------------------------------------------------------- #


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def now_iso() -> str:
    return to_iso(utcnow()) or ""


def to_iso(value: datetime | None) -> str | None:
    return value.replace(microsecond=0).isoformat() if value else None


def from_iso(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def in_minutes(minutes: float) -> str:
    return to_iso(utcnow() + timedelta(minutes=minutes))  # type: ignore[return-value]


def in_hours(hours: float) -> str:
    return to_iso(utcnow() + timedelta(hours=hours))  # type: ignore[return-value]


def in_days(days: float) -> str:
    return to_iso(utcnow() + timedelta(days=days))  # type: ignore[return-value]
