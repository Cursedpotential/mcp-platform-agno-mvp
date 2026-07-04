"""evidence/court_language.py — court-safe language mapping for report rendering.

Loads evidence/config/court_safe_language_map.json (derived from
knowledge/legal/coercive-control-classification-rubric.md) and exposes the
diagnostic->court-safe translation the judge-friendly summary generator uses.

The point is prejudice-resistance: internal category keys and clinical labels
(gaslighting, "narcissistic," Cluster B) NEVER reach a court document. Every
finding is rendered under a descriptive, court-safe heading with hedged intent
phrasing — describe behavior, never diagnose.

    from evidence.court_language import court_safe_heading, load_language_map
    court_safe_heading("gaslighting_reality_distortion")
    # -> "Undermining Confidence in Memory or Judgment"
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

MAP_PATH = Path(__file__).parent / "config" / "court_safe_language_map.json"
PROMPT_PATH = Path(__file__).parent / "config" / "coercive_control_analyzer_prompt.md"

# Clinical/diagnostic terms that must never appear in a court-facing string.
_FORBIDDEN_IN_COURT = (
    "narcissist",
    "borderline",
    "antisocial",
    "cluster b",
    "psychopath",
    "sociopath",
    "npd",
    "bpd",
    "diagnos",
)


@lru_cache(maxsize=1)
def load_language_map(path: str | None = None) -> dict[str, Any]:
    """Load + validate the court-safe language map (cached)."""
    p = Path(path) if path else MAP_PATH
    data = json.loads(p.read_text(encoding="utf-8"))
    cats = data.get("categories")
    if not isinstance(cats, dict) or not cats:
        raise ValueError("court_safe_language_map: no categories")
    for key, entry in cats.items():
        heading = entry.get("court_safe_heading", "")
        if not heading:
            raise ValueError(f"category {key!r} missing court_safe_heading")
        low = heading.lower()
        bad = [t for t in _FORBIDDEN_IN_COURT if t in low]
        if bad:
            raise ValueError(f"court_safe_heading for {key!r} leaks clinical term(s) {bad}: {heading!r}")
    return data


def category_keys() -> list[str]:
    return sorted(load_language_map()["categories"])


def court_safe_heading(category_key: str) -> str:
    """Court-safe heading for an internal category key (KeyError if unknown)."""
    cats = load_language_map()["categories"]
    if category_key not in cats:
        raise KeyError(f"unknown category {category_key!r}; known: {sorted(cats)}")
    return cats[category_key]["court_safe_heading"]


def analyzer_prompt() -> str:
    """The Part-2 meta-analysis system prompt (verbatim)."""
    return PROMPT_PATH.read_text(encoding="utf-8")
