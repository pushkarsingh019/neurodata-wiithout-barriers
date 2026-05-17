from __future__ import annotations

import asyncio

from openneuro_mcp.server import build_server


def test_server_exposes_storage_info_tool() -> None:
    tools = {tool.name for tool in asyncio.run(build_server().list_tools())}

    assert "get_storage_info" in tools
