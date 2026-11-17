"""ReCut Agent API。

路由层只负责 HTTP 语义：参数校验、状态码映射、临时资源清理。
业务逻辑在 storyboard.py / vision.py，认证在 auth.py，持久化在 repositories.py。

启动顺序：lifespan 里先建表，再对外服务。
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

import assets
import auth
import db
import deps
import exports
import media
import projects
import repositories
import security
import storyboard
import uploads
import vision
from config import settings
from deps import require_user
from errors import (
    AccountDisabled,
    AccountLocked,
    AppError,
    AuthenticationRequired,
    ConflictError,
    InvalidCredentials,
    MissingConfigError,
    UpstreamError,
    UploadRejected,
    ValidationRejected,
)
from schemas import (
    ExpandShotRequest,
    ExpandShotResponse,
    GenerateRequest,
    GenerateResponse,
    PlanResponse,
    RefineRequest,
    RefineResponse,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s [%(name)s] %(message)s")
logger = logging.getLogger("recut")

# 这些前缀必须先鉴权再读请求体：否则匿名请求也能把 50MB 素材传完才被拒绝。
PROTECTED_PREFIXES = (
    "/api/v1/storyboard",
    "/api/v1/projects",
    "/api/v1/characters",
    "/api/v1/tags",
    "/api/v1/uploads",
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init_db()
    logger.info("数据库就绪：%s", db.database_path())
    _bootstrap_admin()
    logger.info(
        "ReCut Agent API 启动 | LLM: %s (%s) | Vision: %s (%s)",
        "已配置" if settings.llm_ready else "未配置",
        settings.llm_model,
        "已配置" if settings.vision_ready else "未配置",
        settings.vision_model,
    )
    if not settings.llm_ready:
        logger.warning("未检测到 LLM_API_KEY：生成接口将返回 503，前端会保留演示分镜")
    yield


def _bootstrap_admin() -> None:
    """部署环境没有终端，用环境变量创建第一个管理员。

    只在库里**一个用户都没有**时生效，且账号密码必须由部署者显式提供，
    所以不会在本地误建账号。密码比较敏感，登录后应立刻在界面里改掉。
    """
    email = (os.getenv("AUTH_BOOTSTRAP_EMAIL") or "").strip()
    password = (os.getenv("AUTH_BOOTSTRAP_PASSWORD") or "").strip()
    if not email or not password:
        return
    if repositories.list_users():
        return

    problem = security.password_problem(password)
    if problem:
        logger.error("AUTH_BOOTSTRAP_PASSWORD 不合规，已跳过初始管理员创建：%s", problem)
        return

    repositories.create_user(
        email=email,
        password_hash=security.hash_password(password),
        display_name=(os.getenv("AUTH_BOOTSTRAP_NAME") or "管理员").strip(),
        role="admin",
    )
    logger.info("已创建初始管理员 %s，请登录后立即修改密码", email)


app = FastAPI(
    title="ReCut Agent API",
    description="AIGC video storyboard and prompt workspace API",
    version="0.3.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def auth_gate(request: Request, call_next):
    """在解析请求体之前拦掉未登录请求。

    FastAPI 会先读 body 再解依赖，所以上传接口靠依赖做鉴权会让匿名用户
    把整个文件传完才收到 401。这里提前挡一道，依赖层的校验仍然保留。
    """
    if request.method != "OPTIONS" and request.url.path.startswith(PROTECTED_PREFIXES):
        user = await run_in_threadpool(deps.current_user, request)
        if user is None:
            return JSONResponse(status_code=401, content={"detail": "请先登录"})
    return await call_next(request)


# CORS 最后添加 → 位于中间件栈最外层，401 响应也会带上跨域头。
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.allowed_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(assets.router)
app.include_router(uploads.router)
app.include_router(exports.router)


def _http_error(exc: AppError) -> HTTPException:
    """把业务异常映射成明确的状态码，前端据此给出可读提示。"""
    if isinstance(exc, (AuthenticationRequired, InvalidCredentials)):
        status = 401
    elif isinstance(exc, AccountLocked):
        status = 423
    elif isinstance(exc, AccountDisabled):
        status = 403
    elif isinstance(exc, ConflictError):
        status = 409
    elif isinstance(exc, (UploadRejected, ValidationRejected)):
        status = 422
    elif isinstance(exc, MissingConfigError):
        status = 503
    elif isinstance(exc, UpstreamError):
        status = 502
    else:
        status = 500
    return HTTPException(status_code=status, detail=str(exc))


@app.exception_handler(AppError)
async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    """依赖里抛出的异常（如 require_user）也要走同一套映射。

    带结构化信息的错误（标签被引用、版本冲突）会额外合并 payload，
    前端据此弹出"被谁引用"或"已被其他窗口修改"。
    """
    error = _http_error(exc)
    content: dict[str, object] = {"detail": error.detail}
    extra = exc.payload()
    if extra:
        content.update(extra)
    return JSONResponse(status_code=error.status_code, content=content)


@app.get("/api/health")
async def health() -> dict[str, object]:
    return {
        "status": "ok",
        "service": "recut-agent",
        "llm": "configured" if settings.llm_ready else "missing-key",
        "vision": "configured" if settings.vision_ready else "missing-key",
        "auth": "cookie-session",
    }


@app.post("/api/v1/storyboard/generate", response_model=GenerateResponse)
async def generate_storyboard(
    request: GenerateRequest, user=Depends(require_user)
) -> GenerateResponse:
    """创意 → 分镜脚本。"""
    try:
        shots = await storyboard.generate_shots(request)
    except AppError as exc:
        logger.warning("生成分镜失败（user=%s）：%s", user.id, exc)
        raise _http_error(exc) from exc
    logger.info("生成分镜成功：user=%s, %d 个镜头", user.id, len(shots))
    return GenerateResponse(shots=shots)


@app.post("/api/v1/storyboard/reverse", response_model=GenerateResponse)
async def reverse_storyboard(
    file: UploadFile = File(..., description="视频或图片素材"),
    model: Literal["即梦 Jimeng", "可灵 Kling", "Runway Gen-3"] = Form("即梦 Jimeng"),
    anchors: str = Form("", description="逗号分隔的角色一致性锚点"),
    user=Depends(require_user),
) -> GenerateResponse:
    """视频 / 图片 → 分镜脚本（关键帧理解 + 视听语言反推）。"""
    anchor_list = [item.strip() for item in anchors.replace("，", ",").split(",") if item.strip()]
    saved: media.SavedUpload | None = None
    try:
        saved = await media.save_upload(file)
        duration = media.probe_duration(media.ffmpeg_exe(), saved.path) if saved.is_video else None
        frames = media.extract_keyframes(saved)
        context = media.describe_frames(len(frames), duration)
        shots = await vision.analyze_frames(frames, anchor_list, model, context=context)
    except AppError as exc:
        logger.warning("解析素材失败（user=%s）：%s", user.id, exc)
        raise _http_error(exc) from exc
    finally:
        if saved is not None:
            saved.cleanup()
    logger.info("解析素材成功：user=%s, %d 个镜头", user.id, len(shots))
    return GenerateResponse(shots=shots)


@app.post("/api/v1/storyboard/plan", response_model=PlanResponse)
async def plan_storyboard(
    request: GenerateRequest, user=Depends(require_user)
) -> PlanResponse:
    """B4 阶段一：只生成镜头计划（不含提示词）。"""
    try:
        plan = await storyboard.plan_story(request)
    except AppError as exc:
        logger.warning("生成镜头计划失败（user=%s）：%s", user.id, exc)
        raise _http_error(exc) from exc
    logger.info("镜头计划成功：user=%s, %d 镜 / %ds", user.id, len(plan.shots), plan.total_seconds)
    return PlanResponse(plan=plan)


@app.post("/api/v1/storyboard/shot", response_model=ExpandShotResponse)
async def expand_storyboard_shot(
    payload: ExpandShotRequest, user=Depends(require_user)
) -> ExpandShotResponse:
    """B4 阶段二：把计划中的某一镜展开成完整分镜（前端并发调用）。"""
    try:
        shot = await storyboard.expand_shot(payload)
    except AppError as exc:
        logger.warning("展开第 %s 镜失败（user=%s）：%s", payload.index, user.id, exc)
        raise _http_error(exc) from exc
    return ExpandShotResponse(shot=shot)


@app.post("/api/v1/storyboard/refine", response_model=RefineResponse)
async def refine_storyboard_shot(
    payload: RefineRequest, user=Depends(require_user)
) -> RefineResponse:
    """B1：按指令改写单镜，返回候选（不落库，由前端确认后写回）。"""
    try:
        shot = await storyboard.refine_shot(payload)
    except AppError as exc:
        logger.warning("镜头微调失败（user=%s）：%s", user.id, exc)
        raise _http_error(exc) from exc
    return RefineResponse(shot=shot)


# --------------------------------------------------------------------------- #
# 生产环境：同一个容器同时提供前端静态文件
# --------------------------------------------------------------------------- #
# 必须挂载在根路径，前端才能和 /api 同源——登录 cookie 才不需要跨站配置。
# 放在所有路由之后注册，Starlette 按注册顺序匹配，不会遮蔽 /api 接口。
# 本地开发时 frontend/dist 通常不存在（或已过期），此段自动跳过，开发流程不变。
_FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"

if (_FRONTEND_DIST / "index.html").is_file():
    app.mount("/", StaticFiles(directory=str(_FRONTEND_DIST), html=True), name="frontend")
    logger.info("已挂载前端静态目录：%s", _FRONTEND_DIST)
else:
    logger.warning("未找到 frontend/dist：根路径不提供页面，只提供 /api")

    @app.get("/", include_in_schema=False)
    def _root_without_frontend() -> dict[str, str]:
        """没有前端产物时给一句人话，而不是让访问者看到一个裸的 404。"""
        return {
            "service": "recut-agent",
            "detail": "前端产物未找到（frontend/dist/index.html），当前仅提供 API",
            "health": "/api/health",
        }
