# Quickstart

Once the MCP server is connected, start with read-only discovery.

## Search for Dandisets

Ask your agent:

```text
Use dandi to search for motor cortex Dandisets. Return Dandiset IDs, names, published versions, asset counts, and citations when available.
```

Under the hood, this uses `search_dandisets`.

## Summarize a Dandiset

```text
Use dandi to summarize Dandiset 000006. Prefer the latest published version if one exists, and list a few sample assets.
```

Useful tools:

- `get_dandiset`
- `list_dandiset_versions`
- `summarize_dandiset`

## Browse Asset Paths

```text
Use dandi to browse the top-level paths in Dandiset 000006 draft, then list NWB assets under the first subject folder.
```

Useful tools:

- `list_asset_paths`
- `list_assets`

## Inspect an Asset Before Download

```text
Use dandi to inspect asset a5ad932b-b893-4522-b989-8f406d78e4e0 from Dandiset 000006 draft. Include metadata, validation state, and whether it looks safe to download.
```

Useful tools:

- `get_asset_metadata`
- `get_asset_info`
- `get_asset_validation`

## Resolve a Download URL

```text
Use dandi to get the download URL for asset a5ad932b-b893-4522-b989-8f406d78e4e0.
```

Useful tool:

- `get_asset_download_url`

!!! warning
    Download URLs point to object storage and may expire. Many DANDI assets are large, so inspect metadata and file size before downloading.

