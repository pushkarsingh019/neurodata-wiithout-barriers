from __future__ import annotations

import asyncio

from openneuro_mcp.server import build_server


def test_server_exposes_storage_info_tool() -> None:
    tools = {tool.name for tool in asyncio.run(build_server().list_tools())}

    assert "get_storage_info" in tools
    assert "register_local_dataset" in tools
    assert "index_local_dataset" in tools
    assert "get_dataset_signal_inventory" in tools
    assert "extract_events_table" in tools
    assert "get_dataset_papers" in tools
    assert "resolve_dataset_papers" in tools
    assert "query_dataset_papers" in tools
    assert "explain_dataset_variable" in tools
    assert "register_paper_pdf" in tools
    assert "list_missing_paper_pdfs" in tools
    assert "generate_dataset_explorer" in tools
    assert "explain_visual_dataset_selection" in tools
