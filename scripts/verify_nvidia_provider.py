"""scripts/verify_nvidia_provider.py — verify NVIDIA_API_KEY is alive and
poll the models NVIDIA NIM serves for it.

Born out of the 2026-08-01 knowledge-ingest outage: the text embedder
(``nvidia/nv-embed-v1``) was silently producing zero vectors because
``server/core/session.py`` defaulted its embed base_url/api_key to
OpenRouter (which does not host that model) instead of NVIDIA NIM — see the
comment above ``_EMBED_TEXT_BASE_URL`` in that file for the full trace. This
is the reusable diagnostic that would have caught it immediately: is
NVIDIA_API_KEY valid, what models does NIM actually serve for it, and does
the configured embed model return a vector of the right dimension.

Core list-models call (the "poll available models + verify key in one shot"
piece — a 200 here IS the key check, NIM 401s a dead key before it ever
lists anything):

    import requests
    url = "https://integrate.api.nvidia.com/v1/models"
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        model_ids = [model["id"] for model in response.json().get("data", [])]
    else:
        ...  # response.status_code / response.text explains the failure

Usage:
    .venv/Scripts/python.exe scripts/verify_nvidia_provider.py
    .venv/Scripts/python.exe scripts/verify_nvidia_provider.py --filter ""       # list ALL models, not just embed*
    .venv/Scripts/python.exe scripts/verify_nvidia_provider.py --skip-embed-test # key + model list only, no embeddings call
    .venv/Scripts/python.exe scripts/verify_nvidia_provider.py --embed-model nvidia/llama-nemotron-embed-vl-1b-v2 --embed-dim 2048

Reads NVIDIA_API_KEY / NVIDIA_BASE_URL from the process environment first,
falling back to a tolerant regex parse of the repo .env (never `source`d —
CLAUDE.md's ~/.secrets rule, applied here too). The key is never printed,
only its length and a masked prefix/suffix.
"""
# Byline: Claude Code · Sonnet (agent) · 2026-08-01

from __future__ import annotations

import argparse
import os
import re
from pathlib import Path
from typing import Optional

import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = REPO_ROOT / ".env"
DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"


def load_dotenv(path: Path) -> dict[str, str]:
    """Tolerant KEY=value parse — never `source`d, so `KEY = value` spacing
    (which breaks a shell source) is harmless here."""
    env: dict[str, str] = {}
    if not path.exists():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        m = re.match(r"^\s*([A-Z_][A-Z0-9_]*)\s*=\s*(.*?)\s*$", line)
        if m:
            env[m.group(1)] = m.group(2)
    return env


def resolve(name: str, dotenv: dict[str, str], default: Optional[str] = None) -> Optional[str]:
    """Process env wins over .env wins over default — matches every getenv()
    call in server/core/session.py / settings.py."""
    return os.environ.get(name) or dotenv.get(name) or default


def mask(secret: str) -> str:
    """Never print a secret — length + prefix/suffix only."""
    if not secret:
        return "<empty>"
    if len(secret) <= 8:
        return f"<{len(secret)} chars, masked>"
    return f"{secret[:4]}...{secret[-4:]} ({len(secret)} chars)"


def list_models(base_url: str, api_key: str) -> list[str]:
    """Poll available models + verify the key in one call.

    GET {base_url}/models is the standard OpenAI-compatible listing endpoint.
    A 200 here IS the key verification: NIM 401s a dead/expired/wrong-scope
    key before it ever gets to listing a model.
    """
    url = f"{base_url.rstrip('/')}/models"
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}

    response = requests.get(url, headers=headers, timeout=30)

    if response.status_code != 200:
        raise RuntimeError(f"Error {response.status_code}: {response.text[:500]}")

    models_data = response.json()
    return sorted(model["id"] for model in models_data.get("data", []))


def test_embedding(
    base_url: str, api_key: str, model_id: str, expected_dim: Optional[int] = None
) -> dict:
    """Real embeddings call — a model can be LISTED and still fail on the
    actual /embeddings endpoint, so this is a separate check from list_models."""
    url = f"{base_url.rstrip('/')}/embeddings"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"model": model_id, "input": ["nvidia provider verification probe"], "input_type": "query"}

    response = requests.post(url, headers=headers, json=payload, timeout=30)
    result: dict = {"http_status": response.status_code, "ok": response.status_code == 200}
    if result["ok"]:
        body = response.json()
        vec = body["data"][0]["embedding"]
        result["dim"] = len(vec)
        result["model"] = body.get("model")
        result["usage"] = body.get("usage")
        if expected_dim is not None:
            result["dim_matches_expected"] = len(vec) == expected_dim
    else:
        result["error"] = response.text[:500]
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default=None, help="Override NVIDIA_BASE_URL")
    parser.add_argument("--api-key-var", default="NVIDIA_API_KEY", help="Env var holding the key")
    parser.add_argument("--embed-model", default="nvidia/nv-embed-v1", help="Text embed model to probe end-to-end")
    parser.add_argument("--embed-dim", type=int, default=4096, help="Expected embedding dimension")
    parser.add_argument("--filter", default="embed", help="Substring filter for the printed models list ('' = all)")
    parser.add_argument("--skip-embed-test", action="store_true", help="List/verify only, skip the live embeddings call")
    args = parser.parse_args()

    dotenv = load_dotenv(ENV_PATH)
    base_url = args.base_url or resolve("NVIDIA_BASE_URL", dotenv, DEFAULT_BASE_URL)
    api_key = resolve(args.api_key_var, dotenv)

    print(f"NVIDIA_BASE_URL = {base_url}")
    print(f"{args.api_key_var} = {mask(api_key or '')}")

    if not api_key:
        print(f"FAIL: {args.api_key_var} not set in the environment or {ENV_PATH}")
        return 2

    try:
        model_ids = list_models(base_url, api_key)
    except (RuntimeError, requests.RequestException) as e:
        print(f"FAIL: key verification failed — {e}")
        return 1

    print(f"OK: key is VALID — found {len(model_ids)} available models")

    shown = [i for i in model_ids if args.filter.lower() in i.lower()] if args.filter else model_ids
    print(f"\nModels matching filter {args.filter!r}: {len(shown)}/{len(model_ids)}")
    for model_id in shown:
        flag = " <-- --embed-model" if model_id == args.embed_model else ""
        print(f" - {model_id}{flag}")

    if args.embed_model not in model_ids:
        print(f"\nWARNING: configured embed model {args.embed_model!r} is NOT in this key's model list.")

    if args.skip_embed_test:
        return 0

    print(f"\nProbing live embeddings call: model={args.embed_model!r} expected_dim={args.embed_dim}")
    result = test_embedding(base_url, api_key, args.embed_model, args.embed_dim)
    if not result["ok"]:
        print(f"FAIL: HTTP {result['http_status']} — {result.get('error')}")
        return 1

    match = result.get("dim_matches_expected")
    print(
        f"OK: HTTP {result['http_status']} — dim={result['dim']} (expected {args.embed_dim}, "
        f"{'MATCH' if match else 'MISMATCH'}) usage={result.get('usage')}"
    )
    return 0 if match else 1


if __name__ == "__main__":
    raise SystemExit(main())
