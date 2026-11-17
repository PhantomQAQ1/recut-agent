"""工作区数据的导出 / 导入。

为什么需要它：数据库（`*.db`）和上传目录都在 `.gitignore` / `.dockerignore` 里，
不会随代码上传，所以本地和部署环境是两套完全独立的数据。
这条通道让用户能把本地的项目、角色、标签搬到另一个实例（反之亦然）。

只搬结构化数据，不含密码哈希；参考首帧图片不包含（需要重新上传）。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

import assets_repo as assets
import db
import repositories as repo
from deps import require_user, verify_origin
from errors import AppError, ValidationRejected

router = APIRouter(
    prefix="/api/v1/data",
    tags=["data"],
    dependencies=[Depends(verify_origin)],
)

EXPORT_VERSION = 1


class ImportResult(BaseModel):
    created_projects: int
    created_characters: int
    created_tags: int
    skipped_projects: list[str] = []
    skipped_characters: list[str] = []


def _character_payload(character: assets.Character) -> dict[str, Any]:
    return {
        "name": character.name,
        "role_label": character.role_label,
        "description": character.description,
        "prompt_anchor": character.prompt_anchor,
        "tone": character.tone,
        "tags": [tag.name for tag in character.tags],
    }


@router.get("/export")
def export_data(user=Depends(require_user)) -> dict[str, Any]:
    """当前用户的全部项目、角色、标签。"""
    projects: list[dict[str, Any]] = []
    for summary in repo.list_projects(user.id):
        full = repo.get_project(user.id, int(summary["id"]))
        if full is not None:
            projects.append({"name": full.name, "storyboard": full.storyboard})
    return {
        "version": EXPORT_VERSION,
        "exported_at": db.now_iso(),
        "email": user.email,
        "projects": projects,
        "characters": [_character_payload(item) for item in assets.list_characters(user.id)],
        "tags": [
            {"name": tag.name, "category": tag.category, "tone": tag.tone}
            for tag in assets.list_tags(user.id)
        ],
    }


@router.post("/import", response_model=ImportResult)
def import_data(payload: dict[str, Any], user=Depends(require_user)) -> ImportResult:
    """把导出的 JSON 合并进当前账号。

    同名项目/角色会跳过（不覆盖、不重复），返回里会列出被跳过的名字。
    """
    if payload.get("version") != EXPORT_VERSION:
        raise ValidationRejected(f"不支持的数据版本，需要 version={EXPORT_VERSION}")

    tags_in = payload.get("tags") or []
    characters_in = payload.get("characters") or []
    projects_in = payload.get("projects") or []
    if not isinstance(tags_in, list) or not isinstance(characters_in, list) or not isinstance(projects_in, list):
        raise ValidationRejected("数据格式不正确")

    # 1) 标签：按归一化名字去重，已存在就复用
    tag_ids: dict[str, int] = {}
    created_tags = 0
    for item in tags_in:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        try:
            tag, created = assets.create_tag(
                user.id,
                name=name,
                category=str(item.get("category") or "character"),
                tone=str(item.get("tone") or "neutral"),
            )
        except AppError:
            continue
        tag_ids[assets.normalize_key(name)] = tag.id
        created_tags += int(created)

    # 2) 角色：同名跳过
    existing_characters = {assets.normalize_key(item.name) for item in assets.list_characters(user.id)}
    created_characters = 0
    skipped_characters: list[str] = []
    for item in characters_in:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        key = assets.normalize_key(name)
        if key in existing_characters:
            skipped_characters.append(name)
            continue
        tag_names = [str(tag).strip() for tag in (item.get("tags") or [])]
        linked = [tag_ids[assets.normalize_key(tag)] for tag in tag_names if assets.normalize_key(tag) in tag_ids]
        try:
            assets.create_character(
                user.id,
                name=name,
                role_label=str(item.get("role_label") or "")[:80],
                description=str(item.get("description") or "")[:500],
                prompt_anchor=str(item.get("prompt_anchor") or "")[:500],
                tone=str(item.get("tone") or "amber"),
                tag_ids=linked,
            )
        except AppError:
            continue
        existing_characters.add(key)
        created_characters += 1

    # 3) 项目：同名的跳过
    existing_projects = {str(item["name"]) for item in repo.list_projects(user.id)}
    created_projects = 0
    skipped_projects: list[str] = []
    for item in projects_in:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip() or "未命名项目"
        if name in existing_projects:
            skipped_projects.append(name)
            continue
        storyboard = item.get("storyboard")
        if not isinstance(storyboard, dict):
            storyboard = {}
        repo.create_project(user.id, name[:80], storyboard)
        existing_projects.add(name)
        created_projects += 1

    return ImportResult(
        created_projects=created_projects,
        created_characters=created_characters,
        created_tags=created_tags,
        skipped_projects=skipped_projects,
        skipped_characters=skipped_characters,
    )
