# Configuration

## Environment Variables

| Variable | Purpose | Required |
|---|---|---|
| `DANDI_API_BASE_URL` | Override the DANDI API base URL. Defaults to `https://api.dandiarchive.org/api`. | No |
| `DANDI_API_TIMEOUT` | HTTP timeout in seconds. Defaults to `30`. | No |
| `DANDI_API_TOKEN` | DANDI API token for authenticated operations. | No |
| `DANDI_API_KEY` | Alternative token variable. Used if `DANDI_API_TOKEN` is not set. | No |

## Defaults

The default configuration is safe for public read-only exploration:

```bash
DANDI_API_BASE_URL=https://api.dandiarchive.org/api
DANDI_API_TIMEOUT=30
```

## Test Against Another DANDI Instance

```bash
export DANDI_API_BASE_URL="https://api-staging.dandiarchive.org/api"
uv run dandi-mcp
```

## Authentication Header

If a token is set, the server sends:

```http
Authorization: token <value>
```

