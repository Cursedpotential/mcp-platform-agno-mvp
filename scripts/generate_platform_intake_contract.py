"""Generate the bounded UIW OpenAPI contract from the live FastAPI models.

Byline: Codex · GPT-5.6-Sol · 2026-08-30
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "workbench" / "api"
TARGET = ROOT / "docs" / "schemas" / "platform-intake-job-contract-v1.openapi.yaml"
SELECTED_PATHS = (
    "/api/uiw/source-inspection",
    "/api/uiw/source-contexts",
    "/api/uiw/start",
    "/api/uiw/previews/{preview_handle}",
)


def _collect_schema_refs(value: Any, refs: set[str]) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "$ref" and isinstance(child, str):
                refs.add(child.rsplit("/", 1)[-1])
            else:
                _collect_schema_refs(child, refs)
    elif isinstance(value, list):
        for child in value:
            _collect_schema_refs(child, refs)


def render_contract() -> str:
    sys.path.insert(0, str(API_ROOT))
    import main  # noqa: PLC0415

    source = main.app.openapi()
    paths = {path: source["paths"][path] for path in SELECTED_PATHS}
    refs: set[str] = set()
    _collect_schema_refs(paths, refs)
    while True:
        before = len(refs)
        for name in tuple(refs):
            _collect_schema_refs(source["components"]["schemas"][name], refs)
        if len(refs) == before:
            break
    contract = {
        "openapi": source["openapi"],
        "info": {
            "title": "Platform Intake and Governed Preview Contract",
            "version": "1.0.0",
            "x-byline": "Codex GPT-5.6-Sol 2026-08-30",
            "x-generated-from": "workbench.api.main:app.openapi",
            "description": (
                "Generated bounded client contract for the implemented UIW source inspection, "
                "append-only source context, start, and preview routes. Regenerate instead of "
                "hand-copying browser or backend types."
            ),
        },
        "paths": paths,
        "components": {
            "schemas": {name: source["components"]["schemas"][name] for name in sorted(refs)},
        },
    }
    return yaml.safe_dump(contract, sort_keys=False, allow_unicode=True, width=120)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    rendered = render_contract()
    if args.check:
        return 0 if TARGET.read_text(encoding="utf-8") == rendered else 1
    TARGET.write_text(rendered, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
