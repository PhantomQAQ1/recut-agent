"""数据访问：用户、会话、登录审计、项目。

所有函数都是同步的（sqlite3 本地文件，单次查询微秒级）。
路由层用 `def` 定义，FastAPI 会自动放进线程池执行，不阻塞事件循环。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import db
from errors import ConflictError


@dataclass(frozen=True)
class User:
    id: int
    email: str
    password_hash: str
    display_name: str
    role: str
    status: str
    failed_attempts: int
    locked_until: datetime | None
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime

    def public(self) -> dict[str, Any]:
        """可以安全返回给前端的字段；绝不包含哈希。"""
        return {
            "id": self.id,
            "email": self.email,
            "display_name": self.display_name,
            "role": self.role,
        }

    def is_locked(self, now: datetime | None = None) -> bool:
        if not self.locked_until:
            return False
        return self.locked_until > (now or db.utcnow())

    @property
    def is_disabled(self) -> bool:
        return self.status != "active"


@dataclass(frozen=True)
class Project:
    id: int
    user_id: int
    name: str
    storyboard: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    def summary(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "updated_at": db.to_iso(self.updated_at),
        }

    def detail(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "storyboard": self.storyboard,
            "created_at": db.to_iso(self.created_at),
            "updated_at": db.to_iso(self.updated_at),
        }


def _user_from_row(row) -> User:
    return User(
        id=row["id"],
        email=row["email"],
        password_hash=row["password_hash"],
        display_name=row["display_name"],
        role=row["role"],
        status=row["status"],
        failed_attempts=row["failed_attempts"],
        locked_until=db.from_iso(row["locked_until"]),
        last_login_at=db.from_iso(row["last_login_at"]),
        created_at=db.from_iso(row["created_at"]) or db.utcnow(),
        updated_at=db.from_iso(row["updated_at"]) or db.utcnow(),
    )


def _project_from_row(row) -> Project:
    try:
        storyboard = json.loads(row["storyboard"] or "{}")
    except json.JSONDecodeError:
        storyboard = {}
    return Project(
        id=row["id"],
        user_id=row["user_id"],
        name=row["name"],
        storyboard=storyboard if isinstance(storyboard, dict) else {},
        created_at=db.from_iso(row["created_at"]) or db.utcnow(),
        updated_at=db.from_iso(row["updated_at"]) or db.utcnow(),
    )


# --------------------------------------------------------------------------- #
# 用户
# --------------------------------------------------------------------------- #


def normalize_email(email: str) -> str:
    return email.strip().lower()


def create_user(
    *,
    email: str,
    password_hash: str,
    display_name: str,
    role: str = "member",
) -> User:
    normalized = normalize_email(email)
    now = db.now_iso()
    try:
        with db.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO users (email, password_hash, display_name, role, status,
                                   failed_attempts, created_at, updated_at)
                VALUES (?, ?, ?, ?, 'active', 0, ?, ?)
                """,
                (normalized, password_hash, display_name, role, now, now),
            )
            user_id = int(cursor.lastrowid)
    except Exception as exc:  # sqlite3.IntegrityError，但避免上层依赖 sqlite3
        if "UNIQUE" in str(exc):
            raise ConflictError(f"邮箱 {normalized} 已存在") from exc
        raise
    user = get_user(user_id)
    assert user is not None
    return user


def get_user(user_id: int) -> User | None:
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return _user_from_row(row) if row else None


def get_user_by_email(email: str) -> User | None:
    with db.connect() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE email = ?", (normalize_email(email),)
        ).fetchone()
    return _user_from_row(row) if row else None


def list_users() -> list[User]:
    with db.connect() as conn:
        rows = conn.execute("SELECT * FROM users ORDER BY id").fetchall()
    return [_user_from_row(row) for row in rows]


def set_status(user_id: int, status: str) -> bool:
    with db.connect() as conn:
        cursor = conn.execute(
            "UPDATE users SET status = ?, updated_at = ? WHERE id = ?",
            (status, db.now_iso(), user_id),
        )
        return cursor.rowcount > 0


