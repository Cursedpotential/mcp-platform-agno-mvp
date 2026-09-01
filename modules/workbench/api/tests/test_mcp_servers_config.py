# Byline: Claude Code · Sonnet (agent) · 2026-07-23 (agno 2.8 MCP door migration: token_env resolution)
# Byline: Codex · GPT-5 · 2026-08-16 (ContextForge -> Portkey chain; direct fail-closed)
"""MCP chain and token-resolution tests for Workbench settings."""

from __future__ import annotations

import json

from app.config.settings import Settings


def test_default_exposes_no_direct_mcp_door():
    settings = Settings(_env_file=None, mcp_servers="[]")
    assert settings.mcp_servers_parsed == []


def test_portkey_token_env_resolves_from_process_env(monkeypatch):
    monkeypatch.setenv("PORTKEY_MCP_API_KEY", "secret-bearer-value")
    settings = Settings(
        mcp_servers=json.dumps(
            [
                {
                    "key": "platform-tools",
                    "gateway": "portkey",
                    "url": "https://mcp.portkey.ai/horizon-platform-tools/mcp",
                    "token_env": "PORTKEY_MCP_API_KEY",
                }
            ]
        )
    )
    servers = {s["key"]: s for s in settings.mcp_servers_parsed}
    assert servers["platform-tools"]["token"] == "secret-bearer-value"


def test_direct_server_is_rejected_without_explicit_diagnostic_bypass():
    direct = json.dumps([{"key": "contextforge", "url": "http://contextforge/mcp"}])
    assert Settings(mcp_servers=direct).mcp_servers_parsed == []
    assert Settings(mcp_servers=direct, mcp_direct_bypass_allowed=True).mcp_servers_parsed[0]["key"] == "contextforge"


def test_literal_token_wins_over_token_env(monkeypatch):
    monkeypatch.setenv("PORTKEY_MCP_API_KEY", "from-env")
    settings = Settings(
        mcp_servers=json.dumps(
            [
                {
                    "key": "platform-tools",
                    "gateway": "portkey",
                    "label": "Platform tools",
                    "url": "http://x/mcp",
                    "token": "literal-token",
                    "token_env": "PORTKEY_MCP_API_KEY",
                }
            ]
        )
    )
    servers = {s["key"]: s for s in settings.mcp_servers_parsed}
    assert servers["platform-tools"]["token"] == "literal-token"


def test_contextforge_token_env_resolves(monkeypatch):
    monkeypatch.setenv("CONTEXTFORGE_TOKEN", "cf-secret")
    settings = Settings(
        mcp_direct_bypass_allowed=True,
        mcp_servers=json.dumps(
            [
                {
                    "key": "contextforge",
                    "url": "http://contextforge/servers/id/mcp",
                    "token_env": "CONTEXTFORGE_TOKEN",
                }
            ]
        ),
    )
    servers = {s["key"]: s for s in settings.mcp_servers_parsed}
    assert servers["contextforge"]["token"] == "cf-secret"


def test_contextforge_legacy_field_backfills_when_no_token_env(monkeypatch):
    monkeypatch.delenv("CONTEXTFORGE_TOKEN", raising=False)
    settings = Settings(
        contextforge_token="legacy-field-value",
        mcp_direct_bypass_allowed=True,
        mcp_servers=json.dumps([{"key": "contextforge", "label": "ContextForge", "url": "http://x/mcp"}]),
    )
    servers = {s["key"]: s for s in settings.mcp_servers_parsed}
    assert servers["contextforge"]["token"] == "legacy-field-value"


def test_malformed_json_degrades_to_empty_list():
    settings = Settings(mcp_servers="not json")
    assert settings.mcp_servers_parsed == []
