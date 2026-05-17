# OpenNeuro MCP

The OpenNeuro MCP server provides a BIDS-aware semantic interface for OpenNeuro datasets. It can query remote OpenNeuro metadata and also inspect downloaded BIDS datasets locally.

## What It Is For

Use the OpenNeuro MCP when you need to:

- Search OpenNeuro datasets by keyword, modality, species, task, author, institution, or behavioral paradigm.
- Retrieve and enrich `dataset_description.json`.
- Browse BIDS file trees and classify files by modality and BIDS entities.
- Parse participants and events metadata.
- Discover derivative directories and analysis pipelines.
- Extract paper and code links.
- Build semantic and graph-style dataset relationships.
- Register and inspect a downloaded BIDS dataset locally.
- Generate a local BIDS dataset report.

## Remote OpenNeuro Tools

| Area | Representative tools |
| --- | --- |
| Discovery | `search_datasets`, `semantic_search`, `ontology_search`, `modality_search`, `species_search`, `task_search` |
| Metadata | `get_dataset_metadata`, `get_dataset_files`, `get_modalities`, `get_subject_info` |
| Tasks and events | `get_task_structure`, `get_events`, `find_behavioral_paradigms` |
| Derivatives and code | `get_derivatives`, `get_analysis_pipelines`, `get_associated_code` |
| Literature and graph | `get_related_papers`, `find_similar_datasets`, `query_knowledge_graph` |

The OpenNeuro server is read-only by design.

## Local Dataset Tools

OpenNeuro implements the shared local explorer workflow:

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

OpenNeuro also provides:

```text
extract_events_table
```

This tool reads a local BIDS `events.tsv` file and returns a bounded preview with columns, row count, trial types, onset range, and duration range.

## Local BIDS Index

The local OpenNeuro index captures:

- Dataset ID and tag.
- Dataset name and BIDS version from `dataset_description.json`.
- File counts and file type counts.
- BIDS subjects and sessions.
- Tasks from `task-` entities.
- Modalities inferred from BIDS paths and suffixes.
- Participants summary from `participants.tsv`.
- Events file summaries.
- A signal/file inventory with path, modality, suffix, task, subject, and size.

## Example: Explore A Downloaded OpenNeuro Dataset

Register a local dataset:

```json
{
  "path": "/data/ds000001",
  "dataset_id": "ds000001",
  "tag": "local"
}
```

Summarize it:

```json
{
  "dataset_key": "OPENNEURO_ds000001_local"
}
```

Find event files:

```json
{
  "dataset_key": "OPENNEURO_ds000001_local",
  "glob": "sub-*/func/*_events.tsv"
}
```

Extract a task's event table preview:

```json
{
  "dataset_key": "OPENNEURO_ds000001_local",
  "task": "rest",
  "limit": 20
}
```

## Local Output

The OpenNeuro local explorer writes:

```text
<storage-root>/openneuro/local-datasets/<dataset-key>/manifest.json
<storage-root>/openneuro/local-datasets/<dataset-key>/index.json
<storage-root>/openneuro/artifacts/<dataset-key>/dataset-report.md
```

Source BIDS files are not modified.

## Current Boundaries

The local OpenNeuro explorer is metadata- and table-oriented. It indexes BIDS structure and parses participants/events files, but it does not yet run the full BIDS Validator, load NIfTI images, inspect EEG/MEG binary headers, or compute neuroimaging quality metrics.
