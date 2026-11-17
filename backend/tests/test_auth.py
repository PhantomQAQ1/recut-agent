"""认证行为测试：登录、锁定、会话、改密。

重点覆盖计划里点名的边界：密码错误不可枚举、账号锁定、会话失效。
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import db
import main
import repositories as repo
import security

PASSWORD = "correct-horse-battery"
NEW_PASSWORD = "another-strong-password"


@pytest.fixture(scope="module")
def client():
    # with 语句才会触发 lifespan（建表）。
    with TestClient(main.app) as test_client:
        yield test_client


def make_user(email: str, password: str = PASSWORD, role: str = "member") -> repo.User:
    return repo.create_user(
        email=email,
        password_hash=security.hash_password(password),
        display_name=email.split("@")[0],
        role=role,
    )


def login(client: TestClient, email: str, password: str = PASSWORD, remember: bool = False):
    return client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password, "remember": remember},
    )


def test_login_success_sets_httponly_cookie(client):
    make_user("alice@example.com")
    response = login(client, "alice@example.com")
    assert response.status_code == 200

    payload = response.json()
    assert payload["user"]["email"] == "alice@example.com"
    assert "password_hash" not in payload["user"]

    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie
    assert "recut_session=" in cookie


def test_me_requires_login(client):
    anonymous = TestClient(main.app)
    assert anonymous.get("/api/v1/auth/me").status_code == 401

    make_user("bob@example.com")
    assert login(client, "bob@example.com").status_code == 200
    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["user"]["email"] == "bob@example.com"


def test_wrong_password_and_unknown_email_are_indistinguishable(client):
    make_user("carol@example.com")
    wrong = login(client, "carol@example.com", "definitely-wrong")
    unknown = login(client, "nobody@example.com", "definitely-wrong")

    assert wrong.status_code == 401
    assert unknown.status_code == 401
    # 同样的提示，否则可以用来枚举哪些邮箱已注册。
    assert wrong.json()["detail"] == unknown.json()["detail"]
    assert wrong.json()["detail"] == "邮箱或密码不正确"


def test_account_locks_after_repeated_failures(client):
    make_user("dave@example.com")
    # conftest 把阈值设为 3：前两次 401，第三次触发锁定。
    assert login(client, "dave@example.com", "bad-1").status_code == 401
    assert login(client, "dave@example.com", "bad-2").status_code == 401
    assert login(client, "dave@example.com", "bad-3").status_code == 423

    # 锁定期间即使密码正确也拒绝。
    locked = login(client, "dave@example.com", PASSWORD)
    assert locked.status_code == 423
    assert "锁定" in locked.json()["detail"]


def test_lock_expires_and_allows_login(client):
    make_user("erin@example.com")
    for attempt in range(3):
        login(client, "erin@example.com", f"bad-{attempt}")
    assert login(client, "erin@example.com", PASSWORD).status_code == 423

    # 把锁定时间改到过去，模拟窗口过期。
    with db.connect() as conn:
        conn.execute(
            "UPDATE users SET locked_until = ? WHERE email = ?",
            (db.in_minutes(-1), "erin@example.com"),
        )
    assert login(client, "erin@example.com", PASSWORD).status_code == 200


def test_successful_login_resets_failure_counter(client):
    make_user("frank@example.com")
    login(client, "frank@example.com", "bad-1")
    login(client, "frank@example.com", "bad-2")
    assert login(client, "frank@example.com", PASSWORD).status_code == 200

    user = repo.get_user_by_email("frank@example.com")
    assert user is not None
    assert user.failed_attempts == 0
    assert user.locked_until is None


def test_logout_revokes_session(client):
    make_user("grace@example.com")
    assert login(client, "grace@example.com").status_code == 200
    assert client.get("/api/v1/auth/me").status_code == 200

    assert client.post("/api/v1/auth/logout").status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401


def test_remember_me_uses_persistent_cookie(client):
    make_user("henry@example.com")
    response = login(client, "henry@example.com", remember=True)
    assert response.status_code == 200
    assert "Max-Age=" in response.headers["set-cookie"]
    assert response.json()["remember"] is True


def test_disabled_account_is_rejected(client):
    user = make_user("ivan@example.com")
    repo.set_status(user.id, "disabled")
    response = login(client, "ivan@example.com")
    assert response.status_code == 403
    assert "停用" in response.json()["detail"]
    repo.set_status(user.id, "active")


def test_change_password_requires_current_password(client):
    make_user("judy@example.com")
    assert login(client, "judy@example.com").status_code == 200

    wrong = client.post(
        "/api/v1/auth/password",
        json={"current_password": "not-the-password", "new_password": NEW_PASSWORD},
    )
    assert wrong.status_code == 401

    too_short = client.post(
        "/api/v1/auth/password",
        json={"current_password": PASSWORD, "new_password": "short"},
    )
    assert too_short.status_code == 422

    ok = client.post(
        "/api/v1/auth/password",
        json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
    )
    assert ok.status_code == 204

    # 旧密码失效，新密码可用（当前会话保留）。
    other = TestClient(main.app)
    assert login(other, "judy@example.com", PASSWORD).status_code == 401
    assert login(other, "judy@example.com", NEW_PASSWORD).status_code == 200


def test_password_change_kicks_other_sessions(client):
    make_user("kate@example.com")
    phone = TestClient(main.app)
    laptop = TestClient(main.app)
    assert login(phone, "kate@example.com").status_code == 200
    assert login(laptop, "kate@example.com").status_code == 200

    changed = laptop.post(
        "/api/v1/auth/password",
        json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
    )
    assert changed.status_code == 204

    # 另一台设备被踢下线，发起改密的这台仍然可用。
    assert phone.get("/api/v1/auth/me").status_code == 401
    assert laptop.get("/api/v1/auth/me").status_code == 200


def test_business_endpoints_require_login():
    anonymous = TestClient(main.app)
    response = anonymous.post(
        "/api/v1/storyboard/generate",
        json={"idea": "一个测试梗概", "style": "燃向踩点", "anchors": [], "model": "即梦 Jimeng"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "请先登录"


def test_expired_session_is_rejected(client):
    make_user("leo@example.com")
    assert login(client, "leo@example.com").status_code == 200

    with db.connect() as conn:
        conn.execute("UPDATE sessions SET expires_at = ?", (db.in_minutes(-1),))

    fresh = TestClient(main.app)
    fresh.cookies.set("recut_session", client.cookies.get("recut_session"))
    assert fresh.get("/api/v1/auth/me").status_code == 401


def test_foreign_origin_is_rejected(client):
    """跨站 Origin 必须挡住：这是 Cookie 鉴权之外的 CSRF 防线。"""
    make_user("origin-blocked@example.com")
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "origin-blocked@example.com", "password": PASSWORD},
        headers={"Origin": "https://evil.example"},
    )
    assert response.status_code == 403


def test_same_origin_is_allowed_without_allowlist(client):
    """部署到陌生域名时，同源请求不该被白名单误伤。

    白名单默认只有 localhost:5173；魔搭创空间这类新域名靠"Origin == 本请求 host"放行。
    """
    make_user("origin-same@example.com")
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "origin-same@example.com", "password": PASSWORD},
        headers={"Origin": "http://testserver"},
    )
    assert response.status_code == 200


def test_same_origin_behind_proxy_is_allowed(client):
    """反向代理场景：Origin 与 X-Forwarded-Host 一致时也应放行。"""
    make_user("origin-proxy@example.com")
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "origin-proxy@example.com", "password": PASSWORD},
        headers={
            "Origin": "https://demo.ms.show",
            "X-Forwarded-Proto": "https",
            "X-Forwarded-Host": "demo.ms.show",
        },
    )
    assert response.status_code == 200
