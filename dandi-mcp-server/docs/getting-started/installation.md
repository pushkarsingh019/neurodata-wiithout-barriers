# Installation

## Requirements

- Python 3.10 or newer.
- [`uv`](https://docs.astral.sh/uv/) is recommended.
- Network access to `https://api.dandiarchive.org`.

## Install With uv

From this repository:

```bash
cd /Users/pushkarsingh/Documents/side-projects/paper-lineage-cli/dandi-mcp-server
uv sync --extra dev
```

Run the server:

```bash
uv run dandi-mcp
```

## Install With pip

```bash
cd /Users/pushkarsingh/Documents/side-projects/paper-lineage-cli/dandi-mcp-server
python -m pip install -e ".[dev]"
dandi-mcp
```

## Verify

```bash
uv run --extra dev pytest
```

You can also start the MCP Inspector:

```bash
uv run mcp dev src/dandi_mcp/server.py
```
