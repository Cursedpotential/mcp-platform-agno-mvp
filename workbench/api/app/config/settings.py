# Byline: Claude Code · Sonnet (agent) · 2026-07-19 (agno 2.8 MCP door migration + Graphiti pane wiring 2026-07-23)
# Byline: Codex · GPT-5 · 2026-08-16 (Portkey-routed neutral chat settings)
# Byline: Codex · GPT-5 · 2026-08-18 (owner-only evidence-search capability)
# Byline: Codex · GPT-5 · 2026-08-29 (strict Authentik trusted-proxy boundary)
"""Workbench settings — S3-agnostic object store (R2 now, B2/any-S3 = env swap later).

Env var names are the pydantic-settings default (uppercase of the field name)
and must match compose.workbench.yaml exactly — see that file for the deployed
defaults and the Coolify env-literal-rendering gotcha.
"""

from __future__ import annotations

import ipaddress
import json
import os

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
    # Direct-tailnet UIW starter boundary; blank values fail closed in the adapter.
    uiw_starter_url: str = ""
    # Separate from the shared AgentOS service bearer. Only the operator
    # Workbench receives this capability; agent calls must use walk context.
    evidence_operator_security_key: str = ""

    # --- MCP tool servers (Tool Explorer) ---
    # ContextForge is the authored registry; Portkey is the downstream audited
    # gateway. Default empty is intentional: an unprovisioned chain exposes no
    # tools instead of falling back to a direct AgentOS/ContextForge door. Each
    # entry may carry its own literal "token" (bearer), or a "token_env" —
    # the NAME of an env var holding the bearer, resolved at read time via
    # mcp_servers_parsed (never baked into the JSON literal itself, so the
    # actual secret value lives only in the process env / Coolify env editor,
    # never in this file or compose.workbench.yaml's MCP_SERVERS string).
    # Each normal entry declares gateway:"portkey" and names Portkey's
    # /<server-slug>/mcp endpoint. ContextForge's /servers/<uuid>/mcp URL is
    # an upstream publication target, never a normal Workbench client door.
    mcp_servers: str = "[]"
    # Temporary diagnostics may explicitly opt into a direct door. This must
    # never become the production default or an automatic failure fallback.
    mcp_direct_bypass_allowed: bool = False
    # Back-compat only: used to fill the "contextforge" entry's token when
    # that entry carries neither "token" nor a resolvable "token_env" (a
    # pre-C4 MCP_SERVERS literal that hasn't been migrated to the token_env
    # convention above yet) — see mcp_servers_parsed.
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

    # --- Neutral operator chat (Portkey is the normal audited route) ---
    # PORTKEY_CONFIG is intentionally required by the route: saved configs own
    # fallback/load-balancing policy, while direct providers remain confined to
    # the explicitly labeled diagnostic model lab.
    portkey_api_key: str = ""
    portkey_base_url: str = "https://api.portkey.ai/v1"
    portkey_config: str = ""
    portkey_environment: str = "development"

    # --- Copilot preset prompts (optional JSON override, merged over
    # in-code defaults — see app/service/copilot_presets.py) ---
    copilot_presets_path: str = "/data/copilot/presets.json"

    # --- Graphiti knowledge-graph memory (C4 Graph memory pane) ---
    # The tailnet "graphiti-hostfix" nginx sidecar (compose.data-graphiti.yaml)
    # — NOT graphiti-mcp directly. Read-only wiring only (search_memory_facts/
    # search_nodes/get_episodes); see app/repo/graphiti_client.py for the
    # transport quirk (server-side Host-header rewrite, nothing special
    # needed client-side) and app/service/graphiti.py for the tool contract.
    # No auth today (tailnet-only, matches the `grc` CLI's --via direct).
    graphiti_mcp_url: str = "http://100.119.96.29:8071/mcp"
    # Temporary operator boundary until authenticated Matter/Run grants land.
    # Comma-separated namespaces; browser input never expands this allowlist.
    graphiti_allowed_groups: str = "platform"

    @property
    def graphiti_allowed_group_set(self) -> frozenset[str]:
        """Configured read-only Graphiti namespaces, normalized fail-closed."""
        return frozenset(group.strip() for group in self.graphiti_allowed_groups.split(",") if group.strip())

    # --- Authentication: Traefik+Authentik trusted-proxy ingress ---
    # Empty or malformed configuration fails closed. Production binds this to
    # the exact Traefik socket peer as a /32 or /128, never a broad network.
    trusted_auth_proxy_cidrs: str = ""

    # --- App ---
    app_port: int = 8020
    static_dir: str = "/app/static"
    max_upload_mb: int = 200
    # Compatibility read only: older local .env files may contain this key.
    # The Workbench boundary does not consult or deploy it.
    workbench_api_key: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def mcp_servers_parsed(self) -> list[dict]:
        """Parse MCP_SERVERS (json) into [{key, label, url, token?}, ...].

        Token resolution order per entry:
        1. A literal "token" already on the entry wins as-is (rare — mostly
           a manual override).
        2. "token_env": the name of an env var holding the bearer, resolved
           via `os.environ` at read time so the raw secret never has to be
           embedded in the MCP_SERVERS JSON literal itself.
        3. Back-compat: the bare CONTEXTFORGE_TOKEN env fills in the
           "contextforge"-keyed entry specifically, when it has neither of
           the above (a pre-C4 MCP_SERVERS literal that predates the
           token_env convention).

        Malformed/non-list JSON degrades to an empty list rather than
        raising. Entries without gateway:"portkey" are filtered unless the
        explicit diagnostic bypass is enabled.
        """
        try:
            servers = json.loads(self.mcp_servers)
        except (TypeError, ValueError):
            return []
        if not isinstance(servers, list):
            return []
        allowed_servers = []
        for server in servers:
            if not isinstance(server, dict):
                continue
            if server.get("gateway") != "portkey" and not self.mcp_direct_bypass_allowed:
                continue
            if server.get("token"):
                allowed_servers.append(server)
                continue
            token_env = server.get("token_env")
            resolved = os.environ.get(token_env) if token_env else None
            if resolved:
                server["token"] = resolved
            elif server.get("key") == "contextforge" and self.contextforge_token:
                server["token"] = self.contextforge_token
            allowed_servers.append(server)
        return allowed_servers

    @property
    def trusted_auth_proxy_cidrs_parsed(self) -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
        """Parse trusted proxy CIDRs, returning no trust on any malformed value."""
        if not self.trusted_auth_proxy_cidrs:
            return []
        cidrs: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
        for raw_part in self.trusted_auth_proxy_cidrs.split(","):
            part = raw_part.strip()
            if not part:
                return []
            try:
                cidrs.append(ipaddress.ip_network(part, strict=True))
            except ValueError:
                return []
        return cidrs


settings = Settings()
