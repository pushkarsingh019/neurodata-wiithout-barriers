# MCP Client Setup

Most MCP clients need a server name, command, and argument list. Use the local project path as the working directory for `uv`.

## Generic MCP Configuration

```json
{
  "mcpServers": {
    "dandi": {
      "command": "uv",
      "args": [
        "--directory",
        "/Users/pushkarsingh/Documents/side-projects/paper-lineage-cli/dandi-mcp-server",
        "run",
        "dandi-mcp"
      ]
    }
  }
}
```

## With Authentication

Authenticated reads and mutating operations need a DANDI token.

```json
{
  "mcpServers": {
    "dandi": {
      "command": "uv",
      "args": [
        "--directory",
        "/Users/pushkarsingh/Documents/side-projects/paper-lineage-cli/dandi-mcp-server",
        "run",
        "dandi-mcp"
      ],
      "env": {
        "DANDI_API_TOKEN": "your_token_here"
      }
    }
  }
}
```

## Codex

If your Codex environment exposes MCP server configuration, add the generic block above. After restarting the MCP session, ask Codex to use the `dandi` server.

Example:

```text
Use the dandi MCP server to search for Dandisets about motor cortex and summarize the top candidates.
```

## opencode

Add the same MCP server block to your opencode MCP configuration. The server uses standard stdio MCP transport through the `dandi-mcp` command.

Example:

```text
Use dandi to inspect Dandiset 000006 and list the first 10 NWB assets.
```

## Claude Desktop Style

Claude Desktop uses the same shape under `mcpServers`. Use the JSON block above and restart Claude Desktop after editing its config.

