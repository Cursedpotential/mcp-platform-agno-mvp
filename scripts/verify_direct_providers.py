"""scripts/verify_direct_providers.py — live verification + full model
enumeration for the DIRECT provider chain (Ollama Cloud, NVIDIA NIM,
Anthropic), bypassing Portkey (ADR-0042 retirement in progress).

Born out of the 2026-08-01 "wire providers direct" task: OpenRouter was
present-but-dead (402, out of credits) and nearly got wired anyway — the
owner's standing rule is a present key is worse than an absent one if nobody
proves it's alive. This script is the proof, for all three direct providers,
plus a full model-list pull (not a guess) for Ollama Cloud and NVIDIA NIM so
agno can be configured with the account's REAL catalog instead of a hardcoded
handful of ids.

Reads keys from the process environment first, falling back to a tolerant
regex parse of ~/.secrets/probata.env (formerly Agno-MCP-Platform.env) and ~/.secrets/anthropic.env
(never `source`d — CLAUDE.md's ~/.secrets rule: `KEY = value` spacing breaks
a shell source and echoes fragments). Secret VALUES are never printed, only
presence + length + a masked prefix/suffix.

Usage:
    .venv/Scripts/python.exe scripts/verify_direct_providers.py
    .venv/Scripts/python.exe scripts/verify_direct_providers.py --json-out <path>   # write full catalog as JSON (model ids/metadata only, no secrets)
    .venv/Scripts/python.exe scripts/verify_direct_providers.py --skip-live-chat    # list-only, skip the minimal completion calls (cheaper/faster)
"""
# Byline: Claude Code · Sonnet (agent) · 2026-08-01

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any, Optional

import requests

HOME = Path(os.environ.get("USERPROFILE") or os.environ.get("HOME") or "~").expanduser()
SECRETS_DIR = HOME / ".secrets"
PLATFORM_ENV = SECRETS_DIR / "probata.env"
ANTHROPIC_ENV = SECRETS_DIR / "anthropic.env"

NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
OLLAMA_CLOUD_HOST = "https://ollama.com"
ANTHROPIC_BASE_URL = "https://api.anthropic.com"
ANTHROPIC_VERSION = "2023-06-01"

# Substrings used to bucket NVIDIA NIM's flat model list into chat / embedding /
# rerank / vision-language buckets. NIM doesn't tag model "type" in /v1/models,
# so this is heuristic classification on the id string — good enough to split
# "usable as a chat model" from "usable as an embedder" for the registry.
EMBED_MARKERS = ("embed",)
RERANK_MARKERS = ("rerank",)


def load_dotenv(path: Path) -> dict[str, str]:
    """Tolerant KEY=value parse. Never `source`d — CLAUDE.md ~/.secrets rule."""
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
            # Strip one matching pair of wrapping quotes — some .env files quote
            # values literally (e.g. anthropic.env: KEY="sk-ant-..."), and a
            # naive parse folds the quote chars into the secret, corrupting any
            # Bearer header built from it (401 "Invalid bearer token", caught
            # live 2026-08-01 diagnosing why a known-valid OAuth token failed).
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                value = value[1:-1]
            env[m.group(1)] = value
    return env


def resolve(name: str, *dotenvs: dict[str, str]) -> Optional[str]:
    """Process env wins over each dotenv in order."""
    if os.environ.get(name):
        return os.environ[name]
    for d in dotenvs:
        if d.get(name):
            return d[name]
    return None


def mask(secret: Optional[str]) -> str:
    if not secret:
        return "<unset>"
    if len(secret) <= 8:
        return f"<{len(secret)} chars, masked>"
    return f"{secret[:4]}...{secret[-4:]} ({len(secret)} chars)"


# ---------------------------------------------------------------------------
# Ollama Cloud
# ---------------------------------------------------------------------------


def check_ollama(api_key: str) -> dict[str, Any]:
    result: dict[str, Any] = {"provider": "ollama"}
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    resp = requests.get(f"{OLLAMA_CLOUD_HOST}/api/tags", headers=headers, timeout=30)
    result["list_http_status"] = resp.status_code
    if resp.status_code != 200:
        result["ok"] = False
        result["error"] = resp.text[:500]
        return result
    data = resp.json()
    models = sorted(m.get("model") or m.get("name") for m in data.get("models", []))
    result["ok"] = True
    result["model_count"] = len(models)
    result["models"] = models
    return result


