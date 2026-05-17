# Contributing

## Project Layout

```text
dandi-mcp-server/
  src/dandi_mcp/client.py    # DANDI REST API client
  src/dandi_mcp/server.py    # FastMCP server, tools, resources, prompts
  docs/                      # MkDocs documentation
  tests/                     # pytest suite
  mkdocs.yml                 # Documentation site config
  pyproject.toml             # Package metadata and dependencies
```

## Adding a Tool

1. Add or reuse a method in `src/dandi_mcp/client.py`.
2. Register a tool in `src/dandi_mcp/server.py`.
3. Add tests for URL construction, guardrails, or tool exposure.
4. Update `docs/reference/tools.md`.
5. Update `docs/API_COVERAGE.md` when the tool maps to a DANDI API operation.

## Mutation Guardrails

Any tool that can change DANDI archive state should require `confirm=true`. The generic `call_dandi_api` already blocks non-GET calls unless `allow_mutation=true`.

## Documentation

Run the docs locally:

```bash
uv run mkdocs serve
```

Build the static site:

```bash
uv run mkdocs build --strict
```

