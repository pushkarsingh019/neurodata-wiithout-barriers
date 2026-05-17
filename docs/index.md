# Neurodata Without Barriers

Neurodata Without Barriers is a collection of Model Context Protocol servers that let AI agents discover, inspect, download, and locally explore neuroscience datasets. The repository currently includes servers for DANDI, OpenNeuro, and the International Brain Laboratory.

The project has two complementary goals. First, each server exposes the native public data infrastructure for its ecosystem, such as DANDI Archive assets, OpenNeuro BIDS metadata, and IBL OpenAlyx sessions. Second, all three servers now share a compatible local dataset explorer workflow so an agent can register downloaded data, scan local files, build an index, inspect subjects and sessions, summarize analysis-ready signals, and generate a Markdown report.

## Server Map

| Server | Primary ecosystem | Strengths |
| --- | --- | --- |
| DANDI MCP | DANDI Archive, NWB, Zarr | Dandisets, versions, assets, download URLs, Zarr listings, local NWB inspection, NWBInspector validation, signal inventory, trial previews |
| OpenNeuro MCP | OpenNeuro, BIDS | Dataset search, BIDS file classification, participants, tasks, events, derivatives, semantic search, local BIDS indexing |
| IBL MCP | International Brain Laboratory, OpenAlyx, ALF | Sessions, datasets, file records, subjects, insertions, channels, behavior summaries, ecephys metadata, local ALF-style indexing |

## What The Shared Explorer Adds

The shared local explorer API gives all three servers a common shape:

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

This means an agent can follow the same high-level workflow no matter where the data came from. DANDI still adds NWB-specific tools, OpenNeuro still adds BIDS events extraction, and IBL still keeps ALF/session-specific intelligence.

## Recommended Reading

Start with [Getting Started](getting-started.md) to install and run the servers. Then read [Shared Local Explorer](shared-local-explorer.md) to understand the compatible workflow. Finally, use the server-specific guides for [DANDI](mcps/dandi.md), [OpenNeuro](mcps/openneuro.md), and [IBL](mcps/ibl.md).