def ollama_chat_probe(api_key: str, model_id: str) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": "Reply with exactly one word: OK"}],
        "stream": False,
    }
    resp = requests.post(f"{OLLAMA_CLOUD_HOST}/api/chat", headers=headers, json=payload, timeout=60)
    out: dict[str, Any] = {"http_status": resp.status_code, "ok": resp.status_code == 200}
    if out["ok"]:
        body = resp.json()
        out["model"] = body.get("model")
        out["content"] = (body.get("message") or {}).get("content", "")[:80]
    else:
        out["error"] = resp.text[:500]
    return out


# ---------------------------------------------------------------------------
# NVIDIA NIM
# ---------------------------------------------------------------------------


def check_nvidia(api_key: str, base_url: str = NVIDIA_BASE_URL) -> dict[str, Any]:
    result: dict[str, Any] = {"provider": "nvidia"}
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    resp = requests.get(f"{base_url}/models", headers=headers, timeout=30)
    result["list_http_status"] = resp.status_code
    if resp.status_code != 200:
        result["ok"] = False
        result["error"] = resp.text[:500]
        return result
    ids = sorted(m["id"] for m in resp.json().get("data", []))
    embed = [i for i in ids if any(mk in i.lower() for mk in EMBED_MARKERS)]
    rerank = [i for i in ids if any(mk in i.lower() for mk in RERANK_MARKERS)]
    chat = [i for i in ids if i not in embed and i not in rerank]
    result.update(
        ok=True,
        model_count=len(ids),
        chat_models=chat,
        embed_models=embed,
        rerank_models=rerank,
    )
    return result


def nvidia_chat_probe(api_key: str, model_id: str, base_url: str = NVIDIA_BASE_URL) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": "Reply with exactly one word: OK"}],
        "max_tokens": 8,
        "stream": False,
    }
    resp = requests.post(f"{base_url}/chat/completions", headers=headers, json=payload, timeout=60)
    out: dict[str, Any] = {"http_status": resp.status_code, "ok": resp.status_code == 200}
    if out["ok"]:
        body = resp.json()
        out["model"] = body.get("model")
        choices = body.get("choices") or [{}]
        out["content"] = ((choices[0].get("message") or {}).get("content") or "")[:80]
    else:
        out["error"] = resp.text[:500]
    return out


# ---------------------------------------------------------------------------
# Anthropic — CLAUDE_CODE_OAUTH_TOKEN is a subscription OAuth token
# (sk-ant-oat-...), NOT a standard ANTHROPIC_API_KEY. It authenticates via
# `Authorization: Bearer <token>` + `anthropic-beta: oauth-2025-04-20`
# (no `x-api-key`) — the pattern already proven live by
# server/tools/.../cb_sort_assist.py (Case Bible plugin). Standard
# ANTHROPIC_API_KEY (if ever added) would instead use `x-api-key`.
# ---------------------------------------------------------------------------


def check_anthropic_oauth(oauth_token: str) -> dict[str, Any]:
    result: dict[str, Any] = {"provider": "anthropic_oauth"}
    headers = {
        "Authorization": f"Bearer {oauth_token}",
        "anthropic-version": ANTHROPIC_VERSION,
        "anthropic-beta": "oauth-2025-04-20",
        "Accept": "application/json",
    }
    resp = requests.get(f"{ANTHROPIC_BASE_URL}/v1/models", headers=headers, timeout=30)
    result["list_http_status"] = resp.status_code
    if resp.status_code != 200:
        result["ok"] = False
        result["error"] = resp.text[:500]
        return result
    ids = sorted(m["id"] for m in resp.json().get("data", []))
    result["ok"] = True
    result["model_count"] = len(ids)
    result["models"] = ids
    return result


def anthropic_oauth_chat_probe(oauth_token: str, model_id: str) -> dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {oauth_token}",
        "anthropic-version": ANTHROPIC_VERSION,
        "anthropic-beta": "oauth-2025-04-20",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model_id,
        "max_tokens": 8,
        "messages": [{"role": "user", "content": "Reply with exactly one word: OK"}],
    }
    resp = requests.post(f"{ANTHROPIC_BASE_URL}/v1/messages", headers=headers, json=payload, timeout=60)
    out: dict[str, Any] = {"http_status": resp.status_code, "ok": resp.status_code == 200}
    if out["ok"]:
        body = resp.json()
        out["model"] = body.get("model")
        content_blocks = body.get("content") or []
        text = "".join(b.get("text", "") for b in content_blocks if isinstance(b, dict))
        out["content"] = text[:80]
    else:
        out["error"] = resp.text[:500]
    return out


