# IBL / OpenAlyx MCP Coverage

This MCP server prioritizes the public OpenAlyx REST surface used by the ONE API. It exposes typed tools for common agent workflows and a guarded generic `call_alyx_api` tool for endpoint coverage that may vary across Alyx deployments.

| Alyx Endpoint | MCP Coverage |
|---|---|
| `/` | `list_alyx_endpoints` |
| `/{endpoint}/` OPTIONS | `describe_alyx_endpoint` |
| `/sessions/`, `/sessions/{id}/` | `search_sessions`, `get_session`, `summarize_session`, resources |
| `/sessions/`, `/datasets/`, `/insertions/` combined | `get_session_metadata`, `get_session_datasets`, `search_behavioral_sessions`, `search_neural_recording_sessions` |
| `/datasets/`, `/datasets/{id}/` | `list_datasets`, `get_dataset`, `get_dataset_download_urls`, `get_trials`, `get_behavior_summary`, `get_psychometric_summary`, `get_wheel_data`, `get_lick_data`, `get_video_metadata`, `get_pose_data`, `get_pupil_data`, `get_spike_metadata`, `get_cluster_qc`, resources |
| `/files/` | `list_files`, `get_dataset_download_urls`, high-level array loaders |
| `/insertions/`, `/insertions/{id}/` | `list_insertions`, `search_probe_insertions`, `get_insertion`, `get_probe_metadata`, resources |
| `/trajectories/` | `list_trajectories` |
| `/channels/` | `list_channels` |
| `/subjects/` | `list_subjects`, `search_subjects` |
| `/brain-regions/` | `list_brain_regions`, `get_brain_regions` |
| `/dataset-types/` | `list_dataset_types` |
| `/data-formats/` | `list_data_formats` |
| `/tags/` | `list_tags` |
| `/labs/` | `list_labs`, `search_labs` |
| `/projects/` | `list_projects`, `search_projects` |
| `/revisions/` | `list_revisions` |
| `/downloads/` | `list_downloads` |
| `/tasks/` | `list_tasks` |
| `/cache/`, `/cache.zip` | `get_cache_info`, `get_cache_zip_url`, `ibl://cache` |
| Any read endpoint | `call_alyx_api(method="GET"|"OPTIONS", path=...)` |
| Authenticated mutation endpoints | `confirmed_mutating_alyx_api(..., confirm=true)` |

Local semantic/knowledge tools that do not map one-to-one to Alyx endpoints:

| Local Layer | MCP Coverage |
|---|---|
| IBL dataset ontology | `semantic_search`, `find_similar_sessions`, `query_knowledge_graph` |
| Publication/code registry | `get_related_papers`, `get_associated_code` |
| Event alignment | `align_behavior_to_events`, `align_spikes_to_events` |

The live OpenAlyx endpoint list currently includes additional endpoints such as `downloads`, `new-download`, `notes`, `procedures`, `revisions`, `tasks`, `uploaded`, `users`, water administration endpoints, and surgery endpoints. These are reachable with `call_alyx_api`; narrow named tools can be added later if agent workflows need specialized ergonomics around those records.
