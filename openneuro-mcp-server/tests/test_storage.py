from __future__ import annotations

from openneuro_mcp.storage import MCPStorage


def test_storage_describe_prompts_when_env_missing(monkeypatch) -> None:
    monkeypatch.delenv("OPENNEURO_MCP_STORAGE_DIR", raising=False)
    monkeypatch.delenv("NEURODATA_MCP_STORAGE_DIR", raising=False)

    info = MCPStorage.from_env("openneuro").describe()

    assert "NEURODATA_MCP_STORAGE_DIR is not set" in info["configuration_prompt"]


def test_storage_describe_has_no_prompt_when_env_configured(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("NEURODATA_MCP_STORAGE_DIR", str(tmp_path))

    info = MCPStorage.from_env("openneuro").describe()

    assert info["root_dir"] == str(tmp_path)
    assert info["configuration_prompt"] is None
