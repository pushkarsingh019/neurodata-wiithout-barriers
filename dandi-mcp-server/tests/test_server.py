from __future__ import annotations

import asyncio

from dandi_mcp.server import mcp


def test_server_exposes_broad_dandi_tool_surface() -> None:
    tools = {tool.name for tool in asyncio.run(mcp.list_tools())}

    expected = {
        "get_storage_info",
        "register_local_dandiset",
        "register_local_dataset",
        "summarize_local_dandiset",
        "summarize_local_dataset",
        "browse_local_dandiset",
        "browse_local_dataset",
        "inspect_nwb_file",
        "index_local_dandiset",
        "index_local_dataset",
        "get_dataset_signal_inventory",
        "extract_trials_table",
        "generate_dataset_report",
        "search_dandisets",
        "get_dandiset",
        "list_dandiset_versions",
        "get_dandiset_version_metadata",
        "list_assets",
        "list_asset_paths",
        "get_asset_metadata",
        "get_asset_info_by_id",
        "get_version_asset_metadata",
        "get_asset_validation",
        "get_archive_info",
        "get_archive_stats",
        "get_schema",
        "list_available_schemas",
        "list_users",
        "search_users",
        "list_zarr_archives",
        "list_zarr_files",
        "create_dandiset",
        "delete_dandiset",
        "publish_dandiset_version",
        "initialize_upload",
        "finalize_zarr_archive",
        "call_dandi_api",
    }

    assert expected <= tools
    assert len(tools) >= 50
