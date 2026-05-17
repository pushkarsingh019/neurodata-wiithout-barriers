#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SERVERS = {
    "dandi": {
        "directory": "dandi-mcp-server",
        "command": "dandi-mcp",
        "description": "DANDI Archive dandisets, assets, metadata, and download URLs.",
    },
    "ibl": {
        "directory": "ibl-mcp-server",
        "command": "ibl-mcp",
        "description": "International Brain Laboratory OpenAlyx sessions, datasets, and QC-aware summaries.",
    },
    "openneuro": {
        "directory": "openneuro-mcp-server",
        "command": "openneuro-mcp",
        "description": "OpenNeuro BIDS-aware semantic dataset discovery.",
    },
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def command_config(root: Path, server: dict[str, str]) -> dict[str, Any]:
    directory = root / server["directory"]
    return {
        "command": "uv",
        "args": [
            "--directory",
            str(directory),
            "run",
            server["command"],
        ],
        "env": {
            "UV_CACHE_DIR": str(directory / ".uv-cache"),
            "NEURODATA_MCP_STORAGE_DIR": str(root / ".mcp-storage"),
        },
    }


def mcp_json(root: Path) -> str:
    payload = {
        "mcpServers": {
            name: command_config(root, server)
            for name, server in SERVERS.items()
        }
    }
    return json.dumps(payload, indent=2)


def codex_toml(root: Path) -> str:
    sections: list[str] = []
    for name, server in SERVERS.items():
        cfg = command_config(root, server)
        args = ", ".join(json.dumps(arg) for arg in cfg["args"])
        sections.append(
            "\n".join(
                [
                    f"[mcp_servers.{name}]",
                    f'command = "{cfg["command"]}"',
                    f"args = [{args}]",
                    (
                        f'env = {{ UV_CACHE_DIR = "{cfg["env"]["UV_CACHE_DIR"]}", '
                        f'NEURODATA_MCP_STORAGE_DIR = "{cfg["env"]["NEURODATA_MCP_STORAGE_DIR"]}" }}'
                    ),
                ]
            )
        )
    return "\n\n".join(sections)


def opencode_json(root: Path) -> str:
    payload = {
        "mcp": {
            name: {
                "type": "local",
                "enabled": True,
                "command": ["uv", *command_config(root, server)["args"]],
                "environment": command_config(root, server)["env"],
            }
            for name, server in SERVERS.items()
        }
    }
    return json.dumps(payload, indent=2)


def server_table(root: Path) -> str:
    lines = ["name\tdirectory\tcommand\tdescription"]
    for name, server in SERVERS.items():
        lines.append(
            "\t".join(
                [
                    name,
                    str(root / server["directory"]),
                    " ".join(["uv", *command_config(root, server)["args"]]),
                    server["description"],
                ]
            )
        )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate local MCP client configuration for all neurodata servers."
    )
    parser.add_argument(
        "--format",
        choices=["mcp-json", "claude-desktop", "codex-toml", "opencode-json", "table"],
        default="mcp-json",
        help="Output format. claude-desktop is the standard mcpServers JSON shape.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional output path. Defaults to stdout.",
    )
    args = parser.parse_args()

    root = repo_root()
    if args.format in {"mcp-json", "claude-desktop"}:
        output = mcp_json(root)
    elif args.format == "codex-toml":
        output = codex_toml(root)
    elif args.format == "opencode-json":
        output = opencode_json(root)
    else:
        output = server_table(root)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output + "\n", encoding="utf-8")
    else:
        print(output)


if __name__ == "__main__":
    main()
