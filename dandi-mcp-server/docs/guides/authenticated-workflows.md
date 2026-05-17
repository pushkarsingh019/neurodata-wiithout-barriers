# Authenticated Workflows

The server supports authenticated DANDI operations through `DANDI_API_TOKEN` or `DANDI_API_KEY`.

## Configure a Token

```bash
export DANDI_API_TOKEN="your_token_here"
uv run dandi-mcp
```

Or put the token in your MCP client config:

```json
{
  "env": {
    "DANDI_API_TOKEN": "your_token_here"
  }
}
```

## Confirming Mutations

Mutating tools return a blocked response unless called with `confirm=true`.

This applies to:

- Creating Dandisets.
- Updating metadata.
- Deleting Dandisets, versions, assets, uploads, or Zarr files.
- Publishing versions.
- Starring or unstarring Dandisets.
- Upload initialization, completion, and validation.
- Zarr create/finalize/file upload operations.

Example blocked call:

```json
{
  "dandiset_id": "000006"
}
```

Example confirmed call:

```json
{
  "dandiset_id": "000006",
  "confirm": true
}
```

## Universal API Calls

`call_dandi_api` can reach any DANDI API path.

Read-only example:

```json
{
  "method": "GET",
  "path": "stats/"
}
```

Mutating example:

```json
{
  "method": "POST",
  "path": "dandisets/000006/star/",
  "allow_mutation": true
}
```

!!! danger
    Authenticated mutating operations affect real DANDI archive state. Agents should explain intent, target Dandiset/version/asset, and expected consequence before calling confirmed mutations.

