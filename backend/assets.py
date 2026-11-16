"""角色资产与标签的 HTTP 接口。

所有路由都要求登录；归属过滤在 assets_repo 里完成，
别人的资产一律返回 404（不用 403，避免用状态码探测 id 是否存在）。
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field

import assets_repo as repo
import deps

router = APIRouter(
    prefix="/api/v1",
    tags=["assets"],
    dependencies=[Depends(deps.verify_origin)],
)

Tone = Literal["amber", "violet", "rose", "indigo", "neutral"]
Category = Literal["character", "emotion", "palette", "lighting", "appearance"]


# --------------------------------------------------------------------------- #
# 出入参
# --------------------------------------------------------------------------- #


class TagOut(BaseModel):
    id: int
    name: str
    category: str
    tone: str
    usage_count: int = 0


class TagCreatedOut(TagOut):
    """创建标签的返回：`created=false` 表示重名复用，前端据此提示用户。"""

    created: bool


class CharacterOut(BaseModel):
    id: int
    name: str
    role_label: str
    description: str
    consistency: float | None
    prompt_anchor: str
    tone: str
    version: int
    tags: list[TagOut]
    created_at: str
    updated_at: str


class CharacterCreate(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    role_label: str = ""
    description: str = ""
    prompt_anchor: str = ""
    tone: Tone = "amber"
    tag_ids: list[int] = Field(default_factory=list)


class CharacterUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=40)
    role_label: str | None = None
    description: str | None = None
    prompt_anchor: str | None = None
    tone: Tone | None = None
    expected_version: int | None = None
    # consistency 本轮不开放编辑：等接入真实比对算法后再由后台写入。


class CharacterTagsPatch(BaseModel):
    add: list[int] = Field(default_factory=list)
    remove: list[int] = Field(default_factory=list)


class CharacterTagsReplace(BaseModel):
    tag_ids: list[int]
    expected_version: int


class TagCreate(BaseModel):
    name: str = Field(min_length=1, max_length=24)
    category: Category
    tone: Tone = "neutral"


class TagUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=24)
    category: Category | None = None
    tone: Tone | None = None


def _character(user_id: int, character_id: int) -> dict[str, Any]:
    character = repo.get_character(user_id, character_id)
    if character is None:
        raise HTTPException(status_code=404, detail="角色不存在")
    return character.public()


def _tag(user_id: int, tag_id: int) -> dict[str, Any]:
    tag = repo.get_tag(user_id, tag_id)
    if tag is None:
        raise HTTPException(status_code=404, detail="标签不存在")
    return tag.public()


# --------------------------------------------------------------------------- #
# 角色
# --------------------------------------------------------------------------- #


@router.get("/characters", response_model=list[CharacterOut])
def list_characters(
    q: str | None = Query(default=None, max_length=80),
    tag_id: int | None = None,
    category: Category | None = None,
    user=Depends(deps.require_user),
) -> list[dict[str, Any]]:
    repo.ensure_seeded(user.id)
    characters = repo.list_characters(user.id, query=q, tag_id=tag_id, category=category)
    return [character.public() for character in characters]


@router.post("/characters", response_model=CharacterOut, status_code=201)
def create_character(payload: CharacterCreate, user=Depends(deps.require_user)):
    character = repo.create_character(
        user.id,
        name=payload.name,
        role_label=payload.role_label,
        description=payload.description,
        prompt_anchor=payload.prompt_anchor,
        tone=payload.tone,
        tag_ids=payload.tag_ids,
    )
    return character.public()


@router.get("/characters/{character_id}", response_model=CharacterOut)
def get_character(character_id: int, user=Depends(deps.require_user)):
    return _character(user.id, character_id)


@router.patch("/characters/{character_id}", response_model=CharacterOut)
def update_character(
    character_id: int, payload: CharacterUpdate, user=Depends(deps.require_user)
):
    updated = repo.update_character(
        user.id,
        character_id,
        name=payload.name,
        role_label=payload.role_label,
        description=payload.description,
        prompt_anchor=payload.prompt_anchor,
        tone=payload.tone,
        expected_version=payload.expected_version,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="角色不存在")
    return updated.public()


@router.delete("/characters/{character_id}", status_code=204)
def delete_character(character_id: int, user=Depends(deps.require_user)) -> None:
    if not repo.delete_character(user.id, character_id):
        raise HTTPException(status_code=404, detail="角色不存在")
    return None


@router.patch("/characters/{character_id}/tags", response_model=CharacterOut)
def patch_character_tags(
    character_id: int, payload: CharacterTagsPatch, user=Depends(deps.require_user)
):
    """增量打标：天然可合并、幂等，两个窗口各自加标签不会互相覆盖。"""
    updated: Any = None
    if payload.add:
        updated = repo.add_character_tags(user.id, character_id, payload.add)
        if updated is None:
            raise HTTPException(status_code=404, detail="角色不存在")
    if payload.remove:
        updated = repo.remove_character_tags(user.id, character_id, payload.remove)
        if updated is None:
            raise HTTPException(status_code=404, detail="角色不存在")
    if updated is None:
        updated = repo.get_character(user.id, character_id)
        if updated is None:
            raise HTTPException(status_code=404, detail="角色不存在")
    return updated.public()


@router.put("/characters/{character_id}/tags", response_model=CharacterOut)
def replace_character_tags(
    character_id: int, payload: CharacterTagsReplace, user=Depends(deps.require_user)
):
    """全量替换：必须带 expected_version，防止覆盖别处的修改。"""
    updated = repo.replace_character_tags(
        user.id, character_id, payload.tag_ids, expected_version=payload.expected_version
    )
    return updated.public()


# --------------------------------------------------------------------------- #
# 标签
# --------------------------------------------------------------------------- #


@router.get("/tags", response_model=list[TagOut])
def list_tags(
    category: Category | None = None, user=Depends(deps.require_user)
) -> list[dict[str, Any]]:
    repo.ensure_seeded(user.id)
    return [tag.public() for tag in repo.list_tags(user.id, category=category)]


@router.post("/tags", response_model=TagCreatedOut)
def create_tag(payload: TagCreate, response: Response, user=Depends(deps.require_user)):
    """重名不报错：直接返回已有标签，`created=false` 提示前端复用。"""
    tag, created = repo.create_tag(
        user.id, name=payload.name, category=payload.category, tone=payload.tone
    )
    response.status_code = 201 if created else 200
    payload_out = tag.public()
    payload_out["created"] = created
    return payload_out


@router.patch("/tags/{tag_id}", response_model=TagOut)
def update_tag(tag_id: int, payload: TagUpdate, user=Depends(deps.require_user)):
    tag = repo.update_tag(
        user.id,
        tag_id,
        name=payload.name,
        category=payload.category,
        tone=payload.tone,
    )
    if tag is None:
        raise HTTPException(status_code=404, detail="标签不存在")
    return tag.public()


@router.delete("/tags/{tag_id}", status_code=204)
def delete_tag(
    tag_id: int,
    force: bool = False,
    reassign_to: int | None = None,
    user=Depends(deps.require_user),
) -> None:
    """默认拒绝删除仍被引用的标签；`force` 仅解绑，`reassign_to` 迁移关联。"""
    if not repo.delete_tag(user.id, tag_id, force=force, reassign_to=reassign_to):
        raise HTTPException(status_code=404, detail="标签不存在")
    return None


@router.get("/tags/{tag_id}/characters")
def tag_characters(tag_id: int, user=Depends(deps.require_user)) -> dict[str, Any]:
    tag = repo.get_tag(user.id, tag_id)
    if tag is None:
        raise HTTPException(status_code=404, detail="标签不存在")
    return {"tag": tag.public(), "characters": repo.tag_usage(user.id, tag_id)}
