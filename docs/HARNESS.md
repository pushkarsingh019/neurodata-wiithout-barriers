# MCP Harness

This repository keeps the DANDI, IBL, and OpenNeuro MCP servers as separate source-specific adapters. The root `harness/` scripts provide a thin operational layer for clients that can connect to one or more local MCP servers.

## Servers

| Name | Directory | Command |
| --- | --- | --- |
| `dandi` | `dandi-mcp-server` | `uv --directory ./dandi-mcp-server run dandi-mcp` |
| `ibl` | `ibl-mcp-server` | `uv --directory ./ibl-mcp-server run ibl-mcp` |
| `openneuro` | `openneuro-mcp-server` | `uv --directory ./openneuro-mcp-server run openneuro-mcp` |

## Verify Local Launch

Run this from the repository root:

```bash
python harness/check_servers.py
```

The check imports each server module and builds the MCP server object through that project's own `uv` environment. It does not make archive API calls.

## Generate Client Config

Most desktop and coding-agent MCP clients need absolute paths. Generate those paths on the machine where the repo lives:

```bash
python harness/generate_mcp_config.py --format mcp-json
```

The generated configs also set `UV_CACHE_DIR` to each project's local `.uv-cache`, so clients do not need to write into a user-level uv cache.

For Claude Desktop-style config:

```bash
python harness/generate_mcp_config.py --format claude-desktop
```

For Codex-style TOML snippets:

```bash
python harness/generate_mcp_config.py --format codex-toml
```

For OpenCode-style local MCP JSON:

```bash
python harness/generate_mcp_config.py --format opencode-json
```

OpenCode uses `environment` for local MCP environment variables. The root `opencode.json` in this repo is project-local, so it should be picked up when OpenCode is launched from this directory.

You can write any generated config to a file:

```bash
python harness/generate_mcp_config.py --format mcp-json --output harness/generated/mcp.json
```

## Recommended Client Shape

Connect all three servers directly in the client first. This gives the agent full tool visibility and avoids prematurely hiding archive-specific capabilities.

Use the servers by intent:

| Intent | Server |
| --- | --- |
| NWB assets, Dandisets, DANDI metadata, DANDI download URLs | `dandi` |
| IBL sessions, OpenAlyx datasets, probes, behavioral summaries, QC hints | `ibl` |
| OpenNeuro datasets, BIDS metadata, modality/task inference, semantic BIDS search | `openneuro` |

Add a router MCP only after the direct multi-server setup becomes noisy. A router should stay thin: classify the user intent, call one or more source MCPs, and summarize cross-archive results without replacing the source-specific servers.

## OpenCode Dataset Smoke Test

After launching OpenCode from the repository root, use the reusable prompt in `harness/prompts/work_with_neurodata_dataset.md` to test whether the agent can inspect one DANDI dandiset, one OpenNeuro dataset, and one IBL session through MCP.

From a terminal, the same check can be run non-interactively:

```bash
opencode run --model llamacpp/Qwen "$(cat harness/prompts/work_with_neurodata_dataset.md)"
```

The prompt asks the agent to avoid large downloads and to distinguish MCP tool facts from interpretation.

## OpenCode Visual Explorer Demo

For the browser-launching dataset explorer demo, run OpenCode from the repository root:

```bash
opencode run --model llamacpp/Qwen "$(cat harness/prompts/demo_visualize_dandi_001097.md)"
```

The demo prompt requires the agent to call `generate_dataset_explorer` with `open_in_browser: true`, report the generated `html_path` and `file_url`, and avoid generating PNG plots unless the user explicitly asks for plots.
