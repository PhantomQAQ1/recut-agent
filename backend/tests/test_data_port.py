"""导出/导入通道的测试：能搬过去、重复导入不产生副本。"""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import main
import repositories as repo
import security

PASSWORD = "correct-horse-battery"


@pytest.fixture()
def client():
    with TestClient(main.app) as test_client:
        email = f"data-{uuid4().hex[:8]}@example.com"
        repo.create_user(
            email=email,
            password_hash=security.hash_password(PASSWORD),
            display_name="数据员",
            role="member",
        )
        response = test_client.post(
            "/api/v1/auth/login", json={"email": email, "password": PASSWORD}
        )
        assert response.status_code == 200
        yield test_client


PAYLOAD = {
    "version": 1,
    "tags": [{"name": "搬迁标签", "category": "character", "tone": "neutral"}],
    "characters": [
        {"name": "搬迁角色", "role_label": "配角", "prompt_anchor": "silhouette", "tags": ["搬迁标签"]}
    ],
    "projects": [{"name": "搬迁项目", "storyboard": {"idea": "一段用来验证搬运的梗概"}}],
}


def test_export_shape(client):
    data = client.get("/api/v1/data/export").json()
    assert data["version"] == 1
    assert isinstance(data["projects"], list)
    assert isinstance(data["characters"], list)
    assert isinstance(data["tags"], list)
    # 不能泄露密码哈希之类的东西
    assert "password_hash" not in str(data)


def test_import_then_export_round_trip(client):
    created = client.post("/api/v1/data/import", json=PAYLOAD)
    assert created.status_code == 200
    body = created.json()
    assert body["created_projects"] == 1
    assert body["created_characters"] == 1
    assert body["created_tags"] == 1

    data = client.get("/api/v1/data/export").json()
    assert "搬迁项目" in [item["name"] for item in data["projects"]]
    assert "搬迁角色" in [item["name"] for item in data["characters"]]
    character = next(item for item in data["characters"] if item["name"] == "搬迁角色")
    assert character["tags"] == ["搬迁标签"]


def test_import_twice_skips_duplicates(client):
    client.post("/api/v1/data/import", json=PAYLOAD)
    again = client.post("/api/v1/data/import", json=PAYLOAD).json()
    assert again["created_projects"] == 0
    assert again["created_characters"] == 0
    assert "搬迁项目" in again["skipped_projects"]
    assert "搬迁角色" in again["skipped_characters"]


def test_import_rejects_unknown_version(client):
    response = client.post("/api/v1/data/import", json={"version": 99})
    assert response.status_code == 422
