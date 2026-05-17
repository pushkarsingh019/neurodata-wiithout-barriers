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

## MCP Harness

Use the root harness scripts to connect all three servers from MCP clients such as Claude Desktop, Codex-style agents, and OpenCode-style local runners:

```bash
python harness/check_servers.py
python harness/generate_mcp_config.py --format mcp-json
```

See [docs/HARNESS.md](docs/HARNESS.md) for generated config formats and recommended usage.

## Documentation Site

The repository includes a unified MkDocs Material documentation site for all three MCP servers:

```bash
mkdocs build --strict
mkdocs serve
```

Start with [docs/index.md](docs/index.md), then read the server guides under [docs/mcps](docs/mcps).
