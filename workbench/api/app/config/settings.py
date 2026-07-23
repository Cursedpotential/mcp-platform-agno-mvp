# Byline: Claude Code · Sonnet (agent) · 2026-07-19
"""Workbench settings — S3-agnostic object store (R2 now, B2/any-S3 = env swap later).

Env var names are the pydantic-settings default (uppercase of the field name)
and must match compose.workbench.yaml exactly — see that file for the deployed
defaults and the Coolify env-literal-rendering gotcha.
"""

from __future__ import annotations

import json

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- S3-compatible object store: R2 today, B2/AWS/any-S3 = pure env swap ---
    object_store_endpoint_url: str = ""
    object_store_bucket: str = ""
    object_store_access_key_id: str = ""
    object_store_secret_access_key: str = ""
    object_store_region: str = "auto"
    object_store_prefix: str = "workbench/staging"

    # --- LanceDB local whole-file staging store (no S3, no AWS env vars) ---
    lancedb_path: str = "/data/lancedb"

    # --- Existing platform ingestion API (the promote target + the run spine) ---
    agentos_api_url: str = "http://100.72.169.40:8000"
    agentos_api_token: str | None = None

    # --- MCP tool servers (Tool Explorer) ---
    # Config-driven so the C1 console never hardcodes a server list. Each
    # entry may carry its own "token" (bearer); CONTEXTFORGE_TOKEN below fills
    # in the "contextforge" entry's token when the entry itself doesn't carry
    # one — see mcp_servers_parsed. NOTE the default "contextforge" URL below
    # is the bare gateway root; the confirmed real path convention (see
    # docs/planning/architecture-directives/contextforge-integration.md) is
    # per-virtual-server: `http://<host>:4444/servers/<SERVER_UUID>/mcp`, and
    # ContextForge has AUTH_REQUIRED=true (JWT bearer, minted via
    # `mcpgateway.utils.create_jwt_token`) — NOT the "no auth on tailnet" the
    # build brief assumed. Update MCP_SERVERS with the real registered
    # virtual-server URL (e.g. for "platform_tools") once known, and set
    # CONTEXTFORGE_TOKEN to a minted JWT.
    # agentos url uses :8000/mcp (agentos-api's mounted MCP surface) — the
    # standalone agentos-mcp service (:8001) was retired 2026-07-23, its
    # mounted-/mcp bug fixed upstream in agno 2.8.0.
    mcp_servers: str = (
        '[{"key":"agentos","label":"AgentOS","url":"http://100.72.169.40:8000/mcp"},'
        '{"key":"contextforge","label":"ContextForge","url":"http://100.72.169.40:4444/mcp"}]'
    )
    contextforge_token: str | None = None

    # --- OpenCode headless server (Ops Copilot, C2.5) ---
    # Basic auth is native to `opencode serve` via these two env names — see
    # compose.gateway.yaml (OPENCODE_SERVER_USERNAME/OPENCODE_SERVER_PASSWORD,
    # the C2.5 build's key-leak fix: GET /provider returns plaintext provider
    # keys unauth'd). When opencode_password is empty, no Authorization
    # header is sent — matches the pre-redeploy, still-unauthenticated
    # tailnet state (see app/repo/opencode_client.py).
    opencode_url: str = "http://100.72.169.40:4096"
    opencode_username: str = "opencode"
    opencode_password: str | None = None
    # provider/model, e.g. "groq/llama-3.3-70b-versatile" — overridable per request
    opencode_model: str = "groq/llama-3.3-70b-versatile"
    # SINGLE shared session-workspace directory for ALL copilot sessions (not
    # per-session) — the workbench container can't mkdir on the gateway host,
    # so isolation comes from opencode's own session model, not per-session
    # dirs. See app/repo/opencode_client.py module docstring + the
    # compose.gateway.yaml HOST-PREP comment (bind mount + one-time mkdir).
    opencode_workspace_dir: str = "/workspace/copilot"

    # --- Copilot preset prompts (optional JSON override, merged over
    # in-code defaults — see app/service/copilot_presets.py) ---
    copilot_presets_path: str = "/data/copilot/presets.json"

    # --- App ---
    app_port: int = 8020
    static_dir: str = "/app/static"
    max_upload_mb: int = 200

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def mcp_servers_parsed(self) -> list[dict]:
        """Parse MCP_SERVERS (json) into [{key, label, url, token?}, ...].

        A bare CONTEXTFORGE_TOKEN env fills in the bearer token for the
        "contextforge"-keyed entry when that entry doesn't already carry its
        own "token" field. Malformed/non-list JSON degrades to an empty list
        rather than raising — a bad env var should not crash the whole app.
        """
        try:
            servers = json.loads(self.mcp_servers)
        except (TypeError, ValueError):
            return []
        if not isinstance(servers, list):
            return []
        for server in servers:
            if not isinstance(server, dict):
                continue
            if server.get("key") == "contextforge" and not server.get("token") and self.contextforge_token:
                server["token"] = self.contextforge_token
        return servers


settings = Settings()
