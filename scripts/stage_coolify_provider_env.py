"""scripts/stage_coolify_provider_env.py — stage (and, only with --apply,
actually push) the direct-provider env vars onto the exec-tier Coolify app.

Bypasses Portkey per the 2026-08-01 "run direct" task: Ollama Cloud + NVIDIA
NIM + Anthropic (via the ANTHROPIC_AUTH_TOKEN fallback added to
server/core/settings.py, since this platform has no standard
ANTHROPIC_API_KEY — only a Claude Code subscription OAuth token).

SAFE BY DEFAULT: with no flags, this only PRINTS the keys that would be
upserted and a masked preview of the request body — it never touches the
network and never writes a secret value to disk. Pass --apply to actually
PATCH Coolify. Nobody should pass --apply without explicit sign-off: exec-
tier is mid-migration (another workstream owns it) and Coolify bakes env
values into the rendered compose at DEPLOY time, so an --apply here alone
does NOT reach the running container — a deploy still has to follow, and
this script does not trigger one (deliberately; see CLAUDE.md hard rule).

Reads keys from ~/.secrets via a tolerant regex parse (never `source`d —
strips one matching pair of wrapping quotes, the same fix applied in
verify_direct_providers.py after a quoted value corrupted a Bearer header).
Secret VALUES are never printed or written to disk by this script, in
--apply mode or otherwise — only resolved in-memory immediately before the
PATCH call.

Usage:
    .venv/Scripts/python.exe scripts/stage_coolify_provider_env.py               # dry run (default, safe)
    .venv/Scripts/python.exe scripts/stage_coolify_provider_env.py --apply       # actually PATCH exec-tier env (do NOT run without sign-off)
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
PLATFORM_ENV = SECRETS_DIR / "probata.env"
ANTHROPIC_ENV = SECRETS_DIR / "anthropic.env"
COOLIFY_ENV = SECRETS_DIR / "coolify-ionos-api.env"

DEFAULT_BASE_URL = "http://100.98.98.38:8000/api/v1"
DEFAULT_APP_UUID = "rz41wqhpjfh1rj796ixvjhfs"

# Every env var this upsert touches, and where its value comes from. Only
# the vars server/core/settings.py actually calls getenv() on for the
# direct-provider chain (ADR-0008) — no guessed names.
PLAN: list[tuple[str, Path, str]] = [
    ("OLLAMA_API_KEY", PLATFORM_ENV, "OLLAMA_API_KEY"),
    ("NVIDIA_API_KEY", PLATFORM_ENV, "NVIDIA_API_KEY"),
    # No standard ANTHROPIC_API_KEY exists anywhere in ~/.secrets (verified
    # 2026-08-01) — only the Claude Code subscription OAuth token. Mapped to
    # ANTHROPIC_AUTH_TOKEN, which settings.py's _try_provider("anthropic")
    # now reads as a fallback (agno.models.anthropic.Claude natively
    # supports it -> Bearer auth). Verified live: works with NO
    # anthropic-beta header against both /v1/models and /v1/messages.
    ("ANTHROPIC_AUTH_TOKEN", ANTHROPIC_ENV, "CLAUDE_CODE_OAUTH_TOKEN"),
]

# Deliberately NOT staged: DEFAULT_MODEL_PROVIDER. It's already unset/empty
# on exec-tier (confirmed via audit_coolify_exec_env.py), which is what we
# want — with all three direct providers now credentialed, the existing
# ADR-0008 priority chain (ollama -> nvidia -> kimi -> openrouter ->
# anthropic -> ...) resolves on its own; forcing a single provider was never
# asked for and would remove the fallback behavior the chain exists for.


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


def mask(secret: Optional[str]) -> str:
    if not secret:
        return "<unset>"
    if len(secret) <= 8:
        return f"<{len(secret)} chars, masked>"
    return f"{secret[:4]}...{secret[-4:]} ({len(secret)} chars)"


def build_payload() -> tuple[list[dict[str, object]], list[tuple[str, str]]]:
    """Resolve every value in PLAN and build the exact PATCH body shape.

    Returns (payload_data, masked_preview_rows) — the payload carries real
    secret values (only ever held in memory), the preview never does.
    """
    data: list[dict[str, object]] = []
    preview: list[tuple[str, str]] = []
    for target_key, source_path, source_var in PLAN:
        dotenv = load_dotenv(source_path)
        value = os.environ.get(source_var) or dotenv.get(source_var)
        if not value:
            preview.append((target_key, "MISSING — not found in env or " + str(source_path)))
            continue
        data.append({"key": target_key, "value": value, "is_preview": False})
        preview.append((target_key, mask(value)))
    return data, preview


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--uuid", default=DEFAULT_APP_UUID, help="Coolify application UUID")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Coolify API base URL")
    parser.add_argument("--apply", action="store_true", help="Actually PATCH Coolify (default: dry run only)")
    args = parser.parse_args()

    data, preview = build_payload()

    print("=== Staged env upsert for exec-tier (values never printed) ===")
    for key, masked in preview:
        print(f"  {key} = {masked}")
    print(f"\nPATCH body shape: {{'data': [{{'key', 'value', 'is_preview'}}, ...]}} — {len(data)} entries ready")

    if not args.apply:
        print("\nDRY RUN (default) — nothing sent. Re-run with --apply to actually PATCH Coolify.")
        print("Reminder: a PATCH alone does not reach the running container — Coolify bakes env")
        print("values into the rendered compose at DEPLOY time. A deploy must follow, and this")
        print("script does not trigger one.")
        return 0

    if len(data) != len(PLAN):
        print("\nFAIL: not all planned values resolved — refusing to apply a partial upsert.")
        return 2

    dotenv = load_dotenv(COOLIFY_ENV)
    token = os.environ.get("COOLIFY_API_TOKEN") or dotenv.get("COOLIFY_API_TOKEN")
    if not token:
        print(f"FAIL: no COOLIFY_API_TOKEN found in env or {COOLIFY_ENV}")
        return 2

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    resp = requests.patch(f"{args.base_url}/applications/{args.uuid}/envs/bulk", headers=headers, json={"data": data}, timeout=30)
    print(f"\nPATCH /applications/{args.uuid}/envs/bulk -> HTTP {resp.status_code}")
    if resp.status_code >= 300:
        print(resp.text[:1000])
        return 1
    print("Applied. NOTE: exec-tier still needs a deploy for this to reach the running container —")
    print("this script does not trigger one (owner rule: main session owns the exec-tier redeploy).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
