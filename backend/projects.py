"""项目持久化：每个用户只能看到自己的项目。

归属校验方式：所有查询都带 `user_id = 当前用户`，别人的项目一律返回 404
（而不是 403），避免用状态码探测某个 id 是否存在。
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

import repositories as repo
from deps import require_user

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])

# 故事板正文（含提示词）单个项目上限，防止用超大 JSON 拖垮服务。
MAX_STORYBOARD_BYTES = 512 * 1024


class ProjectCreate(BaseModel):
    name: str = Field(default="未命名项目", min_length=1, max_length=80)
    storyboard: dict[str, Any] | None = None


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    storyboard: dict[str, Any] | None = None
    # 传了就做乐观锁：版本不匹配返回 409 并带上 current_version
    expected_version: int | None = Field(default=None, ge=1)


def _check_storyboard(storyboard: dict[str, Any] | None) -> None:
    if storyboard is None:
        return
    encoded = json.dumps(storyboard, ensure_ascii=False)
    if len(encoded.encode("utf-8")) > MAX_STORYBOARD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"项目数据超过 {MAX_STORYBOARD_BYTES // 1024}KB 上限",
        )


def _load(user_id: int, project_id: int) -> repo.Project:
    project = repo.get_project(user_id, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    return project


@router.get("")
def list_projects(user=Depends(require_user)) -> dict[str, Any]:
    return {"projects": repo.list_projects(user.id)}


@router.post("", status_code=201)
def create_project(payload: ProjectCreate, user=Depends(require_user)) -> dict[str, Any]:
    _check_storyboard(payload.storyboard)
    project = repo.create_project(user.id, payload.name.strip(), payload.storyboard)
    return project.detail()


@router.get("/{project_id}")
def get_project(project_id: int, user=Depends(require_user)) -> dict[str, Any]:
    return _load(user.id, project_id).detail()


@router.put("/{project_id}")
def update_project(
    project_id: int, payload: ProjectUpdate, user=Depends(require_user)
) -> dict[str, Any]:
    _load(user.id, project_id)
    _check_storyboard(payload.storyboard)
    name = payload.name.strip() if payload.name is not None else None
    project = repo.update_project(
        user.id,
        project_id,
        name=name,
        storyboard=payload.storyboard,
        expected_version=payload.expected_version,
    )
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    return project.detail()


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: int, user=Depends(require_user)) -> None:
    if not repo.delete_project(user.id, project_id):
        raise HTTPException(status_code=404, detail="项目不存在")
    return None
