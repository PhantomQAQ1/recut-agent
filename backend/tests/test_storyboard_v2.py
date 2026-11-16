"""故事板改版：B1 微调、B4 计划/展开、C1 上传、E2 导出的后端行为。"""

from __future__ import annotations

import io
import json
import zipfile
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import main
import repositories as users_repo
import security
import storyboard
from schemas import ExpandShotRequest, GenerateRequest, RefineRequest, Shot

PASSWORD = "correct-horse-battery"

PLAN_JSON = {
    "total_seconds": 999,  # 故意写错，应被求和覆盖
    "narrative": "建立 → 升级 → 高潮",
    "shots": [
        {"index": 1, "duration": "5 秒", "scale": "wide shot", "lens": "135mm", "move": "", "purpose": "建立环境"},
        {"index": 2, "duration": "03s", "scale": "特写 ECU", "lens": "85mm", "move": "急速推镜 Crash Zoom", "purpose": "高潮"},
    ],
}

SHOT_JSON = {
    "id": 99,
    "duration": "04s",
    "scale": "近景 CU",
    "lens": "85mm",
    "move": "急速推镜 Crash Zoom",
    "title": "铜锣无风自鸣",
    "description": "铜锣震颤，尘埃浮动。",
    "prompt": "golden circlet, 战士, 铜锣自鸣",
    "runwayPrompt": "An 85mm close-up of a vibrating gong",
    "palette": "from-amber-950 via-orange-950 to-slate-950",
    "scene": "lantern",
}


class FakeCompletions:
    def __init__(self, contents: list[str]):
        self._contents = list(contents)
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        content = self._contents.pop(0) if self._contents else "{}"
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


def fake_client(*contents: str) -> SimpleNamespace:
    return SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions(list(contents))))


def ensure_user(email: str) -> None:
    if users_repo.get_user_by_email(email) is None:
        users_repo.create_user(
            email=email,
            password_hash=security.hash_password(PASSWORD),
            display_name=email.split("@")[0],
        )