def check_anthropic_api_key(api_key: str) -> dict[str, Any]:
    """Standard ANTHROPIC_API_KEY path (x-api-key header) — for completeness,
    in case one is ever added to secrets. Currently expected to be skipped
    (no ANTHROPIC_API_KEY exists in ~/.secrets as of 2026-08-01)."""
    result: dict[str, Any] = {"provider": "anthropic_api_key"}
    headers = {
        "x-api-key": api_key,
        "anthropic-version": ANTHROPIC_VERSION,
        "Accept": "application/json",
    }
    resp = requests.get(f"{ANTHROPIC_BASE_URL}/v1/models", headers=headers, timeout=30)
    result["list_http_status"] = resp.status_code
    if resp.status_code != 200:
        result["ok"] = False
        result["error"] = resp.text[:500]
        return result
    ids = sorted(m["id"] for m in resp.json().get("data", []))
    result["ok"] = True
    result["model_count"] = len(ids)
    result["models"] = ids
    return result


def agno_build_model_smoke_test(provider: str, env_overrides: dict[str, str]) -> dict[str, Any]:
    """Construct a model via server.core.settings.build_model() with the
    given env vars injected into os.environ (restored after), and run one
    real minimal .run() call through agno's own model class — not this
    script's raw-HTTP reimplementation. Proves the actual code path the app
    uses, not just that the credential is valid in isolation."""
    import sys as _sys

    _sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from agno.agent import Agent  # type: ignore

    from server.core.settings import build_model  # type: ignore

    saved = {k: os.environ.get(k) for k in env_overrides}
    os.environ.update(env_overrides)
    try:
        model = build_model(provider)
        agent = Agent(model=model)
        response = agent.run("Reply with exactly one word: OK")
        return {"ok": True, "model_class": type(model).__name__, "model_id": getattr(model, "id", None), "content": str(response.content)[:80]}
    except Exception as e:  # noqa: BLE001 - diagnostic script, report any failure
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--json-out", default=None, help="Write full catalog (model ids/metadata, no secrets) to this path")
    parser.add_argument("--skip-live-chat", action="store_true", help="Skip minimal live completion calls, list-only")
    parser.add_argument(
        "--agno-smoke-test",
        action="store_true",
        help="Also run one real call through server.core.settings.build_model() + agno.Agent for each live provider",
    )
    args = parser.parse_args()

    platform_env = load_dotenv(PLATFORM_ENV)
    anthropic_env = load_dotenv(ANTHROPIC_ENV)

    ollama_key = resolve("OLLAMA_API_KEY", platform_env)
    nvidia_key = resolve("NVIDIA_API_KEY", platform_env)
    anthropic_oauth = resolve("CLAUDE_CODE_OAUTH_TOKEN", anthropic_env)
    anthropic_api_key = resolve("ANTHROPIC_API_KEY", platform_env, anthropic_env)

    print("=== Key presence (values never printed) ===")
    print(f"OLLAMA_API_KEY          = {mask(ollama_key)}")
    print(f"NVIDIA_API_KEY          = {mask(nvidia_key)}")
    print(f"CLAUDE_CODE_OAUTH_TOKEN = {mask(anthropic_oauth)}")
    print(f"ANTHROPIC_API_KEY       = {mask(anthropic_api_key)}")
    print()

    catalog: dict[str, Any] = {}

    # --- Ollama Cloud ---
    if ollama_key:
        print("=== Ollama Cloud: GET /api/tags ===")
        r = check_ollama(ollama_key)
        catalog["ollama"] = r
        print(f"HTTP {r['list_http_status']} — ok={r['ok']}")
        if r["ok"]:
            print(f"{r['model_count']} models:")
            for m in r["models"]:
                print(f"  - {m}")
            if not args.skip_live_chat and r["models"]:
                probe_model = next((m for m in r["models"] if "glm-5.1" in m), r["models"][0])
                print(f"\nLive chat probe: model={probe_model!r}")
                p = ollama_chat_probe(ollama_key, probe_model)
                catalog["ollama"]["chat_probe"] = p
                print(f"HTTP {p['http_status']} — ok={p['ok']} — content={p.get('content') or p.get('error')}")
        else:
            print(f"FAIL: {r.get('error')}")
    else:
        print("OLLAMA_API_KEY not set — skipping Ollama Cloud checks")
    print()

    # --- NVIDIA NIM ---
    if nvidia_key:
        print("=== NVIDIA NIM: GET /v1/models ===")
        r = check_nvidia(nvidia_key)
        catalog["nvidia"] = r
        print(f"HTTP {r['list_http_status']} — ok={r['ok']}")
        if r["ok"]:
            print(f"{r['model_count']} total — chat={len(r['chat_models'])} embed={len(r['embed_models'])} rerank={len(r['rerank_models'])}")
            if not args.skip_live_chat and r["chat_models"]:
                probe_model = "nvidia/nemotron-3-super-120b-a12b" if "nvidia/nemotron-3-super-120b-a12b" in r["chat_models"] else r["chat_models"][0]
                print(f"\nLive chat probe: model={probe_model!r}")
                p = nvidia_chat_probe(nvidia_key, probe_model)
                catalog["nvidia"]["chat_probe"] = p
                print(f"HTTP {p['http_status']} — ok={p['ok']} — content={p.get('content') or p.get('error')}")
        else:
            print(f"FAIL: {r.get('error')}")
    else:
        print("NVIDIA_API_KEY not set — skipping NVIDIA NIM checks")
    print()

    # --- Anthropic ---
    if anthropic_api_key:
        print("=== Anthropic (standard ANTHROPIC_API_KEY, x-api-key): GET /v1/models ===")
        r = check_anthropic_api_key(anthropic_api_key)
        catalog["anthropic_api_key"] = r
        print(f"HTTP {r['list_http_status']} — ok={r['ok']}")
        if r["ok"]:
            print(f"{r['model_count']} models: {r['models'][:10]}{'...' if len(r['models']) > 10 else ''}")
        else:
            print(f"FAIL: {r.get('error')}")
    else:
        print("ANTHROPIC_API_KEY not set anywhere in ~/.secrets — no standard-key path to test")
    print()

    if anthropic_oauth:
        print("=== Anthropic (CLAUDE_CODE_OAUTH_TOKEN, Bearer + oauth-2025-04-20 beta): GET /v1/models ===")
        r = check_anthropic_oauth(anthropic_oauth)
        catalog["anthropic_oauth"] = r
        print(f"HTTP {r['list_http_status']} — ok={r['ok']}")
        if r["ok"]:
            print(f"{r['model_count']} models: {r['models'][:10]}{'...' if len(r['models']) > 10 else ''}")
            if not args.skip_live_chat:
                probe_model = "claude-sonnet-4-6" if "claude-sonnet-4-6" in r["models"] else r["models"][0]
                print(f"\nLive chat probe: model={probe_model!r}")
                p = anthropic_oauth_chat_probe(anthropic_oauth, probe_model)
                catalog["anthropic_oauth"]["chat_probe"] = p
                print(f"HTTP {p['http_status']} — ok={p['ok']} — content={p.get('content') or p.get('error')}")
        else:
            print(f"FAIL: {r.get('error')}")
    else:
        print("CLAUDE_CODE_OAUTH_TOKEN not set — skipping OAuth-token checks")

    if args.agno_smoke_test:
        print("\n=== agno-native smoke tests (server.core.settings.build_model + Agent.run) ===")
        if ollama_key:
            r = agno_build_model_smoke_test("ollama", {"OLLAMA_API_KEY": ollama_key})
            catalog.setdefault("agno_smoke", {})["ollama"] = r
            print(f"ollama: {r}")
        if nvidia_key:
            r = agno_build_model_smoke_test("nvidia", {"NVIDIA_API_KEY": nvidia_key})
            catalog.setdefault("agno_smoke", {})["nvidia"] = r
            print(f"nvidia: {r}")
        if anthropic_oauth:
            r = agno_build_model_smoke_test("anthropic", {"ANTHROPIC_AUTH_TOKEN": anthropic_oauth})
            catalog.setdefault("agno_smoke", {})["anthropic_via_auth_token"] = r
            print(f"anthropic (ANTHROPIC_AUTH_TOKEN fallback): {r}")

    if args.json_out:
        Path(args.json_out).write_text(json.dumps(catalog, indent=2), encoding="utf-8")
        print(f"\nWrote catalog to {args.json_out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
