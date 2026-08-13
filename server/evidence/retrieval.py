"""server/evidence/retrieval.py — THE horizon-gated evidence retrieval seam (ADR-0050 §4).

Byline: Claude Code · Fable 5 · 2026-08-11
Byline: Codex · GPT-5 · 2026-08-13 (make the injected audit seam type-safe)

CONTRACT (ADR-0050 §4, owner-ruled 2026-08-10):
- This module is the ONLY sanctioned read path into the evidence knowledge
  base. No agent ever holds the raw evidence handle; Phase 4 wires agents to
  ``evidence_search`` (via the Evidence Analyst team member), never to the
  handle itself.
- Every search ALWAYS applies the horizon pre-filter. There is no bypass
  parameter on purpose — a caller who "just needs everything" is exactly the
  caller this seam exists to stop (horizon contamination destroys the
  as-lived-vs-hindsight delta, which IS the analytical deliverable).
- **Pre-S6 deny-undated default**: a document with no usable visibility clock
  is DENIED, and the denial is counted in the audit row.
- Every call is audited via ``server/core/audit.record_read`` (ADR-0047 —
  this is the first live caller of the S5 read interface). If the audit write
  fails, the search fails: an unaudited evidence read must not be served.

VISIBILITY CLOCK (ADR-0045, Option A):
``visible_from = COALESCE(earliest approved realization, occurred_at)``.
Until S6 lands realization events there are zero approved realizations, so
the live computation degenerates to ``occurred_at`` — this module therefore
reads ``visible_from`` from metadata when present (S6 will write it) and
falls back to ``occurred_at_min`` (written by ``store.horizon_axes`` today).
Neither present → deny. Timestamps are ISO-8601 UTC strings; lexicographic
comparison is correct for them and keeps the whole predicate flat-scalar
(the platform's Weaviate dict-filters-only constraint — filtering happens
app-side here because agno serializes metadata into one ``meta_data`` blob,
so no store-side range filter can reach it).
"""

from __future__ import annotations

import hashlib
from typing import Any, Callable

from server.core.knowledge_handle import resolve_knowledge

__all__ = ["evidence_search", "EvidenceSearchResult"]

# Over-fetch multiplier: the horizon filter runs AFTER vector search, so we
# pull extra candidates to keep post-filter recall reasonable. Bounded — the
# evidence corpus is retrieved per-conversation-document, not per-message.
_OVERFETCH = 5
_MAX_FETCH = 100


class EvidenceSearchResult:
    """What the seam returns: the visible documents plus the filter accounting
    (kept/denied counts + the audit row id), so callers and tests can observe
    the gate working rather than trusting it."""

    def __init__(self, documents: list[Any], kept: int, denied: int, audit_id: int) -> None:
        self.documents = documents
        self.kept = kept
        self.denied = denied
        self.audit_id = audit_id


def _visible_from(meta: dict[str, Any]) -> str | None:
    """ADR-0045 COALESCE(realized visibility, occurred_at) over the metadata
    that exists today. Returns None when the document has no usable clock."""
    value = meta.get("visible_from") or meta.get("occurred_at_min")
    return value if isinstance(value, str) and value else None


async def evidence_search(
    knowledge: Any,
    query: str,
    *,
    horizon: str,
    actor: str,
    limit: int = 10,
    case_id: str = "primary",
    audit: Callable[..., int] | None = None,
) -> EvidenceSearchResult:
    """Horizon-gated hybrid search over the evidence knowledge base.

    Parameters
    ----------
    knowledge:
        The evidence ``Knowledge`` instance or its ``KnowledgeHandle``
        (resolved freshly per call — boot-resilience contract).
    query:
        The search query.
    horizon:
        ISO-8601 UTC timestamp — the knowledge horizon this caller is allowed
        to see. Documents whose visibility clock is after this are denied.
    actor:
        Who is reading (agent/team/user id) — stamped into the audit row.
    limit:
        Max documents returned AFTER the horizon filter.
    case_id:
        Standing rule: TEXT 'primary'. Documents tagged with a different
        case_id are denied (defense in depth; there is only one case).
    audit:
        Injection point for tests ONLY. Defaults to
        ``server.core.audit.record_read``; a failed audit write raises —
        an unaudited evidence read is never served.
    """
    if not horizon or not isinstance(horizon, str):
        raise ValueError("evidence_search requires an ISO-8601 `horizon` string")

    if audit is None:
        from server.core.audit import record_read

        audit = record_read

    engine = resolve_knowledge(knowledge)
    if engine is None:
        raise RuntimeError("evidence knowledge base unavailable (handle unresolved)")

    fetch = min(max(limit * _OVERFETCH, limit), _MAX_FETCH)
    raw = await engine.async_search(query, max_results=fetch)

    kept: list[Any] = []
    denied = 0
    for doc in raw:
        meta = getattr(doc, "meta_data", None) or {}
        if meta.get("case_id") not in (None, case_id):
            denied += 1
            continue
        clock = _visible_from(meta)
        if clock is None or clock > horizon:
            denied += 1  # deny-undated + deny-future in one gate (ADR-0050 §4)
            continue
        kept.append(doc)
    visible = kept[:limit]

    # Audit BEFORE returning: the read row records the horizon that governed
    # the read, the query (hashed, not the text), and the gate accounting.
    audit_id = audit(
        hashlib.sha256(query.encode("utf-8")).hexdigest(),
        actor=actor,
        ctx={
            "case_id": case_id,
            "horizon": horizon,
            "lane": "evidence",
            "kept": len(visible),
            "denied": denied,
            "fetched": len(raw),
        },
        object_schema="knowledge/evidence",
    )
    return EvidenceSearchResult(visible, kept=len(visible), denied=denied, audit_id=audit_id)
