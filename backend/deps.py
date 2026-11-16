"""鉴权依赖：读取会话 cookie、解析当前用户、校验跨站来源。

同步函数：FastAPI 会把它们放进线程池，sqlite 的同步查询不会阻塞事件循环。
"""

from __future__ import annotations

from datetime import timedelta

from fastapi import Depends, HTTPException, Request

import db
import repositories
import security
from config import settings
from errors import AuthenticationRequired

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def verify_origin(request: Request) -> None:
    """Cookie 鉴权的补充防线。

    `SameSite=Lax` 已经挡住跨站表单提交；这里再加一道 Origin 校验，
    防止将来把 SameSite 调成 None 时被 CSRF 利用。
    没有 Origin 头的请求（curl、同源导航）放行。
    """
    if request.method in SAFE_METHODS:
        return
    origin = (request.headers.get("origin") or "").rstrip("/")
    if not origin:
        return
    if origin not in {item.rstrip("/") for item in settings.allowed_origins}:
        raise HTTPException(status_code=403, detail="请求来源不被允许")


def session_token(request: Request) -> str | None:
    return request.cookies.get(settings.session_cookie)


def current_user(request: Request) -> repositories.User | None:
    """返回当前用户；未登录返回 None（不抛异常，便于 /me 做软判断）。"""
    token = session_token(request)
    if not token:
        return None
    digest = security.token_digest(token)
    user = repositories.session_user(digest)
    if user is None:
        return None
    _slide(digest)
    return user


def _slide(digest: str) -> None:
    """滑动续期：只在剩余寿命不足一半时推进，避免每个请求都写库。"""
    if not settings.session_sliding:
        return
    info = repositories.session_info(digest)
    if not info:
        return
    ttl = (
        timedelta(days=settings.session_remember_days)
        if info["remember"]
        else timedelta(hours=settings.session_ttl_hours)
    )
    expires_at = db.from_iso(info["expires_at"])
    if expires_at is None:
        return
    if expires_at - db.utcnow() < ttl / 2:
        repositories.touch_session(digest, extend_to=db.to_iso(db.utcnow() + ttl))


def require_user(user: repositories.User | None = Depends(current_user)) -> repositories.User:
    if user is None:
        raise AuthenticationRequired("请先登录")
    return user


def require_admin(user: repositories.User = Depends(require_user)) -> repositories.User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user
