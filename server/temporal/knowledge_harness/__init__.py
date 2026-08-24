"""
server/temporal/knowledge_harness — THE FRAMEWORK BAKE.

One interface, two implementations of the knowledge step, both calling the SAME
governed door. The bake exists to answer a single question with running code
instead of opinion: does the platform's knowledge stage read better as
Agno-as-library or as a PydanticAI agent with a typed tool? Scoring sheet and
the deletion rule live in ``BAKE.md`` next to this file.

THE INTERFACE
-------------

    async def run_knowledge_step(
        records_ref: RecordsRef,
        lane: str,
        run_meta: dict[str, Any],
    ) -> KnowledgeResult

- ``records_ref`` names the records by custody ``artifact_id``; each side reads
  them back out of Postgres with ``store.py::load_records_for_artifact`` (:576).
  Postgres stays authority — the records never travel on a wire, and neither
  harness is allowed to reconstruct them from anything else.
- ``lane`` is the ADR-0053 five-lane vocabulary (``store.py:67`` —
  platform / legal / personal_history / context / evidence). The chat-transcript
  vertical defaults to ``context`` (``run_routes.py:114``).
- ``run_meta`` is opaque reporting context (run_id, parent_run_id, harness
  notes). It must never become an input to any hash or projection decision.

Selection is by environment: ``KNOWLEDGE_HARNESS=agno`` (default) or
``pydantic_ai``. That is what the env flip in BAKE.md toggles, and what
``activities.py::knowledge_activity`` reads.

This module is stdlib-only on purpose — ``activities.py`` imports it at module
scope, and workflow code imports ``activities`` for its dataclass types. Both
harness implementations are imported lazily inside ``get_harness``.

Byline: Claude Code · Opus 5 · 2026-08-23
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

__all__ = [
    "RecordsRef",
    "KnowledgeResult",
    "KnowledgeStep",
    "HARNESSES",
    "DEFAULT_HARNESS",
    "get_harness",
]

DEFAULT_HARNESS = "agno"
HARNESSES = ("agno", "pydantic_ai")


@dataclass
class RecordsRef:
    """Pointer to already-stored records. Postgres is the only place they live.

    ``record_ids`` is optional and additive: the native projection path enqueues
    by ``working.normalized_record`` id (``workflows.py:1122``), so a harness
    that wants to narrow a replay can, while the default (empty) means "every
    record for this artifact", matching ``run_knowledge_from_store``."""

    artifact_id: str
    record_ids: list[str] = field(default_factory=list)


@dataclass
class KnowledgeResult:
    """The shared contract. Both harnesses return exactly this — that identity
    is what makes the bake a comparison rather than two features.

    Field meanings are taken from the live knowledge step's ctx keys
    (``workflows.py:111-158`` ``_ledger_stage_output``): ``docs_ingested`` is
    ``ctx['knowledge_docs']``, ``skipped`` is ``ctx['knowledge_skipped']``,
    ``attempts`` is ``ctx['knowledge_attempts']``. ``harness`` names which side
    of the bake produced the row, so a run report can attribute it."""

    docs_ingested: int
    skipped: bool
    detail: str
    harness: str
    lane: str
    attempts: list[dict[str, Any]] = field(default_factory=list)


KnowledgeStep = Callable[[RecordsRef, str, dict[str, Any]], Awaitable[KnowledgeResult]]


def get_harness(name: str | None = None) -> KnowledgeStep:
    """Return the selected harness's ``run_knowledge_step``.

    ``name`` defaults to ``agno``. An empty/whitespace value is treated as
    unset (a Coolify env var set to an empty string is a real occurrence), and
    an unknown value is a hard ``ValueError`` — silently falling back to the
    default would make a mistyped flip look like a successful A/B.

    The implementation modules are imported HERE, not at module scope: the agno
    side pulls in ``server.evidence``/``server.core`` (DB + Weaviate + embedder
    config) and the pydantic_ai side pulls in an optional dependency. Neither
    belongs in an import that workflow code transitively touches."""
    selected = (name or DEFAULT_HARNESS).strip() or DEFAULT_HARNESS
    if selected == "agno":
        from server.temporal.knowledge_harness.agno_harness import run_knowledge_step

        return run_knowledge_step
    if selected == "pydantic_ai":
        from server.temporal.knowledge_harness.pydantic_ai_harness import run_knowledge_step

        return run_knowledge_step
    raise ValueError(f"unknown KNOWLEDGE_HARNESS {selected!r}; expected one of {HARNESSES}")