def set_password(user_id: int, password_hash: str) -> bool:
    with db.connect() as conn:
        cursor = conn.execute(
            """
            UPDATE users
               SET password_hash = ?, failed_attempts = 0, locked_until = NULL, updated_at = ?
             WHERE id = ?
            """,
            (password_hash, db.now_iso(), user_id),
        )
        return cursor.rowcount > 0


def register_failure(user_id: int, *, max_attempts: int, lockout_minutes: int) -> User | None:
    """记一次失败；达到阈值就上锁并把计数清零（解锁后重新获得完整配额）。"""
    with db.connect() as conn:
        row = conn.execute(
            "SELECT failed_attempts FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if row is None:
            return None
        attempts = int(row["failed_attempts"]) + 1
        if attempts >= max_attempts:
            conn.execute(
                """
                UPDATE users
                   SET failed_attempts = 0,
                       locked_until = ?,
                       updated_at = ?
                 WHERE id = ?
                """,
                (db.in_minutes(lockout_minutes), db.now_iso(), user_id),
            )
        else:
            conn.execute(
                "UPDATE users SET failed_attempts = ?, updated_at = ? WHERE id = ?",
                (attempts, db.now_iso(), user_id),
            )
    return get_user(user_id)


def mark_login_success(user_id: int) -> None:
    now = db.now_iso()
    with db.connect() as conn:
        conn.execute(
            """
            UPDATE users
               SET failed_attempts = 0, locked_until = NULL, last_login_at = ?, updated_at = ?
             WHERE id = ?
            """,
            (now, now, user_id),
        )


def unlock_user(user_id: int) -> bool:
    with db.connect() as conn:
        cursor = conn.execute(
            """
            UPDATE users
               SET failed_attempts = 0, locked_until = NULL, updated_at = ?
             WHERE id = ?
            """,
            (db.now_iso(), user_id),
        )
        return cursor.rowcount > 0


# --------------------------------------------------------------------------- #
# 登录审计
# --------------------------------------------------------------------------- #


def record_attempt(*, email: str | None, ip: str | None, success: bool, reason: str) -> None:
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO login_attempts (email, ip, success, reason, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                normalize_email(email) if email else None,
                ip,
                1 if success else 0,
                reason,
                db.now_iso(),
            ),
        )


# --------------------------------------------------------------------------- #
# 会话
# --------------------------------------------------------------------------- #


