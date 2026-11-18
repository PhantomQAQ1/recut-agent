"""OpenAI-compatible vision client; never falls back to fabricated observations."""
from __future__ import annotations
import base64
import hashlib
import json
import os
from pathlib import Path
from urllib.parse import urlsplit
import httpx
from pydantic import ValidationError
from .models import Observation

PROMPT = Path(__file__).parent / "prompts" / "vision.md"


def configuration() -> dict:
    base = os.environ.get("STORYBOARD_VISION_BASE_URL", "").rstrip("/")
    model = os.environ.get("STORYBOARD_VISION_MODEL", "")
    return {"configured": bool(base and model and os.environ.get("STORYBOARD_VISION_API_KEY")),
            "model": model or None, "prompt_version": hashlib.sha256(PROMPT.read_bytes()).hexdigest()[:16]}


async def analyze(shot: dict) -> dict:
    if not configuration()["configured"]:
        raise ValueError("Configure STORYBOARD_VISION_BASE_URL, STORYBOARD_VISION_MODEL and STORYBOARD_VISION_API_KEY")
    base = os.environ["STORYBOARD_VISION_BASE_URL"].rstrip("/")
    parsed = urlsplit(base)
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Vision base URL must not contain credentials, query or fragment")
    if parsed.scheme != "https" and not (parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}):
        raise ValueError("Vision endpoint must use HTTPS or local HTTP")
    frames = shot["frames"]
    content = [{"type": "text", "text": json.dumps({"shot_id": shot["id"], "start": shot["start"], "end": shot["end"],
                "frame_times": [f["timestamp"] for f in frames], "schema": Observation.model_json_schema()}, ensure_ascii=False)}]
    for index, frame in enumerate(frames):
        raw = Path(frame["path"]).read_bytes()
        if len(raw) > 4 * 1024 * 1024:
            raise ValueError("Evidence JPEG exceeds 4 MiB")
        content.extend([{"type": "text", "text": f"证据帧 {index}，时间 {frame['timestamp']} 秒"},
                        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(raw).decode("ascii")}}])
    messages = [{"role": "system", "content": PROMPT.read_text(encoding="utf-8")}, {"role": "user", "content": content}]
    payload = {"model": os.environ["STORYBOARD_VISION_MODEL"], "messages": messages,
               "temperature": 0.1, "max_tokens": 2500, "response_format": {"type": "json_object"}}
    async with httpx.AsyncClient(timeout=httpx.Timeout(120), trust_env=False) as client:
        for attempt in range(3):
            try:
                async with client.stream("POST", base + "/chat/completions", json=payload,
                        headers={"Authorization": "Bearer " + os.environ["STORYBOARD_VISION_API_KEY"]}) as response:
                    if response.status_code >= 400:
                        # Never expose upstream response bodies or credentials in errors.
                        raise RuntimeError(f"Vision endpoint returned HTTP {response.status_code}")
                    raw = bytearray()
                    async for chunk in response.aiter_bytes():
                        raw.extend(chunk)
                        if len(raw) > 2 * 1024 * 1024:
                            raise ValueError("Vision response exceeds 2 MiB")
                text = json.loads(raw)["choices"][0]["message"]["content"]
                if not isinstance(text, str):
                    raise ValueError("Expected JSON text message")
                result = Observation.model_validate_json(text)
                # Validate indexes before dereferencing them, then assess motion
                # using only the evidence the model actually cites.
                result.enforce_evidence(len(frames), len({f['timestamp'] for f in frames}))
                cited_times = {frames[i]['timestamp'] for i in result.evidence_frames}
                result.enforce_evidence(len(frames), len(cited_times))
                return result.model_dump()
            except (ValidationError, ValueError, KeyError, IndexError, TypeError):
                if attempt == 2:
                    raise RuntimeError("Vision output failed schema/evidence validation after 3 attempts") from None
                messages.append({"role": "user", "content": "输出未通过 JSON/schema/证据索引校验，请重新输出一个符合给定 schema 的对象。"})
            except httpx.HTTPError:
                raise RuntimeError("Vision network request failed; check endpoint and connectivity") from None
    raise RuntimeError("Vision analysis did not produce a result")
