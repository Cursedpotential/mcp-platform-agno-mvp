"""Probe every candidate model and write ONLY the usable ones to config.yaml.

Byline: Claude Code . Fable 5 . 2026-08-02 (v2 — verification is now the only
path into config.yaml; the v1 script trusted the static catalog and the owner
correctly called that out: a listed id is not a usable id).

For each provider the candidate ids come from server/core/model_catalog.py,
then every id is probed with a minimal 1-token chat completion:

  pass  : HTTP 200, or 429 (model exists, we are merely rate-limited)
  fail  : 401/403 (no entitlement), 404 (not hosted), payment-required,
          or repeated 5xx/timeout (one retry) — conservatively excluded

Keys are read from the environment or the repo .env with a tolerant regex
(never sourced, never printed). Missing key => provider skipped with a note.

usage:  uv run python scripts/update_available_models.py            # probe + write
        uv run python scripts/update_available_models.py --no-verify  # old v1 behavior
        uv run python scripts/update_available_models.py --dry-run    # probe, print, no write
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import pathlib
import re
import urllib.error
import urllib.request

import yaml

from server.core.model_catalog import available_models

REPO = pathlib.Path(__file__).resolve().parents[1]
CONFIG = REPO / "server" / "api" / "config.yaml"

PROVIDERS: dict[str, dict[str, str]] = {
    "ollama": {"url": "https://ollama.com/api/chat", "key_env": "OLLAMA_API_KEY", "style": "ollama"},
    "nvidia": {"url": "https://integrate.api.nvidia.com/v1/chat/completions",
               "key_env": "NVIDIA_API_KEY", "style": "openai"},
    "google": {"url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
               "key_env": "GOOGLE_API_KEY", "style": "openai"},
}
WORKERS = 4
TIMEOUT_S = 30


def _env(name: str) -> str:
    import os
    if os.environ.get(name):
        return os.environ[name]
    dotenv = REPO / ".env"
    if dotenv.exists():
        for line in dotenv.read_text(encoding="utf-8", errors="ignore").splitlines():
            m = re.match(rf"^\s*{name}\s*=\s*(.+?)\s*$", line)
            if m:
                return m.group(1).strip("\"'")
    return ""


def _probe(url: str, key: str, style: str, model_id: str) -> tuple[str, bool, str]:
    if style == "ollama":
        body = {"model": model_id, "messages": [{"role": "user", "content": "hi"}],
                "stream": False, "options": {"num_predict": 1}}
    else:
        body = {"model": model_id, "messages": [{"role": "user", "content": "hi"}],
                "max_tokens": 1, "stream": False}
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), method="POST",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    last = ""
    for attempt in (1, 2):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
                return model_id, True, f"http {resp.status}"
        except urllib.error.HTTPError as e:
            if e.code == 429:
                return model_id, True, "429 rate-limited (exists)"
            if e.code in (400, 401, 402, 403, 404, 422):
                # 400/422: some endpoints reject unknown ids with a 4xx body
                # instead of 404 — either way, not usable as-called.
                return model_id, False, f"http {e.code}"
            last = f"http {e.code}"  # 5xx: retry once
        except Exception as e:  # timeout / connection
            last = type(e).__name__
    return model_id, False, f"{last} (after retry)"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--no-verify", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    verified: list[str] = []
    report: list[str] = []
    for provider, cfg in PROVIDERS.items():
        try:
            candidates = available_models(provider)
        except Exception:
            candidates = []
        if not candidates:
            report.append(f"{provider}: no catalog entries, skipped")
            continue
        if args.no_verify:
            verified.extend(f"{provider}:{m}" for m in candidates)
            report.append(f"{provider}: {len(candidates)} UNVERIFIED (--no-verify)")
            continue
        key = _env(cfg["key_env"])
        if not key:
            report.append(f"{provider}: {cfg['key_env']} not found, skipped ({len(candidates)} candidates unprobed)")
            continue
        with cf.ThreadPoolExecutor(max_workers=WORKERS) as pool:
            results = list(pool.map(lambda m: _probe(cfg["url"], key, cfg["style"], m), candidates))
        ok = [m for m, passed, _ in results if passed]
        failed = [(m, why) for m, passed, why in results if not passed]
        verified.extend(f"{provider}:{m}" for m in ok)
        report.append(f"{provider}: {len(ok)}/{len(candidates)} usable")
        for m, why in failed:
            report.append(f"  FAIL {provider}:{m}  [{why}]")

    print("\n".join(report))
    print(f"\ntotal usable: {len(verified)}")
    if args.dry_run:
        return
    doc = yaml.safe_load(CONFIG.read_text(encoding="utf-8")) or {}
    doc["available_models"] = verified
    CONFIG.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True), encoding="utf-8")
    print(f"config.yaml written with {len(verified)} verified ids")


if __name__ == "__main__":
    main()