@pytest.fixture(scope="module")
def client():
    test_client = TestClient(main.app)
    test_client.__enter__()
    ensure_user("board@example.com")
    response = test_client.post(
        "/api/v1/auth/login", json={"email": "board@example.com", "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    yield test_client
    test_client.__exit__(None, None, None)


# --------------------------------------------------------------------------- #
# B4 计划
# --------------------------------------------------------------------------- #


def test_plan_normalizes_and_sums_duration():
    import asyncio

    fake = fake_client(json.dumps(PLAN_JSON, ensure_ascii=False))
    plan = asyncio.run(
        storyboard.plan_story(GenerateRequest(idea="戏台"), client=fake)
    )
    assert [shot.index for shot in plan.shots] == [1, 2]
    assert plan.shots[0].duration == "05s"  # "5 秒" 被归一化
    assert plan.shots[0].scale == "全景 WS"  # wide shot
    assert plan.shots[0].lens == "85mm"  # 135mm 就近收敛
    assert plan.shots[0].move == "固定机位 Static"  # 空值兜底
    # 总和由各镜时长相加，不采信模型写的 999
    assert plan.total_seconds == 8


def test_expand_shot_keeps_plan_index_as_id():
    import asyncio

    fake = fake_client(json.dumps({"shot": SHOT_JSON}, ensure_ascii=False))
    payload = ExpandShotRequest(
        idea="戏台",
        plan={
            "total_seconds": 8,
            "narrative": "",
            "shots": [
                {"index": 1, "duration": "04s", "scale": "近景 CU", "lens": "85mm", "move": "x", "purpose": ""},
                {"index": 2, "duration": "04s", "scale": "特写 ECU", "lens": "85mm", "move": "y", "purpose": ""},
            ],
        },
        index=2,
    )
    shot = asyncio.run(storyboard.expand_shot(payload, client=fake))
    assert shot.id == 2
    assert shot.title == "铜锣无风自鸣"


# --------------------------------------------------------------------------- #
# B1 微调
# --------------------------------------------------------------------------- #


def test_refine_preserves_original_id_and_changes_prompt():
    import asyncio

    original = Shot(**{**SHOT_JSON, "id": 7})
    refined_payload = {**SHOT_JSON, "id": 123, "prompt": "golden circlet, 赛博霓虹, 铜锣自鸣"}
    fake = fake_client(json.dumps({"shot": refined_payload}, ensure_ascii=False))

    result = asyncio.run(
        storyboard.refine_shot(
            RefineRequest(shot=original, instruction="改成赛博朋克霓虹"), client=fake
        )
    )
    assert result.id == 7  # 保留原始 id，前端才能定位
    assert "赛博霓虹" in result.prompt
    # 未提及的字段保持原样
    assert result.duration == original.duration


# --------------------------------------------------------------------------- #
# C1 上传
# --------------------------------------------------------------------------- #

PNG_1X1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d494844520000000100000001080600000"
    "01f15c4890000000d4944415478da63f8ffff3f0005fe02fea735d3a40000000049454e44ae426082"
)


def upload(client: TestClient, data: bytes, mime: str = "image/png", name: str = "a.png"):
    return client.post(
        "/api/v1/uploads",
        files={"file": (name, io.BytesIO(data), mime)},
    )


def test_upload_dedupes_and_serves_bytes(client):
    first = upload(client, PNG_1X1)
    assert first.status_code == 200, first.text
    payload = first.json()
    assert payload["width"] == 1 and payload["height"] == 1

    second = upload(client, PNG_1X1)
    assert second.json()["id"] == payload["id"]  # 同图去重

    fetched = client.get(payload["url"])
    assert fetched.status_code == 200
    assert fetched.content == PNG_1X1
    assert "immutable" in fetched.headers["cache-control"]


def test_upload_rejects_wrong_type(client):
    response = upload(client, b"not an image", mime="application/pdf", name="a.pdf")
    assert response.status_code == 422


def test_upload_is_private(client):
    other = TestClient(main.app)
    other.__enter__()
    ensure_user("board-other@example.com")
    assert other.post(
        "/api/v1/auth/login",
        json={"email": "board-other@example.com", "password": PASSWORD},
    ).status_code == 200

    mine = upload(client, PNG_1X1).json()
    assert other.get(mine["url"]).status_code == 404
    other.__exit__(None, None, None)


# --------------------------------------------------------------------------- #
# E2 剪映草稿导出
# --------------------------------------------------------------------------- #


def test_export_jianying_zip_structure(client):
    created = client.post(
        "/api/v1/projects",
        json={
            "name": "导出测试",
            "storyboard": {
                "shots": [
                    {**SHOT_JSON, "id": 1},
                    {**SHOT_JSON, "id": 2, "duration": "06s", "title": "第二镜"},
                ],
                "anchors": ["golden circlet"],
            },
        },
    )
    assert created.status_code == 201, created.text
    project_id = created.json()["id"]

    response = client.get(f"/api/v1/projects/{project_id}/export/jianying")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"

    archive = zipfile.ZipFile(io.BytesIO(response.content))
    names = set(archive.namelist())
    assert "recut-draft/draft_content.json" in names
    assert "recut-draft/shots.md" in names
    assert "recut-draft/shots.csv" in names
    assert "recut-draft/materials/shot-01.png" in names
    assert "recut-draft/materials/shot-02.png" in names

    content = json.loads(archive.read("recut-draft/draft_content.json"))
    assert content["canvas_config"]["width"] == 1920
    # 4s + 6s = 10s
    assert content["duration"] == 10_000_000
    assert len(content["tracks"]) == 2

    page = archive.read("recut-draft/materials/shot-01.png")
    assert page[:8] == b"\x89PNG\r\n\x1a\n"


def test_export_rejects_empty_project(client):
    created = client.post("/api/v1/projects", json={"name": "空项目", "storyboard": {}})
    project_id = created.json()["id"]
    response = client.get(f"/api/v1/projects/{project_id}/export/jianying")
    assert response.status_code == 422
