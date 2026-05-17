# Getting Started

Each MCP server is an independent Python package with its own entry point, tests, and dependencies. You can run one server at a time, or generate a combined MCP client configuration from the root harness.

## Requirements

Use Python 3.10 or newer. The repository uses `uv` for reproducible installs, but the packages can also be installed with `pip` in editable mode.

The DANDI local NWB explorer uses PyNWB and NWBInspector. Those dependencies are available through the DANDI server's `analysis` extra and are included in its development extra.

## Install A Server

From a server directory, install its development dependencies:

```bash
cd dandi-mcp-server
uv sync --extra dev
```

The same pattern works for the other servers:

```bash
cd openneuro-mcp-server
uv sync --extra dev
```

```bash
cd ibl-mcp-server
uv sync --extra dev
```

## Run A Server

Run the DANDI MCP server:

```bash
cd dandi-mcp-server
uv run dandi-mcp
```

Run the OpenNeuro MCP server:

```bash
cd openneuro-mcp-server
uv run openneuro-mcp
```

Run the IBL MCP server:

```bash
cd ibl-mcp-server
uv run ibl-mcp
```

## Generate MCP Client Config

From the repository root, generate a combined MCP configuration:

```bash
python harness/generate_mcp_config.py --format mcp-json
```

Check that all configured servers can start:

```bash
python harness/check_servers.py
```

See [MCP Harness](HARNESS.md) for more client configuration details.

## Storage

All servers use a shared storage convention. By default, metadata, local manifests, generated reports, downloads, and indexes are stored under:

```text
~/.cache/neurodata-without-barriers/<provider>/
```

You can override the root storage location for all servers:

```bash
export NEURODATA_MCP_STORAGE_DIR=/path/to/mcp-storage
```

You can also configure a provider-specific storage root:

```bash
export DANDI_MCP_STORAGE_DIR=/path/to/dandi-storage
export OPENNEURO_MCP_STORAGE_DIR=/path/to/openneuro-storage
export IBL_MCP_STORAGE_DIR=/path/to/ibl-storage
```

## Local Dataset Roots

When registering local data by ID instead of explicit path, each server searches common local roots and a provider-specific environment variable:

| Server | Environment variable |
| --- | --- |
| DANDI | `DANDI_MCP_DATA_ROOTS` |
| OpenNeuro | `OPENNEURO_MCP_DATA_ROOTS` |
| IBL | `IBL_MCP_DATA_ROOTS` |

Each variable accepts a colon-separated list of directories on macOS/Linux.

## Test Everything

Run each server's tests from its package directory:

```bash
PYTHONPATH=src uv run pytest tests
```

The same command can be run with your active Python environment:

```bash
PYTHONPATH=src pytest tests
```
