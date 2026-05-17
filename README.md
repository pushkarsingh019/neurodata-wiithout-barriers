# Neurodata Without Barriers

Neurodata Without Barriers is a suite for making neuroscience datasets easier for agents and researchers to discover, inspect, index, explain, and reuse. It combines Model Context Protocol servers, a hostable browser app, shared local dataset tooling, literature-aware variable explanation, and project documentation.

The repository does not ship local datasets, NWB files, generated figures, demo videos, or session transcripts. Public archive metadata is fetched at runtime, and local data stays in user-provided paths or runtime cache volumes.

## What Is Included

| Area | Path | What it does |
| --- | --- | --- |
| DANDI MCP server | `dandi-mcp-server` | Explores DANDI dandisets, versions, assets, download URLs, NWB/Zarr metadata, local NWB files, NWBInspector validation, trial/event previews, signal inventories, and DANDI-linked literature. |
| OpenNeuro MCP server | `openneuro-mcp-server` | Searches OpenNeuro, classifies BIDS files, inspects participants/tasks/events/derivatives, supports semantic discovery, and indexes local BIDS datasets. |
| IBL MCP server | `ibl-mcp-server` | Works with International Brain Laboratory OpenAlyx sessions, datasets, file records, subjects, probes, channels, behavior summaries, ecephys metadata, and local ALF-style files. |
| Shared local explorer | all MCP servers | Provides a common workflow for registering local datasets, browsing files, indexing contents, listing subjects/sessions, extracting signal inventories, and generating reports. |
| Literature tools | all MCP servers | Resolves dataset-related papers, queries abstracts/full text when available, explains variables with evidence, tracks missing PDFs, and lets users register local paper PDFs. |
| Web explorer | `web-app` | React + FastAPI app for DANDI dataset pages, local NWB indexing, variable maps, local-model summaries, code snippets, and dataset skill export. |
| Hosting assets | `Dockerfile`, `docker-compose.web.yml` | Builds the web frontend and backend into a single deployable service with persistent runtime storage. |
| MCP harness | `harness` | Checks server entry points and generates MCP client configuration for Claude Desktop, Codex-style agents, OpenCode-style runners, and JSON-based MCP clients. |
| Documentation site | `docs`, `mkdocs.yml` | Unified MkDocs documentation covering installation, server guides, local explorer workflows, compatibility, harness usage, and development. |

## Quick Start

Run the web app as a single service:

```bash
docker compose -f docker-compose.web.yml up --build
```

Open `http://127.0.0.1:8787`, paste a DANDI ID or URL, and explore the dataset. Optional runtime overrides live in [web-app/.env.example](web-app/.env.example).

Deploy the web app to Vercel:

```bash
npx vercel --prod
```

The Vercel deployment uses [vercel.json](vercel.json), builds the Vite app from `web-app/frontend`, serves the static frontend, and routes `/api/*` to the FastAPI app in [api/index.py](api/index.py). Local filesystem indexing is still intended for local/Docker runs; Vercel should be treated as the public metadata and documentation host unless you attach external storage.

Generate MCP client configuration for the server suite:

```bash
python harness/check_servers.py
python harness/generate_mcp_config.py --format mcp-json
```

## Web App

The web app is designed for easy hosting and low repository weight. The FastAPI backend can serve the built React frontend, so the Docker path runs as one container. The app can:

- Resolve DANDI IDs and URLs into dataset pages.
- Fetch DANDI metadata, asset summaries, paper links, and variable-level metadata.
- Use an OpenAI-compatible model endpoint for grounded dataset and variable explanations.
- Index a user-provided local Dandiset path at runtime for richer NWB variable maps.
- Export a dataset-specific skill zip for agent workflows.
- Show built-in documentation at `/docs`.

For local development, see [web-app/README.md](web-app/README.md).

## MCP Server Suite

Each server can run independently and has its own `README.md`, `pyproject.toml`, tests, and runtime entry point. The shared workflow gives agents the same high-level tool pattern across providers:

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
resolve_dataset_papers
query_dataset_papers
explain_dataset_variable
generate_dataset_explorer
```

Provider-specific tools remain available for domain details, such as DANDI NWB inspection, OpenNeuro BIDS events, and IBL OpenAlyx session metadata.

## Data And Runtime Policy

The repository ignores local datasets and generated artifacts, including `*.nwb`, `001097/`, `figures/`, `harness/generated/`, `.mcp-storage/`, frontend build output, dependency folders, and session transcripts. Runtime indexes and caches should live in `NEURODATA_MCP_STORAGE_DIR`, which defaults to `.mcp-storage` locally and `/data/.mcp-storage` in Docker.

## Development

Install dependencies from an individual project directory:

```bash
uv sync --extra dev
```

Run tests from an individual project directory:

```bash
uv run pytest
```

Build the frontend:

```bash
cd web-app/frontend
npm install
npm run build
```

## Documentation

The unified documentation site uses MkDocs Material:

```bash
mkdocs build --strict
mkdocs serve
```

Start with [docs/index.md](docs/index.md), then read [docs/getting-started.md](docs/getting-started.md), [docs/shared-local-explorer.md](docs/shared-local-explorer.md), [docs/reference/tool-compatibility.md](docs/reference/tool-compatibility.md), and the provider guides under [docs/mcps](docs/mcps).
