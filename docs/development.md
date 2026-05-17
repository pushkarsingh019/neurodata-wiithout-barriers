# Development

This repository contains three independent MCP server packages plus a root documentation site.

## Repository Layout

```text
dandi-mcp-server/
openneuro-mcp-server/
ibl-mcp-server/
docs/
mkdocs.yml
harness/
```

Each server has its own `pyproject.toml`, source package, tests, and runtime entry point. The root `mkdocs.yml` builds the unified documentation site.

## Run Tests

Run DANDI tests:

```bash
cd dandi-mcp-server
PYTHONPATH=src pytest tests
```

Run OpenNeuro tests:

```bash
cd openneuro-mcp-server
PYTHONPATH=src pytest tests
```

Run IBL tests:

```bash
cd ibl-mcp-server
PYTHONPATH=src pytest tests
```

## Build Documentation

Install MkDocs Material in your environment:

```bash
python -m pip install mkdocs-material
```

Build the site from the repository root:

```bash
mkdocs build --strict
```

Serve locally:

```bash
mkdocs serve
```

## Adding A New Local Explorer Capability

When adding local explorer behavior, keep the shared API stable:

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

Provider-specific capabilities should be added as additional tools. For example, DANDI adds NWB-specific inspection and validation, while OpenNeuro adds BIDS events extraction.

## Testing Local Explorer Changes

Local explorer tests should use small synthetic datasets unless a compact fixture already exists in the repository. Tests should verify:

- Registration creates a manifest.
- Indexing returns expected subjects, sessions, tasks, modalities, or ALF objects.
- Signal inventory is non-empty when analysis files exist.
- Report generation writes a Markdown file.
- Existing server tool registration includes the new tools.

## Documentation Rules

When tools change, update:

- The provider-specific guide under `docs/mcps/`.
- The compatibility matrix under `docs/reference/tool-compatibility.md` if the shared API changes.
- The provider package docs or README when relevant.

The documentation should explain what the tool does, when to use it, what it returns, and any safety or performance boundaries.
