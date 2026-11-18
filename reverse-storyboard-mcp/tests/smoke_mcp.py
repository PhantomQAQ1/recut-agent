"""Run explicitly with the installed MCP environment: python tests/smoke_mcp.py.

Uses the official SDK to verify a real child-process stdio connection.
Does not request video preparation or invoke a vision provider.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def check() -> None:
    root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root / "src")
    # Stable paths resolved independently of the caller's working directory.
    env.setdefault("STORYBOARD_MEDIA_ROOTS", str(root / "media"))
    env.setdefault("STORYBOARD_DATA_DIR", str(root / "data"))
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "reverse_storyboard.server"],
        env=env,
    )
    async with stdio_client(params) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            initialized = await session.initialize()
            tools = await session.list_tools()
            actual = {tool.name for tool in tools.tools}
            expected = {"health", "prepare_video", "analyze_shots", "get_project", "export_storyboard"}
            if actual != expected:
                raise RuntimeError(f"Unexpected tools: {sorted(actual)}")
            result = await session.call_tool("health", {})
            if result.isError:
                raise RuntimeError("MCP health returned a tool error")
            texts = [item.text for item in result.content if item.type == "text"]
            payloads = [json.loads(text) for text in texts]
            if not any(isinstance(item, dict) and item.get("status") == "ok" for item in payloads):
                raise RuntimeError("MCP health did not return status=ok")
            print(json.dumps({
                "status": "passed", "protocol_version": initialized.protocolVersion,
                "server": initialized.serverInfo.name, "tools": sorted(actual),
                "health": payloads,
            }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(asyncio.wait_for(check(), timeout=45))
