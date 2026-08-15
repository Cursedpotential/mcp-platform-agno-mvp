# Byline: Claude Code · Sonnet (agent) · 2026-07-23 (agno 2.8 MCP door migration: token_env resolution)
"""Unit tests for app/config/settings.py's mcp_servers_parsed — the token
resolution order (literal "token" > "token_env" env lookup > legacy
CONTEXTFORGE_TOKEN back-compat) that lets the agentos entry attach an
Authorization: Bearer <OS_SECURITY_KEY> header without embedding the secret
in the MCP_SERVERS JSON literal itself.
"""

from __future__ import annotations

import json

from app.config.settings import Settings


def test_default_agentos_entry_points_at_mounted_door():
    settings = Settings()
    servers = {s["key"]: s for s in settings.mcp_servers_parsed}
    assert servers["agentos"]["url"] == "http://100.72.169.40:8000/mcp"


def test_token_env_resolves_from_process_env(monkeypatch):
    monkeypatch.setenv("AGENTOS_API_TOKEN", "secret-bearer-value")
    settings = Settings()
    servers = {s["key"]: s for s in settings.mcp_servers_parsed}
    assert servers["agentos"]["token"] == "secret-bearer-value"


def test_token_env_missing_leaves_no_token(monkeypatch):
    monkeypatch.delenv("AGENTOS_API_TOKEN", raising=False)
    settings = Settings()
    servers = {s["key"]: s for s in settings.mcp_servers_parsed}
    assert "token" not in servers["agentos"]


def test_literal_token_wins_over_token_env(monkeypatch):
    monkeypatch.setenv("AGENTOS_API_TOKEN", "from-env")
    settings = Settings(
        mcp_servers=json.dumps(
            [
                {
                    "key": "agentos",
                    "label": "AgentOS",
                    "url": "http://x/mcp",
                    "token": "literal-token",
                    "token_env": "AGENTOS_API_TOKEN",
                }
            ]
        )
    )
    servers = {s["key"]: s for s in settings.mcp_servers_parsed}
    assert servers["agentos"]["token"] == "literal-token"


def test_contextforge_token_env_resolves(monkeypatch):
    monkeypatch.setenv("CONTEXTFORGE_TOKEN", "cf-secret")
    settings = Settings()
    servers = {s["key"]: s for s in settings.mcp_servers_parsed}
    assert servers["contextforge"]["token"] == "cf-secret"


def test_contextforge_legacy_field_backfills_when_no_token_env(monkeypatch):
    monkeypatch.delenv("CONTEXTFORGE_TOKEN", raising=False)
    settings = Settings(
        contextforge_token="legacy-field-value",
        mcp_servers=json.dumps([{"key": "contextforge", "label": "ContextForge", "url": "http://x/mcp"}]),
    )
    servers = {s["key"]: s for s in settings.mcp_servers_parsed}
    assert servers["contextforge"]["token"] == "legacy-field-value"


def test_malformed_json_degrades_to_empty_list():
    settings = Settings(mcp_servers="not json")
    assert settings.mcp_servers_parsed == []
