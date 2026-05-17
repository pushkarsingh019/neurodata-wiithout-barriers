from __future__ import annotations

import asyncio

from ibl_mcp.server import mcp


def test_server_exposes_rich_ibl_tool_surface() -> None:
    tools = {tool.name for tool in asyncio.run(mcp.list_tools())}

    expected = {
        "list_alyx_endpoints",
        "describe_alyx_endpoint",
        "search_sessions",
        "get_session",
        "summarize_session",
        "get_session_metadata",
        "get_session_datasets",
        "list_datasets",
        "get_dataset",
        "list_files",
        "get_dataset_download_urls",
        "download_url",
        "list_insertions",
        "get_insertion",
        "list_trajectories",
        "list_channels",
        "list_subjects",
        "search_subjects",
        "list_brain_regions",
        "get_brain_regions",
        "list_dataset_types",
        "list_data_formats",
        "list_tags",
        "list_labs",
        "list_projects",
        "search_labs",
        "search_projects",
        "search_task_protocols",
        "search_behavioral_sessions",
        "search_neural_recording_sessions",
        "get_trials",
        "get_behavior_summary",
        "get_psychometric_summary",
        "get_wheel_data",
        "get_lick_data",
        "get_video_metadata",
        "get_spike_metadata",
        "get_cluster_qc",
        "align_behavior_to_events",
        "align_spikes_to_events",
        "semantic_search",
        "get_related_papers",
        "get_associated_code",
        "query_knowledge_graph",
        "get_cache_info",
        "get_cache_zip_url",
        "call_alyx_api",
        "confirmed_mutating_alyx_api",
    }

    assert expected <= tools
    assert len(tools) >= 55
