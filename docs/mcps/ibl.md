# IBL MCP

The IBL MCP server provides access to International Brain Laboratory data through OpenAlyx/Alyx and adds a local explorer for downloaded ALF-style files.

## What It Is For

Use the IBL MCP when you need to:

- Search IBL sessions by subject, lab, project, protocol, brain region, dataset presence, or QC.
- Inspect session metadata, subject records, dataset records, file records, and object-store locations.
- Discover Neuropixels insertions, trajectories, channels, and brain region assignments.
- Summarize behavioral trials, wheel data, licking data, video metadata, spikes, and cluster QC when available through the domain service.
- Resolve dataset download URLs and download explicit files.
- Register local IBL/ALF-style downloads.
- Build a local index over subjects, sessions, collections, ALF objects, attributes, and modalities.
- Generate local dataset reports.

## Remote OpenAlyx Tools

| Area | Representative tools |
| --- | --- |
| Endpoint discovery | `list_alyx_endpoints`, `describe_alyx_endpoint` |
| Sessions | `search_sessions`, `get_session`, `summarize_session`, `get_session_metadata` |
| Datasets and files | `list_datasets`, `get_dataset`, `list_files`, `get_dataset_download_urls`, `download_url` |
| Subjects and labs | `list_subjects`, `search_subjects`, `list_labs`, `list_projects`, `list_tags` |
| Ecephys anatomy | `list_insertions`, `get_insertion`, `list_trajectories`, `list_channels`, `list_brain_regions` |
| Behavior and signals | `get_trials`, `get_behavior_summary`, `get_wheel_data`, `get_lick_data`, `get_video_metadata`, `get_spike_metadata`, `get_cluster_qc` |
| Reasoning | `semantic_search`, `get_related_papers`, `get_associated_code`, `query_knowledge_graph` |
| Escape hatches | `call_alyx_api`, `confirmed_mutating_alyx_api` |

Mutating Alyx calls are guarded behind explicit confirmation.

## Local Dataset Tools

IBL implements the shared local explorer workflow:

```text
register_local_dataset
list_local_datasets
summarize_local_dataset
browse_local_dataset
list_local_files
index_local_dataset
get_dataset_subjects
get_dataset_sessions
get_dataset_signal_inventory
generate_dataset_report
```

## Local ALF Index

The local IBL explorer scans downloaded files and extracts:

- Subject identifiers from `sub-` path tokens.
- Session identifiers from `ses-` path tokens or UUID-like path tokens.
- Collections such as `alf`, `alf/probe00`, or other nested directories.
- ALF object names and attributes from filenames such as `_ibl_trials.intervals.npy` or `spikes.times.npy`.
- File types and sizes.
- Inferred modalities such as behavior, ecephys, and video.

The signal inventory is ALF-aware. Rows include source file, collection, ALF object, ALF attribute, modality, and size.

## Example: Explore A Downloaded IBL Session

Register by local path:

```json
{
  "path": "/data/ibl/session-abc",
  "session_id": "session-abc"
}
```

Summarize and index:

```json
{
  "dataset_key": "IBL_session-abc"
}
```

Filter local files:

```json
{
  "dataset_key": "IBL_session-abc",
  "glob": "**/spikes.*.npy",
  "limit": 50
}
```

Generate a local report:

```json
{
  "dataset_key": "IBL_session-abc"
}
```

## Local Output

The IBL local explorer writes:

```text
<storage-root>/ibl/local-datasets/<dataset-key>/manifest.json
<storage-root>/ibl/local-datasets/<dataset-key>/index.json
<storage-root>/ibl/artifacts/<dataset-key>/dataset-report.md
```

Source ALF files are not modified.

## Current Boundaries

The local IBL explorer currently indexes file organization and ALF naming semantics. It does not yet load `.npy` arrays, compute trial statistics from local files, align spikes to events locally, or validate local ALF datasets against ONE conventions. Those capabilities can be layered on top of the current manifest and signal inventory.
