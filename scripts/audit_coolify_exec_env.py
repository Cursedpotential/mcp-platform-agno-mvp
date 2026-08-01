"""scripts/audit_coolify_exec_env.py — read-only audit of the exec-tier
Coolify app's currently-stored env vars.

GET only — never writes. Prints env var NAMES for everything, and VALUES
only for a small explicit allowlist of genuinely non-secret config (model
provider selection, feature flags, hostnames, URLs) — never for anything
key/token/password/secret-shaped.

Reads the Coolify API token from ~/.secrets/coolify-ionos-api.env via a
tolerant regex parse (never `source`d — CLAUDE.md ~/.secrets rule; strips
one matching pair of wrapping quotes, the same fix applied in
verify_direct_providers.py after a quoted CLAUDE_CODE_OAUTH_TOKEN value
corrupted a Bearer header).

Usage:
    .venv/Scripts/python.exe scripts/audit_coolify_exec_env.py
    .venv/Scripts/python.exe scripts/audit_coolify_exec_env.py --uuid <app-uuid> --base-url <coolify-api-base>
"""
# Byline: Claude Code · Sonnet (agent) · 2026-08-01

from __future__ import annotations

import argparse
import os
import re
from pathlib import Path
from typing import Optional

import requests

HOME = Path(os.environ.get("USERPROFILE") or os.environ.get("HOME") or "~").expanduser()
SECRETS_DIR = HOME / ".secrets"
COOLIFY_ENV = SECRETS_DIR / "coolify-ionos-api.env"

DEFAULT_BASE_URL = "http://100.98.98.38:8000/api/v1"
DEFAULT_APP_UUID = "rz41wqhpjfh1rj796ixvjhfs"

# Explicit allowlist: keys safe to print the VALUE of (config/routing, not
# credentials). Everything else prints name-only.
NON_SECRET_KEYS = {
    "DEFAULT_MODEL_PROVIDER",
    "DEFAULT_MODEL_ID",
    "OLLAMA_MODEL_ID",
    "NVIDIA_MODEL_ID",
    "ANTHROPIC_MODEL_ID",
    "RUNTIME_ENV",
    "CSRF_ENABLED",
    "SSRF_ALLOW_PRIVATE_NETWORKS",
    "PASSWORD_CHANGE_ENFORCEMENT_ENABLED",
    "EMBED_TEXT_ID",
    "EMBED_TEXT_DIM",
    "EMBED_BASE_URL",
    "NVIDIA_BASE_URL",
    "OVH1_HOST",
    "OVH3_HOST",
    "BIND_IP",
    "GRAPHITI_MCP_URL",
    "SBV_BASE_URL",
    "MILVUS_ADDRESS",
    "SURREALDB_URL",
    "SURREALDB_NS",
    "SURREALDB_DB",
    "R2_ACCOUNT_ID",
    "R2_BUCKET_NAME",
    "R2_ENDPOINT_URL",
}


def load_dotenv(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not path.exists():
        return env
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        m = re.match(r"^\s*([A-Z0-9_]+)\s*=\s*(.+?)\s*$", line)
        if m:
            value = m.group(2)
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                value = value[1:-1]
            env[m.group(1)] = value
    return env


def resolve(name: str, dotenv: dict[str, str]) -> Optional[str]:
    return os.environ.get(name) or dotenv.get(name)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--uuid", default=DEFAULT_APP_UUID, help="Coolify application UUID")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Coolify API base URL")
    args = parser.parse_args()

    dotenv = load_dotenv(COOLIFY_ENV)
    token = resolve("COOLIFY_API_TOKEN", dotenv)
    if not token:
        print(f"FAIL: no COOLIFY_API_TOKEN found in env or {COOLIFY_ENV}")
        return 2

    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    resp = requests.get(f"{args.base_url}/applications/{args.uuid}/envs", headers=headers, timeout=30)
    print(f"GET /applications/{args.uuid}/envs -> HTTP {resp.status_code}")
    if resp.status_code != 200:
        print(resp.text[:1000])
        return 1

    data = resp.json()
    rows = data if isinstance(data, list) else [{"key": k, "value": v} for k, v in data.items()]

    # De-dupe by key (Coolify's envs endpoint can list the same key more than
    # once — e.g. production + preview rows).
    by_key: dict[str, list[dict]] = {}
    for row in rows:
        by_key.setdefault(row.get("key"), []).append(row)

    print(f"\n{len(by_key)} distinct env var names currently set on exec-tier:")
    for key in sorted(by_key):
        entries = by_key[key]
        note = f" ({len(entries)} rows)" if len(entries) > 1 else ""
        if key in NON_SECRET_KEYS:
            values = {str(e.get("value")) for e in entries}
            print(f" - {key}{note} = {values if len(values) > 1 else next(iter(values))}")
        else:
            print(f" - {key}{note}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
