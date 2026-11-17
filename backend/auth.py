"""认证路由：登录、登出、当前用户、修改密码。

注册**不开放**：账号由管理员用 `python -m scripts.manage_user create` 创建。
找回密码 / 邮箱验证留到下一期。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

import db
import repositories as repo
import security
from config import settings
from deps import client_ip, require_user, session_token, verify_origin
from errors import (
    AccountDisabled,
    AccountLocked,
    InvalidCredentials,
    ValidationRejected,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

# 未注册与密码错误必须返回同一句话，否则可以用来枚举邮箱。
GENERIC_CREDENTIALS_ERROR = "邮箱或密码不正确"


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)
    remember: bool = False


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=1, max_length=256)


class SetupRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)
    display_name: str | None = Field(default=None, max_length=40)


def set_session_cookie(response: Response, token: str, *, remember: bool) -> None:
    """记住我 → 带 Max-Age 的持久 cookie；否则是浏览器会话 cookie。

    服务端另有硬过期时间（12 小时或 30 天），不依赖浏览器是否遵守 cookie 规则。
    """
    response.set_cookie(
        key=settings.session_cookie,
        value=token,
        max_age=settings.session_remember_days * 86400 if remember else None,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,  # type: ignore[arg-type]
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.session_cookie,
        path="/",
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,  # type: ignore[arg-type]
    )


def _locked_message() -> str:
    return f"账号已被临时锁定，请 {settings.lockout_minutes} 分钟后再试，或联系管理员解锁"


@router.get("/bootstrap")
def bootstrap_status() -> dict[str, object]:
    """前端据此决定显示"登录"还是"创建管理员"。"""
    return {"initialized": bool(repo.list_users())}


@router.post("/setup", status_code=201, dependencies=[Depends(verify_origin)])
def setup(payload: SetupRequest, request: Request, response: Response) -> dict[str, object]:
    """创建**第一个**管理员。

    只在库里一个账号都没有时可用；一旦有账号就永久关闭（返回 409），
    避免部署后被人抢先注册。建完直接返回登录态，省掉再登一次。
    """
    if repo.list_users():
        raise HTTPException(status_code=409, detail="系统已初始化，无法再次创建管理员")

    problem = security.password_problem(payload.password)
    if problem:
        raise ValidationRejected(problem)

    email = repo.normalize_email(payload.email)
    if "@" not in email:
        raise ValidationRejected("邮箱格式不正确")

    user = repo.create_user(
        email=email,
        password_hash=security.hash_password(payload.password),
        display_name=(payload.display_name or "管理员").strip() or "管理员",
        role="admin",
    )

    token = security.new_session_token()
    digest = security.token_digest(token)
    expires_at = db.in_hours(settings.session_ttl_hours)
    ip = client_ip(request)
    repo.create_session(
        digest=digest,
        user_id=user.id,
        expires_at=expires_at,
        remember=False,
        ip=ip,
        user_agent=request.headers.get("user-agent"),
    )
    repo.record_attempt(email=email, ip=ip, success=True, reason="setup")
    set_session_cookie(response, token, remember=False)
    return {"user": user.public(), "expires_at": expires_at}


@router.post("/login", dependencies=[Depends(verify_origin)])
def login(payload: LoginRequest, request: Request, response: Response) -> dict[str, object]:
    email = repo.normalize_email(payload.email)
    ip = client_ip(request)
    user_agent = request.headers.get("user-agent")

    user = repo.get_user_by_email(email)
    if user is None:
        # 对不存在的账号也跑一次同代价的哈希校验，抹平响应时间差异。
        security.verify_password(payload.password, security.DUMMY_HASH)
        repo.record_attempt(email=email, ip=ip, success=False, reason="unknown_user")
        raise InvalidCredentials(GENERIC_CREDENTIALS_ERROR)

    if user.is_disabled:
        repo.record_attempt(email=email, ip=ip, success=False, reason="disabled")
        raise AccountDisabled("账号已被停用，请联系管理员")

    if user.is_locked():
        repo.record_attempt(email=email, ip=ip, success=False, reason="locked")
        raise AccountLocked(_locked_message())

    if not security.verify_password(payload.password, user.password_hash):
        updated = repo.register_failure(
            user.id,
            max_attempts=settings.max_login_attempts,
            lockout_minutes=settings.lockout_minutes,
        )
        repo.record_attempt(email=email, ip=ip, success=False, reason="bad_password")
        if updated is not None and updated.is_locked():
            raise AccountLocked(_locked_message())
        raise InvalidCredentials(GENERIC_CREDENTIALS_ERROR)

    token = security.new_session_token()
    digest = security.token_digest(token)
    expires_at = (
        db.in_days(settings.session_remember_days)
        if payload.remember
        else db.in_hours(settings.session_ttl_hours)
    )
    repo.purge_expired_sessions()
    repo.create_session(
        digest=digest,
        user_id=user.id,
        expires_at=expires_at,
        remember=payload.remember,
        ip=ip,
        user_agent=user_agent,
    )
    repo.mark_login_success(user.id)
    repo.record_attempt(email=email, ip=ip, success=True, reason="ok")

    set_session_cookie(response, token, remember=payload.remember)
    return {
        "user": user.public(),
        "expires_at": expires_at,
        "remember": payload.remember,
    }


@router.post("/logout", status_code=204, dependencies=[Depends(verify_origin)])
def logout(request: Request, response: Response, user=Depends(require_user)) -> Response:
    token = session_token(request)
    if token:
        repo.revoke_session(security.token_digest(token))
    clear_session_cookie(response)
    response.status_code = 204
    return response


@router.get("/me")
def me(user=Depends(require_user)) -> dict[str, object]:
    return {"user": user.public()}


@router.post("/password", status_code=204, dependencies=[Depends(verify_origin)])
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    response: Response,
    user=Depends(require_user),
) -> Response:
    if not security.verify_password(payload.current_password, user.password_hash):
        raise InvalidCredentials("当前密码不正确")

    problem = security.password_problem(payload.new_password)
    if problem:
        raise ValidationRejected(problem)
    if payload.current_password == payload.new_password:
        raise ValidationRejected("新密码不能与当前密码相同")

    repo.set_password(user.id, security.hash_password(payload.new_password))
    # 改密后踢掉其他设备，只保留当前会话。
    token = session_token(request)
    keep = security.token_digest(token) if token else None
    repo.revoke_user_sessions(user.id, keep=keep)
    response.status_code = 204
    return response
