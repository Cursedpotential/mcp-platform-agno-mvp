"""Regenerate the `available_models` list in server/api/config.yaml.

Byline: Claude Code . Fable 5 . 2026-08-02

AgentOSConfig.available_models (rendered verbatim by GET /config) drives the
OS model picker. The owner's complaint "there's only one model available" was
a config gap: server/core/model_catalog.py has carried the full Ollama Cloud
and NVIDIA NIM id lists all along, unused. This script merges them into
config.yaml as `<provider>:<id>` entries so the picker shows every model the
platform can actually route.

Re-run after a catalog change:  uv run python scripts/update_available_models.py
"""

from __future__ import annotations

import pathlib

import yaml

from server.core.model_catalog import available_models

CONFIG = pathlib.Path(__file__).resolve().parents[1] / "server" / "api" / "config.yaml"

PROVIDERS = ("ollama", "nvidia", "google")


def main() -> None:
    doc = yaml.safe_load(CONFIG.read_text(encoding="utf-8")) or {}
    models: list[str] = []
    for provider in PROVIDERS:
        try:
            ids = available_models(provider)
        except Exception:
            ids = []
        models.extend(f"{provider}:{mid}" for mid in ids)
    doc["available_models"] = models
    CONFIG.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True), encoding="utf-8")
    print(f"config.yaml available_models <- {len(models)} ids "
          f"({', '.join(f'{p}:{len(available_models(p)) if p != 'google' else 0}' for p in PROVIDERS[:2])} ...)")


if __name__ == "__main__":
    main()
