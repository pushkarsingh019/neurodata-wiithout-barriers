# Shared Local Explorer

The shared local explorer is the compatibility layer across DANDI, OpenNeuro, and IBL. It lets agents operate downloaded datasets through the same high-level workflow even though the underlying data formats are different.

## Core Workflow

The standard workflow is:

```text
register_local_dataset
summarize_local_dataset
browse_local_dataset
list_local_files
index_local_dataset
get_dataset_subjects
get_dataset_sessions
get_dataset_signal_inventory
generate_dataset_report
```

The workflow is intentionally conservative. Registration and indexing read source files and write derived manifests, indexes, and reports into MCP storage. They do not modify the source dataset.

## Register

Use `register_local_dataset` when a dataset has already been downloaded:

```json
{
  "path": "/data/001097",
  "dataset_id": "001097"
}
```

For DANDI, `dataset_id` is the Dandiset identifier. The DANDI server also keeps the more specific `register_local_dandiset` tool.

For OpenNeuro, `dataset_id` is usually an OpenNeuro ID such as `ds000001`.

For IBL, registration can use `session_id` or `dataset_id`, because local IBL downloads are often session-centered or dataset-record-centered.

## Summarize

Use `summarize_local_dataset` after registration. It returns a quick orientation:

- Dataset key
- Provider identifier
- Local root path
- File counts and file type counts
- Subjects and sessions, if detected
- Provider-specific scientific structure
- Index status
- Sample files

This is the lowest-cost call for "what did I just download?"

## Browse

Use `browse_local_dataset` to inspect directory structure without returning every file. The tool reports direct children under a path prefix:

```json
{
  "dataset_key": "DANDI_001097_0.240814.1849",
  "path_prefix": "sub-m541"
}
```

This is useful for quickly seeing whether data is organized by subject, session, acquisition, collection, probe, or derivative folder.

## List Files

Use `list_local_files` when you need filtered files:

```json
{
  "dataset_key": "OPENNEURO_ds000001_local",
  "glob": "sub-*/func/*_events.tsv",
  "limit": 20
}
```

Common filters:

| Filter | Meaning |
| --- | --- |
| `glob` | Match paths using shell-style wildcards |
| `file_type` | Match extension-like type, such as `nwb`, `tsv`, `npy`, or `json` |
| `subject` | Match detected subject identifier |
| `limit` | Bound result size |

## Index

Use `index_local_dataset` to build a provider-specific scientific inventory. The output shape is compatible, but the semantics are provider-aware.

| Server | Local index focus |
| --- | --- |
| DANDI | NWB files, subjects, sessions, devices, processing modules, time series, trials, units, validation status |
| OpenNeuro | BIDS subjects, sessions, tasks, participants, events, modalities, BIDS suffixes |
| IBL | ALF collections, objects, attributes, subjects, sessions, behavior/ecephys/video modalities |

Indexing writes a cached `index.json` into MCP storage. Later calls such as `get_dataset_subjects`, `get_dataset_sessions`, and `get_dataset_signal_inventory` reuse that index when available.

## Signal Inventory

Use `get_dataset_signal_inventory` to answer "what can I analyze?"

The meaning varies by provider:

| Server | Inventory rows describe |
| --- | --- |
| DANDI | NWB object paths, neurodata types, shapes, rates, units, and source files |
| OpenNeuro | BIDS files with modality, suffix, task, subject, and size |
| IBL | ALF object/attribute pairs with collection, modality, and size |

The shared name is deliberately broad: it points agents toward analysis-relevant local data without pretending every ecosystem has the same internal file model.

## Reports

Use `generate_dataset_report` to create a Markdown report under MCP artifact storage. Reports include the provider identifier, source path, subjects, sessions, modalities, and provider-specific inventory.

Reports are written outside the source dataset so the original download remains untouched.

## Safety And Performance

The local explorer follows these rules:

- Read source datasets but do not mutate them.
- Cache manifests, indexes, and reports under MCP storage.
- Return bounded previews instead of loading large arrays by default.
- Let provider-specific tools expose deeper format-aware inspection.
- Prefer explicit paths when ID-based lookup cannot find a dataset.

For very large datasets, call `summarize_local_dataset` and `browse_local_dataset` first, then index narrower subsets when provider-specific tools support limits.
