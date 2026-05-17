# Testing

## Unit Tests

```bash
uv run --extra dev pytest
```

The current test suite checks:

- DANDI query construction.
- Download redirect handling.
- Mutation guardrails.
- Auth header wiring.
- Dandiset ID validation.
- Broad MCP tool registration.

## Live Smoke Checks

These commands hit the public DANDI API:

```bash
uv run python - <<'PY'
from dandi_mcp.client import DandiClient

c = DandiClient()
print(c.get_archive_info().keys())
print(c.get_stats())
print(c.list_zarr_archives(page_size=1).get("count"))
PY
```

## Documentation Build

```bash
uv run mkdocs build --strict
```

The strict build catches broken navigation, missing pages, and Markdown issues that MkDocs can detect.
