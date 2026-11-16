"""本地 mock 模型服务：在没有真实 API Key 的情况下联调 / 验证前后端链路。

它实现 OpenAI 兼容的 POST /v1/chat/completions，返回一份「故意带漂移」的分镜
JSON——用来同时验证归一化逻辑（非法配色、"5 秒"、英文景别都会被纠正）。

用法（另开一个终端）：
    .venv\\Scripts\\python -m tests.mock_llm --port 8899

然后用它启动后端：
    $env:LLM_API_KEY="mock-key"; $env:LLM_BASE_URL="http://127.0.0.1:8899/v1"
    .venv\\Scripts\\python -m uvicorn main:app --port 8001
"""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MOCK_SHOTS = {
    "shots": [
        {
            "duration": "5 秒",
            "scale": "wide shot",
            "lens": "135mm",
            "move": "缓慢横移 Truck",
            "title": "雨夜的天台，霓虹在积水里碎成一片",
            "description": "俯拍空旷天台，霓虹招牌的倒影在水洼里晃动。",
            "prompt": "赛博城市, 女主, 雨夜天台俯拍, 霓虹倒影, 冷蓝色调, 电影级光影",
            "runwayPrompt": "A 35mm wide overhead shot of an empty rooftop at rainy night, neon reflections in puddles, cool blue palette, cinematic.",
            "palette": "from-blue-500",
        },
        {
            "duration": "06s",
            "scale": "中景 MS",
            "lens": "50mm",
            "move": "手持跟拍 Handheld",
            "title": "她推开铁门，风把雨吹成斜线",
            "description": "手持跟随角色穿过铁门，雨丝被风压成斜线。",
            "prompt": "赛博城市, 女主, 推开铁门, 逆光雨丝, 手持跟拍, 高反差",
            "runwayPrompt": "A 50mm handheld tracking shot as she pushes an iron door open, backlit rain streaks, high contrast.",
            "palette": "from-indigo-950 via-slate-900 to-amber-950",
        },
        {
            "duration": "03s",
            "scale": "特写 ECU",
            "lens": "85mm",
            "move": "急速推镜 Crash Zoom",
            "title": "瞳孔里映出爆炸的火光",
            "description": "急速推近面部特写，火光在瞳孔中炸开。",
            "prompt": "赛博城市, 女主, 瞳孔特写, 爆炸火光映照, 升格, 强戏剧张力",
            "runwayPrompt": "An 85mm extreme close-up crash zoom into her eye as an explosion ignites, slow motion, dramatic.",
            "palette": "from-red-950 via-amber-950 to-slate-950",
        },
    ]
}


class Handler(BaseHTTPRequestHandler):
    server_version = "MockLLM/1.0"

    def do_POST(self) -> None:  # noqa: N802 - http.server 约定
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length).decode("utf-8", "replace")
        record = {
            "path": self.path,
            "model": self._extract(body, "model"),
            "has_images": "image_url" in body,
            "content_chars": len(body),
        }
        print(json.dumps(record, ensure_ascii=False), flush=True)

        payload = {
            "id": "mock-completion",
            "object": "chat.completion",
            "created": 0,
            "model": "mock-model",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": json.dumps(MOCK_SHOTS, ensure_ascii=False)},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 100, "completion_tokens": 800, "total_tokens": 900},
        }
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    @staticmethod
    def _extract(body: str, key: str) -> str:
        try:
            return str(json.loads(body).get(key, ""))
        except json.JSONDecodeError:
            return ""

    def log_message(self, *_args) -> None:  # 静默默认访问日志
        return


def main() -> None:
    parser = argparse.ArgumentParser(description="OpenAI 兼容的本地 mock 模型服务")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8899)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"mock LLM listening on http://{args.host}:{args.port}/v1", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
