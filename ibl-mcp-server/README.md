# IBL MCP Server

`ibl-mcp-server` is a Model Context Protocol server for International Brain Laboratory public data. It gives agents a one-stop AI-native interface for OpenAlyx/Alyx discovery, session search, dataset and file inspection, behavioral summaries, Neuropixels insertion anatomy, QC-aware warnings, paper/code lookup, semantic search scaffolding, knowledge graph scaffolding, and explicit URL downloads.

The server talks directly to the public Alyx REST API at `https://openalyx.internationalbrainlab.org` by default. Alyx documents that its base URL exposes available endpoints and that `/docs/` provides endpoint details. The ONE examples list the main OpenAlyx endpoints, including `sessions`, `datasets`, `files`, `insertions`, `trajectories`, `channels`, `subjects`, `brain-regions`, `dataset-types`, `data-formats`, `tags`, `projects`, `labs`, `cache`, and `cache.zip`.

## Install

```bash
cd ibl-mcp-server
uv sync --extra dev
```

Or with pip:

```bash
python -m pip install -e ".[dev]"
```

## Run

```bash
uv run ibl-mcp
```

For MCP Inspector:

```bash
uv run mcp dev src/ibl_mcp/server.py
```

## Client Config

```json
{
  "mcpServers": {
    "ibl": {
      "command": "uv",
      "args": [
        "--directory",
        "/Users/pushkar_nairlab/Documents/03_side_projects/neurodata-without-barriers/ibl-mcp-server",
        "run",
        "ibl-mcp"
      ]
    }
  }
}
```

## Environment

| Variable | Purpose |
|---|---|
| `IBL_ALYX_BASE_URL` | Alyx/OpenAlyx base URL. Defaults to `https://openalyx.internationalbrainlab.org`. |
| `IBL_ALYX_TIMEOUT` | HTTP timeout in seconds. Defaults to `45`. |
| `IBL_ALYX_TOKEN` | Optional Alyx token for authenticated servers. |
| `IBL_ALYX_USERNAME`, `IBL_ALYX_PASSWORD` | Optional basic auth credentials when a token is not provided. |
| `IBL_MCP_DOWNLOAD_DIR` | Directory for `download_url`. Defaults to `~/.cache/ibl-mcp/downloads`. |

## Tools

| Tool | Purpose |
|---|---|
| `list_alyx_endpoints` | List the live Alyx endpoint surface. |
| `describe_alyx_endpoint` | Fetch OPTIONS/schema metadata for an endpoint. |
| `search_sessions` | Search IBL sessions by subject, lab, project, protocol, date range, datasets, brain region, QC, or Django lookups. |
| `get_session`, `summarize_session`, `get_session_metadata` | Read a session and summarize datasets, modalities, QC, provenance, and probe insertions. |
| `get_session_datasets` | Return modality-aware dataset inventory with warnings. |
| `list_datasets`, `get_dataset` | Discover and inspect dataset records. |
| `list_files`, `get_dataset_download_urls`, `download_url` | Resolve file/object-store URLs and download explicit URLs locally. |
| `search_behavioral_sessions`, `get_trials`, `get_behavior_summary`, `get_psychometric_summary` | Behavioral neuroscience tools for trial arrays, performance, bias, reaction time, and psychometric curves. |
| `get_wheel_data`, `get_lick_data`, `get_video_metadata`, `get_pose_data`, `get_pupil_data` | Behavioral modality availability and array summaries. |
| `list_insertions`, `search_probe_insertions`, `get_insertion`, `get_probe_metadata` | Search/read Neuropixels probe insertions. |
| `list_trajectories`, `list_channels` | Inspect histology/alignment trajectories and channel brain-region assignments. |
| `search_neural_recording_sessions`, `get_spike_metadata`, `get_spike_times`, `get_cluster_qc` | Neural recording and cluster QC tools. |
| `align_behavior_to_events`, `align_spikes_to_events` | Basic multimodal event alignment. |
| `list_subjects`, `search_subjects`, `list_brain_regions`, `get_brain_regions` | Inspect mice and Allen CCF regions. |
| `list_dataset_types`, `list_data_formats` | Understand dataset names, ALF types, and registered formats. |
| `list_tags`, `list_labs`, `search_labs`, `list_projects`, `search_projects`, `search_task_protocols` | Browse release tags, labs, projects, and derived task protocols. |
| `get_related_papers`, `get_associated_code` | Link topics/projects to IBL publications and repositories. |
| `semantic_search`, `find_similar_sessions`, `query_knowledge_graph` | Local semantic and graph scaffolds for agent reasoning. |
| `get_cache_info`, `get_cache_zip_url` | Inspect/download public ONE cache metadata. |
| `list_revisions`, `list_downloads`, `list_tasks` | Inspect revisions, downloads, and pipeline tasks where exposed by Alyx. |
| `call_alyx_api` | Read any current or future Alyx path. Mutations are blocked by default. |
| `confirmed_mutating_alyx_api` | Authenticated mutation escape hatch requiring `confirm=true`. |

## Resource Templates

| Resource | Purpose |
|---|---|
| `ibl://endpoints` | Advertised Alyx endpoints. |
| `ibl://sessions` | First page/list of public sessions. |
| `ibl://session/{session_id}` | One session record. |
| `ibl://session/{session_id}/datasets` | Datasets for a session. |
| `ibl://session/{session_id}/insertions` | Probe insertions for a session. |
| `ibl://dataset/{dataset_id}` | One dataset record. |
| `ibl://cache` | ONE cache metadata. |

## Prompts

| Prompt | Purpose |
|---|---|
| `find_ibl_data` | Search strategy for a scientific topic, modality, subject, or release. |
| `download_ibl_dataset` | Step-by-step safe download workflow from session to dataset to URL. |
| `explain_ibl_session` | Agent workflow for understanding a session before analysis reuse. |

## Query Examples

Find public sessions with a specific dataset:

```json
{
  "datasets": "spikes.times.npy",
  "project": "brainwide",
  "atlas_acronym": "VISp"
}
```

Find sessions belonging to a release tag with a Django lookup:

```json
{
  "django": "data_dataset_session_related__tags__name,2022_Q2_IBL_et_al_RepeatedSite"
}
```

Find datasets in probe collections for one session:

```json
{
  "session": "ba892860-149e-4bff-9961-aa6583d96661",
  "django": "collection__regex,.*probe.*",
  "exists": true
}
```

## Tests

```bash
uv --cache-dir .uv-cache run --extra dev pytest
```

## Audit And Roadmap

See [docs/AUDIT_REPORT.md](docs/AUDIT_REPORT.md) for the architecture audit, feature matrix, gap analysis, refactor summary, test results, and roadmap for DANDI, OpenNeuro, NWB, Brainlife, and Allen Brain Atlas integration.

## Sources

- [Alyx REST API documentation](https://alyx.readthedocs.io/en/latest/api.html)
- [IBL data download and ONE setup documentation](https://docs.internationalbrainlab.org/notebooks_external/data_download.html)
- [Useful Alyx REST queries in ONE documentation](https://int-brain-lab.github.io/ONE/notebooks/useful_alyx_queries.html)
