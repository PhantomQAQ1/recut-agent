"""应用级异常，用于在路由层映射成明确的 HTTP 状态码。"""

from __future__ import annotations

from typing import Any


class AppError(RuntimeError):
    """所有可预期的业务错误的基类。"""

    def payload(self) -> dict[str, Any] | None:
        """需要随错误一起返回给前端的结构化信息（默认无）。"""
        return None


class MissingConfigError(AppError):
    """缺少 API Key 等必要配置 → 503。"""


class UpstreamError(AppError):
    """模型服务不可用或返回不可用结果 → 502。"""


class UploadRejected(AppError):
    """用户上传的素材不合法 → 422。"""


class ValidationRejected(AppError):
    """请求内容不满足业务规则（如密码过短）→ 422。"""


class ConflictError(AppError):
    """资源冲突（如邮箱已存在）→ 409。"""


class VersionConflictError(ConflictError):
    """乐观锁版本不匹配：别处已经改过这条记录 → 409。

    带上当前版本号，前端可以据此提示"已被其他窗口修改"并刷新。
    """

    def __init__(self, message: str, current_version: int):
        super().__init__(message)
        self.current_version = current_version

    def payload(self) -> dict[str, Any]:
        return {"current_version": self.current_version}


class TagInUseError(ConflictError):
    """标签仍被角色引用 → 409，并返回引用者供前端确认。"""

    def __init__(self, message: str, used_by: list[dict[str, Any]]):
        super().__init__(message)
        self.used_by = used_by

    def payload(self) -> dict[str, Any]:
        return {"used_by": self.used_by}


class AuthenticationRequired(AppError):
    """未登录或会话已失效 → 401。"""


class InvalidCredentials(AppError):
    """邮箱或密码不正确 → 401（与未登录同一状态码，避免枚举）。"""


class AccountLocked(AppError):
    """连续失败触发临时锁定 → 423。"""


class AccountDisabled(AppError):
    """账号被管理员停用 → 403。"""
