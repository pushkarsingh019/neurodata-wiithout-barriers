# DANDI MCP Server

`dandi-mcp-server` is an extensive Model Context Protocol server for the [DANDI Archive](https://dandiarchive.org). It gives agents structured access to Dandisets, versions, assets, folder-like paths, metadata, validation state, Zarr archives, schema information, archive statistics, and authenticated DANDI API workflows.

The server is designed for research agents that need to discover neurophysiology and neuroimaging datasets, inspect metadata before downloading large files, cite the exact Dandiset/version/asset path they used, and operate safely around mutating archive actions.

## What It Provides

| Area | Capabilities |
|---|---|
| Dandisets | Search, inspect metadata, list versions, summarize scientific context. |
| Assets | Browse paths, filter assets, inspect metadata/info/validation, resolve download URLs. |
| Archive metadata | Inspect service info, statistics, available schemas, and schema models. |
| Zarr | List Zarr archives, inspect Zarr metadata, list Zarr files, optionally request download URLs. |
| Users and auth | Read current user/token state, list/search users where allowed by DANDI. |
| Mutating API | Create, update, publish, delete, upload, star, and Zarr mutation tools guarded by confirmation. |
| Agent guidance | MCP prompts for finding Dandisets, exploring datasets, and evaluating assets for reuse. |

## Safety Model

Read-only tools work directly. Authenticated reads may require `DANDI_API_TOKEN` or `DANDI_API_KEY`.

Mutating tools are intentionally blocked until called with `confirm=true`. This includes creating, updating, deleting, publishing, uploads, starring, and Zarr mutation. The universal `call_dandi_api` fallback also blocks non-GET methods unless `allow_mutation=true`.

!!! note
    This MCP server wraps the DANDI API. It does not parse NWB, BIDS, or Zarr payload contents locally yet. It helps agents discover and reason about datasets before deciding whether a large asset download is worthwhile.

