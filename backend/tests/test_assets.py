"""角色资产库：播种、CRUD、标签联动与并发边界。"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import assets_repo as repo
import main
import repositories as users_repo
import security

PASSWORD = "correct-horse-battery"
APPEARANCE_TAG = "金色头箍"


def ensure_user(email: str) -> None:
    if users_repo.get_user_by_email(email) is None:
        users_repo.create_user(
            email=email,
            password_hash=security.hash_password(PASSWORD),
            display_name=email.split("@")[0],
        )


def signed_in(email: str) -> TestClient:
    client = TestClient(main.app)
    client.__enter__()
    ensure_user(email)
    response = client.post(
        "/api/v1/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    return client


@pytest.fixture(scope="module")
def alice():
    client = signed_in("alice-assets@example.com")
    yield client
    client.__exit__(None, None, None)


@pytest.fixture(scope="module")
def bob():
    client = signed_in("bob-assets@example.com")
    yield client
    client.__exit__(None, None, None)


def tags_by_name(client: TestClient) -> dict[str, dict]:
    return {tag["name"]: tag for tag in client.get("/api/v1/tags").json()}


# --------------------------------------------------------------------------- #
# 播种
# --------------------------------------------------------------------------- #


def test_seed_creates_preset_character_and_tags(alice):
    characters = alice.get("/api/v1/characters").json()
    assert [item["name"] for item in characters] == ["天命人"]

    character = characters[0]
    assert character["role_label"] == "齐天大圣 · 核心角色"
    assert character["prompt_anchor"] == "golden circlet, monkey warrior, brown fur"
    assert character["consistency"] is None  # 等真实比对算法接入
    assert sorted(tag["name"] for tag in character["tags"]) == sorted(
        ["棕色毛发", "金色头箍", "玄铁甲胄"]
    )

    tags = tags_by_name(alice)
    assert len(tags) == 14
    assert tags[APPEARANCE_TAG]["category"] == "appearance"
    assert tags[APPEARANCE_TAG]["usage_count"] == 1


def test_seed_does_not_resurrect_after_delete(alice):
    """删光之后刷新不应该把预设塞回来。"""
    for character in alice.get("/api/v1/characters").json():
        assert alice.delete(f"/api/v1/characters/{character['id']}").status_code == 204
    for tag in alice.get("/api/v1/tags").json():
        assert alice.delete(f"/api/v1/tags/{tag['id']}?force=true").status_code == 204

    assert alice.get("/api/v1/characters").json() == []
    assert alice.get("/api/v1/tags").json() == []


# --------------------------------------------------------------------------- #
# 标签：重名归一化
# --------------------------------------------------------------------------- #


def test_duplicate_tag_names_are_reused(alice):
    first = alice.post("/api/v1/tags", json={"name": "热血", "category": "emotion", "tone": "rose"})
    second = alice.post("/api/v1/tags", json={"name": "热血", "category": "emotion", "tone": "rose"})
    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert second.json()["created"] is False


def test_tag_dedup_ignores_whitespace_and_width(alice):
    alice.post("/api/v1/tags", json={"name": "金属质感", "category": "palette", "tone": "neutral"})
    varied = alice.post(
        "/api/v1/tags", json={"name": "金属 质感", "category": "palette", "tone": "neutral"}
    )
    assert varied.status_code == 200
    assert varied.json()["created"] is False
    assert varied.json()["name"] == "金属质感"  # 保留第一次的展示名


def test_rename_to_existing_name_conflicts(alice):
    a = alice.post("/api/v1/tags", json={"name": "冷光", "category": "lighting"})
    b = alice.post("/api/v1/tags", json={"name": "暖光", "category": "lighting"})
    response = alice.patch(f"/api/v1/tags/{b.json()['id']}", json={"name": "冷光"})
    assert response.status_code == 409


# --------------------------------------------------------------------------- #
# 角色 CRUD
# --------------------------------------------------------------------------- #


def test_character_crud_and_tags(alice):
    created = alice.post(
        "/api/v1/characters",
        json={
            "name": "神秘身影",
            "role_label": "反派 · 客串",
            "description": "只在雨夜出现",
            "prompt_anchor": "silhouette, rain",
            "tone": "indigo",
        },
    )
    assert created.status_code == 201
    character = created.json()
    assert character["version"] == 1
    assert character["tags"] == []

    tag = alice.post("/api/v1/tags", json={"name": "剪影", "category": "lighting"}).json()
    patched = alice.patch(
        f"/api/v1/characters/{character['id']}/tags", json={"add": [tag["id"]]}
    )
    assert patched.status_code == 200
    assert [item["name"] for item in patched.json()["tags"]] == ["剪影"]

    renamed = alice.patch(f"/api/v1/characters/{character['id']}", json={"name": "雨夜黑影"})
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "雨夜黑影"

    assert alice.delete(f"/api/v1/characters/{character['id']}").status_code == 204
    assert alice.get(f"/api/v1/characters/{character['id']}").status_code == 404


def test_duplicate_character_name_conflicts(alice):
    alice.post("/api/v1/characters", json={"name": "替身"})
    again = alice.post("/api/v1/characters", json={"name": "替身 "})
    assert again.status_code == 409


def test_other_users_character_is_invisible(alice, bob):
    created = alice.post("/api/v1/characters", json={"name": "Alice 私有"}).json()
    assert bob.get(f"/api/v1/characters/{created['id']}").status_code == 404
    assert bob.patch(f"/api/v1/characters/{created['id']}", json={"name": "劫持"}).status_code == 404
    assert bob.delete(f"/api/v1/characters/{created['id']}").status_code == 404
    # Bob 自己的列表里看不到它
    assert all(item["name"] != "Alice 私有" for item in bob.get("/api/v1/characters").json())


# --------------------------------------------------------------------------- #
# 标签删除三策略
# --------------------------------------------------------------------------- #


def test_delete_referenced_tag_is_rejected_with_usage(bob):
    character = bob.get("/api/v1/characters").json()[0]
    tag = next(item for item in character["tags"] if item["name"] == APPEARANCE_TAG)

    response = bob.delete(f"/api/v1/tags/{tag['id']}")
    assert response.status_code == 409
    body = response.json()
    assert body["used_by"][0]["name"] == "天命人"
    # 标签还在
    assert any(item["id"] == tag["id"] for item in bob.get("/api/v1/tags").json())


def test_delete_tag_with_force_keeps_character(bob):
    tag = tags_by_name(bob)[APPEARANCE_TAG]
    assert bob.delete(f"/api/v1/tags/{tag['id']}?force=true").status_code == 204

    character = bob.get("/api/v1/characters").json()[0]
    assert character["name"] == "天命人"
    assert APPEARANCE_TAG not in [item["name"] for item in character["tags"]]


def test_delete_tag_with_reassign_moves_links(bob):
    source = tags_by_name(bob)["棕色毛发"]
    target = bob.post(
        "/api/v1/tags", json={"name": "深棕毛发", "category": "appearance", "tone": "amber"}
    ).json()
    assert bob.delete(f"/api/v1/tags/{source['id']}?reassign_to={target['id']}").status_code == 204

    character = bob.get("/api/v1/characters").json()[0]
    names = [item["name"] for item in character["tags"]]
    assert "深棕毛发" in names
    assert "棕色毛发" not in names
    assert tags_by_name(bob)["深棕毛发"]["usage_count"] == 1


def test_reassign_across_categories_is_rejected(bob):
    source = tags_by_name(bob)["玄铁甲胄"]
    target = tags_by_name(bob)["热血"]
    response = bob.delete(f"/api/v1/tags/{source['id']}?reassign_to={target['id']}")
    assert response.status_code == 422


# --------------------------------------------------------------------------- #
# 并发：乐观锁与增量合并
# --------------------------------------------------------------------------- #


def test_stale_version_is_rejected(bob):
    character = bob.get("/api/v1/characters").json()[0]
    version = character["version"]

    first = bob.patch(
        f"/api/v1/characters/{character['id']}",
        json={"description": "第一处修改", "expected_version": version},
    )
    assert first.status_code == 200
    assert first.json()["version"] == version + 1

    stale = bob.patch(
        f"/api/v1/characters/{character['id']}",
        json={"description": "基于旧版本的修改", "expected_version": version},
    )
    assert stale.status_code == 409
    assert stale.json()["current_version"] == version + 1


def test_incremental_tag_updates_merge(bob):
    character = bob.get("/api/v1/characters").json()[0]
    drama = bob.post("/api/v1/tags", json={"name": "戏台", "category": "character"}).json()
    lamp = bob.post("/api/v1/tags", json={"name": "灯笼光", "category": "lighting"}).json()

    # 两个窗口各自加一个标签：都加同一个角色也不会互相覆盖
    first = bob.patch(
        f"/api/v1/characters/{character['id']}/tags", json={"add": [drama["id"]]}
    )
    second = bob.patch(
        f"/api/v1/characters/{character['id']}/tags", json={"add": [lamp["id"]]}
    )
    names = {item["name"] for item in second.json()["tags"]}
    assert {"戏台", "灯笼光"} <= names
    assert second.json()["version"] > first.json()["version"]


def test_replace_tags_requires_matching_version(bob):
    character = bob.get("/api/v1/characters").json()[0]
    keeper = bob.post("/api/v1/tags", json={"name": "只留这个", "category": "emotion"}).json()
    stale = bob.put(
        f"/api/v1/characters/{character['id']}/tags",
        json={"tag_ids": [keeper["id"]], "expected_version": character["version"] - 1},
    )
    assert stale.status_code == 409

    fresh = bob.get(f"/api/v1/characters/{character['id']}").json()
    ok = bob.put(
        f"/api/v1/characters/{character['id']}/tags",
        json={"tag_ids": [keeper["id"]], "expected_version": fresh["version"]},
    )
    assert ok.status_code == 200
    assert [item["name"] for item in ok.json()["tags"]] == ["只留这个"]


def _user_id(client: TestClient) -> int:
    return int(client.get("/api/v1/auth/me").json()["user"]["id"])
