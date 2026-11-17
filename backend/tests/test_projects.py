"""项目持久化与归属隔离测试。"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import main
import repositories as repo
import security

PASSWORD = "correct-horse-battery"
STORYBOARD = {
    "style": "燃向踩点",
    "model": "即梦 Jimeng",
    "anchors": ["golden circlet"],
    "shots": [
        {
            "id": 1,
            "duration": "04s",
            "scale": "特写 ECU",
            "lens": "85mm",
            "move": "急速推镜 Crash Zoom",
            "title": "铜锣无风自鸣",
            "description": "尘埃浮动",
            "prompt": "金色头箍, 战士, 铜锣自鸣",
            "runwayPrompt": "An 85mm extreme close-up of a gong",
            "edit": "",
            "palette": "from-amber-950 via-orange-950 to-slate-950",
            "scene": "lantern",
        }
    ],
}


def ensure_user(email: str) -> None:
    if repo.get_user_by_email(email) is None:
        repo.create_user(
            email=email,
            password_hash=security.hash_password(PASSWORD),
            display_name=email.split("@")[0],
        )


def signed_in(email: str) -> TestClient:
    """返回一个已登录的客户端（独立 cookie 罐，便于测多用户隔离）。"""
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
    client = signed_in("alice-proj@example.com")
    yield client
    client.__exit__(None, None, None)


@pytest.fixture(scope="module")
def bob():
    client = signed_in("bob-proj@example.com")
    yield client
    client.__exit__(None, None, None)


def test_anonymous_cannot_touch_projects():
    anonymous = TestClient(main.app)
    assert anonymous.get("/api/v1/projects").status_code == 401
    assert anonymous.post("/api/v1/projects", json={"name": "x"}).status_code == 401


def test_create_then_list(alice):
    created = alice.post(
        "/api/v1/projects", json={"name": "黑神话：最后一盏灯", "storyboard": STORYBOARD}
    )
    assert created.status_code == 201
    project_id = created.json()["id"]
    assert created.json()["storyboard"]["shots"][0]["title"] == "铜锣无风自鸣"

    listing = alice.get("/api/v1/projects")
    assert listing.status_code == 200
    ids = [item["id"] for item in listing.json()["projects"]]
    assert project_id in ids
    # 列表只回摘要，不带故事板正文。
    assert "storyboard" not in listing.json()["projects"][0]


def test_get_update_delete_roundtrip(alice):
    project_id = alice.post("/api/v1/projects", json={"name": "临时项目"}).json()["id"]

    fetched = alice.get(f"/api/v1/projects/{project_id}")
    assert fetched.status_code == 200
    assert fetched.json()["storyboard"] == {}

    updated = alice.put(
        f"/api/v1/projects/{project_id}",
        json={"name": "改过的名字", "storyboard": STORYBOARD},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "改过的名字"
    assert updated.json()["storyboard"]["style"] == "燃向踩点"

    assert alice.delete(f"/api/v1/projects/{project_id}").status_code == 204
    assert alice.get(f"/api/v1/projects/{project_id}").status_code == 404


def test_other_users_project_is_invisible(alice, bob):
    project_id = alice.post(
        "/api/v1/projects", json={"name": "Alice 私有项目", "storyboard": STORYBOARD}
    ).json()["id"]

    # 别人的项目一律 404，避免用状态码探测 id 是否存在。
    assert bob.get(f"/api/v1/projects/{project_id}").status_code == 404
    assert bob.put(f"/api/v1/projects/{project_id}", json={"name": "劫持"}).status_code == 404
    assert bob.delete(f"/api/v1/projects/{project_id}").status_code == 404

    # Alice 自己的数据完好无损。
    assert alice.get(f"/api/v1/projects/{project_id}").status_code == 200


def test_project_version_is_returned_and_bumped(alice):
    created = alice.post("/api/v1/projects", json={"name": "版本测试"}).json()
    assert created["version"] == 1

    updated = alice.put(
        f"/api/v1/projects/{created['id']}",
        json={"name": "版本测试 v2", "expected_version": 1},
    )
    assert updated.status_code == 200
    assert updated.json()["version"] == 2

    fetched = alice.get(f"/api/v1/projects/{created['id']}")
    assert fetched.json()["version"] == 2


def test_stale_project_version_is_rejected(alice):
    created = alice.post("/api/v1/projects", json={"name": "冲突测试"}).json()
    project_id = created["id"]

    first = alice.put(
        f"/api/v1/projects/{project_id}",
        json={"storyboard": {"style": "第一次"}, "expected_version": 1},
    )
    assert first.status_code == 200

    # 拿旧版本再写一次：必须 409，并且带回当前版本号
    stale = alice.put(
        f"/api/v1/projects/{project_id}",
        json={"storyboard": {"style": "基于旧版本"}, "expected_version": 1},
    )
    assert stale.status_code == 409
    assert stale.json()["current_version"] == 2

    # 冲突的那次写入不能生效
    assert alice.get(f"/api/v1/projects/{project_id}").json()["storyboard"]["style"] == "第一次"


def test_project_update_without_version_still_works(alice):
    """不带 expected_version 时保持旧行为，避免老客户端直接报错。"""
    created = alice.post("/api/v1/projects", json={"name": "兼容测试"}).json()
    response = alice.put(
        f"/api/v1/projects/{created['id']}", json={"name": "兼容测试 v2"}
    )
    assert response.status_code == 200
    assert response.json()["version"] == 2


def test_storyboard_size_limit(alice):
    oversized = {"shots": [], "blob": "x" * (513 * 1024)}
    response = alice.post("/api/v1/projects", json={"name": "超大项目", "storyboard": oversized})
    assert response.status_code == 413
    assert "上限" in response.json()["detail"]


def test_update_missing_project_is_404(alice):
    assert alice.put("/api/v1/projects/999999", json={"name": "x"}).status_code == 404
    assert alice.delete("/api/v1/projects/999999").status_code == 404
