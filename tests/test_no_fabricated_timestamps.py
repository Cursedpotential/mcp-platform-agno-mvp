"""Forensic guardrail: parsers must NEVER fabricate an event timestamp.

Motivation (parser-iterations inventory, 2026-07-10): the TypeScript-lineage
iMessage-PDF and one Facebook parser fall back to ``now()`` when a message's
timestamp fails to parse — silently stamping evidence with the *processing*
time instead of the real event time. That is a court-fatal defect: a fabricated
timestamp on an exhibit destroys its evidentiary value and could be argued as
spoliation. Our Python parser lane deliberately does the opposite — it returns
``None`` / preserves the raw string (see ``imessage_txt._parse_ts`` retaining
``attrs['raw_timestamp']``) and never invents a clock time.

This test makes that guarantee mechanical so the TS trap can never creep into
the Python lane: it AST-scans every parser/extractor module and fails if any of
them calls a wall-clock source (``datetime.now``/``utcnow``/``today``,
``date.today``, ``time.time``). A parser has no legitimate reason to read the
current clock — event times come from the source data, not from when we ran.

If a future parser genuinely needs the current time for a NON-event field
(e.g. an ``ingested_at`` audit column), add it to ``_ALLOWED`` with a comment
explaining why it is not an event timestamp — never silently.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

# Roots that hold atomic parser/extractor tool modules.
_PARSER_ROOTS = [
    Path(__file__).resolve().parent.parent / "server" / "tools" / "parsers",
    Path(__file__).resolve().parent.parent / "server" / "tools" / "extractors",
]

# Wall-clock calls a parser must never make. Keyed by the trailing attribute
# name; we match on the attribute so ``datetime.now``, ``dt.datetime.now`` and
# ``timezone.now`` style chains are all caught regardless of import alias.
_FORBIDDEN_ATTRS = {"now", "utcnow", "today"}
_FORBIDDEN_FUNCS = {"time"}  # bare time.time()

# Explicit, documented exceptions. Format: (module_relpath, lineno_or_None).
# Empty by design — no parser currently reads the clock, and none should for an
# event timestamp. Add here ONLY with a comment justifying a non-event use.
_ALLOWED: set[tuple[str, str]] = set()


def _iter_parser_files() -> list[Path]:
    files: list[Path] = []
    for root in _PARSER_ROOTS:
        if root.exists():
            files.extend(p for p in root.rglob("*.py") if p.name != "__init__.py")
    return sorted(files)


def _clock_calls(path: Path) -> list[str]:
    """Return human-readable descriptions of any wall-clock calls in a module."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    hits: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        # datetime.now() / datetime.utcnow() / date.today() / dt.timezone.now()
        if isinstance(func, ast.Attribute) and func.attr in _FORBIDDEN_ATTRS:
            hits.append(f"{path.name}:{func.lineno} -> .{func.attr}()")
        # time.time()
        elif (
            isinstance(func, ast.Attribute)
            and func.attr in _FORBIDDEN_FUNCS
            and isinstance(func.value, ast.Name)
            and func.value.id == "time"
        ):
            hits.append(f"{path.name}:{func.lineno} -> time.time()")
    return hits


def test_parser_tree_is_nonempty() -> None:
    """Guard against the scan silently passing because it found no files
    (e.g. after a directory move like ADR-0035)."""
    files = _iter_parser_files()
    assert files, f"no parser modules found under {[str(r) for r in _PARSER_ROOTS]}"


@pytest.mark.parametrize("path", _iter_parser_files(), ids=lambda p: p.name)
def test_no_wallclock_calls_in_parser(path: Path) -> None:
    hits = [h for h in _clock_calls(path) if (path.name, h.split(" -> ")[0].split(":", 1)[1]) not in _ALLOWED]
    assert not hits, (
        "Parser fabricates a timestamp from the wall clock — forensic defect "
        "(see module docstring). Offending calls:\n  " + "\n  ".join(hits)
    )


def test_imessage_parse_ts_returns_none_on_garbage_not_now() -> None:
    """Behavioral spot-check: an unparseable timestamp yields None (raw preserved
    upstream), NEVER a synthesized 'now'."""
    from server.tools.parsers.messaging.imessage_txt import _parse_ts

    assert _parse_ts("not a timestamp at all") is None
    assert _parse_ts("") is None
    # A well-formed one still parses (proves we didn't just make it always-None).
    # Format is _TS_STRPTIME = "%b %d, %Y %I:%M:%S %p".
    assert _parse_ts("Jan 05, 2026 03:47:12 PM") is not None
