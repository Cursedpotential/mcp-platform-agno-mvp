# Byline: Claude Code · Sonnet (agent) · 2026-07-21
"""Ops Copilot preset prompts (C2.5 scope addition, owner 2026-07-21).

In-code DEFAULT_PRESETS merged with an optional JSON override file at
settings.copilot_presets_path (default /data/copilot/presets.json,
bind-mount-friendly — see compose.workbench.yaml). An override entry with
the same `id` as a default replaces it; new ids append.

Presets here are deliberately GENERIC (no case content). The owner's real
processing prompts live in a local, gitignored corpus
(docs/planning/chat-sample-analysis/, NOT read by this module) — the
defaults below mirror the SHAPE of prompt that corpus's per-file breakdowns
already hand-write (summarize / classify-by-domain / extract-artifacts /
diagnose / identify-format), so the override mechanism is ready for the
owner to drop their own prompts into the JSON file without touching code.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)

# Domain/topic-tag vocabulary mirrored from
# workbench/web/src/lib/shared/types.ts (DOMAIN_OPTIONS) and the platform's
# extraction-lane facet design (docs/planning/chat-sample-analysis/INDEX.md)
# — kept as plain prompt text here, not re-modeled as enums, since these are
# opaque strings to the LLM, not something this service validates.
DEFAULT_PRESETS: list[dict] = [
    {
        "id": "summarize-file",
        "label": "Summarize this file",
        "prompt": (
            "Summarize this file for an operator triaging it: a tight summary "
            "(5-8 sentences), then a bullet list of notable entities and dates "
            "mentioned."
        ),
        "wants_context": "file",
    },
    {
        "id": "classify-segments",
        "label": "Classify segments by domain",
        "prompt": (
            "Split this file into logical segments. For each segment, propose "
            "which of these domains it belongs to: timeline_relationship, "
            "personal_history, platform_design, legal_strategy — and which "
            "topic tag best fits: RELATIONSHIP_HISTORY, PERSONAL_LEGAL, "
            "DEVELOPMENT, EMOTIONAL, EVIDENCE, MIXED, UNKNOWN. A single "
            "conversation usually spans several domains/topics — don't force "
            "one label if the content doesn't fit one."
        ),
        "wants_context": "file",
    },
    {
        "id": "extract-artifacts",
        "label": "Extract artifacts",
        "prompt": (
            "List every embedded artifact in this file: code blocks, drafted "
            "documents or letters, and tables. For each, give a one-line "
            "description and roughly where it sits in the file."
        ),
        "wants_context": "file",
    },
    {
        "id": "diagnose-run",
        "label": "Diagnose this run",
        "prompt": (
            "Read the attached run's stage digest and explain what failed (or is stuck) and suggest a concrete fix."
        ),
        "wants_context": "run",
    },
    {
        "id": "identify-format",
        "label": "What format is this?",
        "prompt": (
            "Identify the export format and originating tool for this file "
            "(e.g. ChatGPT, Gemini, a native JSON export). Note the turn/role "
            "delimiters used, any metadata blocks, and parsing hazards a "
            "script would need to handle."
        ),
        "wants_context": "file",
    },
]


def _load_overrides() -> list[dict]:
    """Read settings.copilot_presets_path if present. Missing file, unreadable
    file, or malformed JSON all degrade to [] (defaults-only) rather than
    raising — a bad override file should never break the copilot page."""
    path = Path(settings.copilot_presets_path)
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        logger.warning("copilot presets: could not read %s: %s", path, e)
        return []
    if not isinstance(data, list):
        logger.warning("copilot presets: %s must be a JSON list, got %s", path, type(data).__name__)
        return []
    return [p for p in data if isinstance(p, dict) and p.get("id") and p.get("label") and p.get("prompt")]


def list_presets() -> list[dict]:
    """DEFAULT_PRESETS merged with the override file, keyed by `id`."""
    merged: dict[str, dict] = {p["id"]: p for p in DEFAULT_PRESETS}
    for preset in _load_overrides():
        merged[preset["id"]] = preset
    return list(merged.values())
