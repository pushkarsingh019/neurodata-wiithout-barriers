# Neurodata Without Barriers

This repository collects Model Context Protocol servers for neuroscience data discovery.

## Projects

| Directory | Description |
| --- | --- |
| `dandi-mcp-server` | MCP server for exploring DANDI Archive dandisets, assets, metadata, and download URLs. |
| `ibl-mcp-server` | MCP server for International Brain Laboratory OpenAlyx data discovery and inspection. |
| `openneuro-mcp-server` | MCP server for semantic discovery and BIDS-aware reasoning over OpenNeuro datasets. |

Each project has its own `README.md`, `pyproject.toml`, tests, and runtime entry point.

## Development

Install dependencies from an individual project directory:

```bash
uv sync --extra dev
```

Run tests from an individual project directory:

```bash
uv run pytest
```
