"""一次性验证：静态前端与 /api 能否同源共存。"""

import re

from starlette.testclient import TestClient

import main

with TestClient(main.app) as client:
    root = client.get("/")
    print("GET /            ->", root.status_code, root.headers.get("content-type"), len(root.content), "bytes")
    print("  index.html ok  ->", b'<div id="app">' in root.content)

    match = re.search(rb"/assets/[A-Za-z0-9_.-]+\.js", root.content)
    if match:
        asset = match.group(0).decode()
        response = client.get(asset)
        print("GET " + asset + " ->", response.status_code, len(response.content), "bytes")
    else:
        print("  (no asset reference found)")

    health = client.get("/api/health")
    print("GET /api/health  ->", health.status_code, health.json())

    me = client.get("/api/v1/auth/me")
    print("GET /api/v1/auth/me ->", me.status_code)

    unknown = client.get("/api/v1/does-not-exist")
    print("GET /api/v1/does-not-exist ->", unknown.status_code)