def create_session(
    *,
    digest: str,
    user_id: int,
    expires_at: str,
    remember: bool,
    ip: str | None,
    user_agent: str | None,
) -> None:
    now = db.now_iso()
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO sessions (id, user_id, remember, created_at, expires_at,
                                  last_seen_at, ip, user_agent, revoked_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL)
            """,
            (
                digest,
                user_id,
                1 if remember else 0,
                now,
                expires_at,
                now,
                ip,
                (user_agent or "")[:300] or None,
            ),
        )


def session_user(digest: str) -> User | None:
    """校验会话并返回用户；过期、已吊销、账号禁用都视为未登录。"""
    now = db.now_iso()
    with db.connect() as conn:
        row = conn.execute(
            """
            SELECT u.* FROM sessions s
              JOIN users u ON u.id = s.user_id
             WHERE s.id = ?
               AND s.revoked_at IS NULL
               AND s.expires_at > ?
               AND u.status = 'active'
            """,
            (digest, now),
        ).fetchone()
    return _user_from_row(row) if row else None


def touch_session(digest: str, *, extend_to: str | None) -> None:
    """滑动续期：只在开启 APP_SESSION_SLIDING 时推进 expires_at。"""
    now = db.now_iso()
    with db.connect() as conn:
        if extend_to:
            conn.execute(
                "UPDATE sessions SET last_seen_at = ?, expires_at = ? WHERE id = ? AND revoked_at IS NULL",
                (now, extend_to, digest),
            )
        else:
            conn.execute(
                "UPDATE sessions SET last_seen_at = ? WHERE id = ? AND revoked_at IS NULL",
                (now, digest),
            )


def revoke_session(digest: str) -> None:
    with db.connect() as conn:
        conn.execute(
            "UPDATE sessions SET revoked_at = ? WHERE id = ? AND revoked_at IS NULL",
            (db.now_iso(), digest),
        )


def revoke_user_sessions(user_id: int, *, keep: str | None = None) -> int:
    now = db.now_iso()
    with db.connect() as conn:
        if keep:
            cursor = conn.execute(
                """
                UPDATE sessions SET revoked_at = ?
                 WHERE user_id = ? AND id <> ? AND revoked_at IS NULL
                """,
                (now, user_id, keep),
            )
        else:
            cursor = conn.execute(
                """
                UPDATE sessions SET revoked_at = ?
                 WHERE user_id = ? AND revoked_at IS NULL
                """,
                (now, user_id),
            )
        return cursor.rowcount


def purge_expired_sessions() -> int:
    with db.connect() as conn:
        cursor = conn.execute("DELETE FROM sessions WHERE expires_at <= ?", (db.now_iso(),))
        return cursor.rowcount


def session_info(digest: str) -> dict[str, Any] | None:
    with db.connect() as conn:
        row = conn.execute(
            "SELECT remember, expires_at, created_at FROM sessions WHERE id = ? AND revoked_at IS NULL",
            (digest,),
        ).fetchone()
    if row is None:
        return None
    return {
        "remember": bool(row["remember"]),
        "expires_at": row["expires_at"],
        "created_at": row["created_at"],
    }


# --------------------------------------------------------------------------- #
# 项目
# --------------------------------------------------------------------------- #


def create_project(user_id: int, name: str, storyboard: dict[str, Any] | None = None) -> Project:
    now = db.now_iso()
    payload = json.dumps(storyboard or {}, ensure_ascii=False)
    with db.connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO projects (user_id, name, storyboard, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, name, payload, now, now),
        )
        project_id = int(cursor.lastrowid)
    project = get_project(user_id, project_id)
    assert project is not None
    return project


def list_projects(user_id: int) -> list[dict[str, Any]]:
    """只返回摘要：故事板正文可能很大，列表页不需要。"""
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT id, name, updated_at FROM projects WHERE user_id = ? ORDER BY updated_at DESC",
            (user_id,),
        ).fetchall()
    return [{"id": row["id"], "name": row["name"], "updated_at": row["updated_at"]} for row in rows]


def get_project(user_id: int, project_id: int) -> Project | None:
    with db.connect() as conn:
        row = conn.execute(
            "SELECT * FROM projects WHERE id = ? AND user_id = ?",
            (project_id, user_id),
        ).fetchone()
    return _project_from_row(row) if row else None


def update_project(
    user_id: int,
    project_id: int,
    *,
    name: str | None = None,
    storyboard: dict[str, Any] | None = None,
) -> Project | None:
    assignments: list[str] = []
    values: list[Any] = []
    if name is not None:
        assignments.append("name = ?")
        values.append(name)
    if storyboard is not None:
        assignments.append("storyboard = ?")
        values.append(json.dumps(storyboard, ensure_ascii=False))
    if not assignments:
        return get_project(user_id, project_id)

    assignments.append("updated_at = ?")
    values.append(db.now_iso())
    values.extend([project_id, user_id])

    with db.connect() as conn:
        cursor = conn.execute(
            f"UPDATE projects SET {', '.join(assignments)} WHERE id = ? AND user_id = ?",
            values,
        )
        if cursor.rowcount == 0:
            return None
    return get_project(user_id, project_id)


def delete_project(user_id: int, project_id: int) -> bool:
    with db.connect() as conn:
        cursor = conn.execute(
            "DELETE FROM projects WHERE id = ? AND user_id = ?", (project_id, user_id)
        )
        return cursor.rowcount > 0
