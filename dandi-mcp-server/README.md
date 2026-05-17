# DANDI MCP Server

`dandi-mcp-server` is a read-only MCP server for exploring the [DANDI Archive](https://dandiarchive.org). It gives an agent structured access to Dandisets, versions, assets, folder-like paths, metadata, and signed download URLs without requiring a DANDI account for public data.

The default workflow is conservative, but the server now covers the full current DANDI Swagger surface. Read operations are exposed directly. Mutating operations are present as named tools with explicit confirmation flags, and `call_dandi_api` can reach any current or future API path.

The server also includes an early neuroscience intelligence layer: semantic dataset search, heuristic ontology extraction, behavioral/NWB path summaries, literature link extraction, and knowledge-graph shaped outputs for AI agents. This is a deterministic baseline, not yet a corpus-scale vector database or full NWB parser.

## Install

```bash
cd dandi-mcp-server
uv sync --extra dev
```

Or with pip:

```bash
python -m pip install -e ".[dev]"
```

## Run

```bash
uv run dandi-mcp
```

For MCP Inspector:

```bash
uv run mcp dev src/dandi_mcp/server.py
```

## Claude Desktop / Codex-style config

Use the absolute path to this project:

```json
{
  "mcpServers": {
    "dandi": {
      "command": "uv",
      "args": [
        "--directory",
        "/Users/pushkarsingh/Documents/side-projects/paper-lineage-cli/dandi-mcp-server",
        "run",
        "dandi-mcp"
      ]
    }
  }
}
```

## Tools

| Tool | Purpose |
|---|---|
| `search_dandisets` | Search/list Dandisets with pagination and ordering. |
| `get_dandiset` | Fetch Dandiset-level metadata for an identifier. |
| `list_dandiset_versions` | List draft and published versions. |
| `get_dandiset_version_metadata` | Fetch full metadata for a specific version. |
| `list_assets` | List assets in a version, with path/glob filters and optional metadata. |
| `list_asset_paths` | Browse direct child files/folders under a path prefix. |
| `get_asset_metadata` | Fetch detailed metadata for an asset UUID. |
| `get_asset_download_url` | Resolve a time-limited object-store URL for an asset. |
| `summarize_dandiset` | Return compact metadata plus sample assets for quick agent orientation. |
| `search_datasets` | Agent-first semantic search across topic, species, modality, behavior, and brain-region terms. |
| `semantic_search_dandisets` | DANDI keyword retrieval followed by local lexical/ontology reranking. |
| `analyze_dandiset_neuroscience` | Extract inferred species, modalities, behaviors, brain regions, literature links, and NWB path hints. |
| `get_related_papers` | Extract DOI, PubMed, Semantic Scholar, GitHub, protocols.io, and related-resource links from metadata. |
| `find_similar_datasets` | Find datasets similar to a source Dandiset using inferred neuroscience profile terms. |
| `find_behavioral_paradigms` | Search for datasets with behavioral task, paradigm, trial, stimulus, or reward hints. |
| `get_dandiset_knowledge_graph`, `query_knowledge_graph` | Build and query an inferred graph of datasets, papers, species, modalities, behaviors, and brain regions. |
| `get_archive_info`, `get_archive_stats` | Inspect archive service metadata and statistics. |
| `get_schema`, `list_available_schemas` | Inspect DANDI schema models. |
| `list_users`, `search_users`, `get_current_user` | User-related API helpers. |
| `list_zarr_archives`, `get_zarr_archive`, `list_zarr_files` | Zarr archive discovery and file listing. |
| `create_*`, `update_*`, `delete_*`, `publish_*`, upload tools | Authenticated mutating API operations guarded by `confirm=true`. |
| `call_dandi_api` | Universal fallback for the full DANDI API surface. |

See [docs/API_COVERAGE.md](docs/API_COVERAGE.md) for the endpoint-by-endpoint coverage matrix and [docs/ARCHITECTURE_AUDIT.md](docs/ARCHITECTURE_AUDIT.md) for the current gap analysis and roadmap.

## Resource Templates

| Resource | Purpose |
|---|---|
| `dandi://dandisets/recent` | Recently modified Dandisets. |
| `dandi://dandiset/{dandiset_id}` | Dandiset record. |
| `dandi://dandiset/{dandiset_id}/{version}` | Version metadata. |
| `dandi://dandiset/{dandiset_id}/{version}/assets` | First page of assets. |
| `dandi://asset/{asset_id}` | Asset metadata. |
| `dandi://archive/info` | Archive service information. |
| `dandi://archive/stats` | Archive statistics. |
| `dandi://schemas/available` | Available schema models. |
| `dandi://zarr/{zarr_id}` | Zarr archive metadata. |

## Authenticated and Mutating Operations

Set one of these environment variables for authenticated API calls:

```bash
export DANDI_API_TOKEN="your_token_here"
# or
export DANDI_API_KEY="your_token_here"
```

Mutating tools are blocked unless called with `confirm=true`. This includes creating, updating, publishing, deleting, starring, upload, and Zarr mutation operations.

## Prompts

| Prompt | Purpose |
|---|---|
| `explore_dandiset` | Guide an agent through inspecting one Dandiset. |
| `find_relevant_dandisets` | Search strategy for a topic/species/modality. |
| `inspect_asset_for_reuse` | Checklist for deciding whether an asset is useful for analysis. |

## Tests

```bash
uv run --extra dev pytest
```

## Notes

DANDI standardizes deposited data around community formats, especially NWB for neurophysiology and BIDS for neuroimaging/microscopy. This server exposes DANDI's public REST API rather than parsing NWB/BIDS payloads directly. A natural next step is adding optional NWB/Zarr metadata sniffing for selected assets.
