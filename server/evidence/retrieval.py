"""server/evidence/retrieval.py — THE horizon-gated evidence retrieval seam (ADR-0050 §4).

Byline: Claude Code · Fable 5 · 2026-08-11
Byline: Codex · GPT-5 · 2026-08-13 (make the injected audit seam type-safe)
Byline amendment: Codex · GPT-5 · 2026-08-18 (source-availability clock split)
Byline amendment: Codex · GPT-5 · 2026-08-18 (native Weaviate pre-ranking retrieval)

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

SOURCE AVAILABILITY (ADR-0059): first-party sources use occurrence; acquired
third-party sources use their approved acquisition. Realization events are
separate knowledge atoms and never move this raw-source boundary. Missing or
incomplete availability metadata is denied. The current Agno Weaviate adapter
can prefilter exact dict fields (case here) but stores metadata as JSON text,
so its missing range-prefilter support remains an activation hold; this seam
retains a defensive postcondition and never treats over-fetch as proof of a
safe horizon query.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any, Callable, Sequence

from server.core.knowledge_handle import resolve_knowledge

__all__ = ["evidence_search", "native_evidence_search", "EvidenceSearchResult"]

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


def native_evidence_search(
    store: Any,
    embed_query: Callable[[str], Sequence[float]],
    query: str,
    *,
    horizon: datetime | None,
    actor: str,
    disclosure_tiers: Sequence[str],
    case_id: str = "primary",
    limit: int = 10,
    mode: str = "hybrid",
    audit: Callable[..., int] | None = None,
) -> EvidenceSearchResult:
    """Native horizon-safe search with permission-derived disclosure tiers.

    The caller must resolve tiers from authenticated permissions.  There is no
    ``allow_hindsight`` convenience flag because that would turn authorization
    into caller-controlled query input.
    """

    from server.core.evidence_vector_store import EVIDENCE_EMBED_DIM, NativeEvidenceVectorStore

    if not isinstance(store, NativeEvidenceVectorStore):
        raise TypeError("native_evidence_search requires NativeEvidenceVectorStore")
    allowed = {"contemporaneous", "discovered", "hindsight"}
    tiers = list(dict.fromkeys(disclosure_tiers))
    if not tiers or not set(tiers).issubset(allowed):
        raise ValueError("disclosure_tiers must be a non-empty permission-derived tier set")
    vector = embed_query(query)
    if vector is None or len(vector) != EVIDENCE_EMBED_DIM:
        actual = "none" if vector is None else str(len(vector))
        raise RuntimeError(f"query embedder returned dimension {actual}; expected {EVIDENCE_EMBED_DIM}")
    response = store.search(
        vector=vector,
        query=query if mode == "hybrid" else None,
        mode=mode,  # type: ignore[arg-type]
        horizon=horizon,
        case_id=case_id,
        disclosure_tiers=tiers,  # type: ignore[arg-type]
        limit=limit,
    )
    documents = list(response.objects)
    if audit is None:
        from server.core.audit import record_read

        audit = record_read
    audit_id = audit(
        hashlib.sha256(query.encode("utf-8")).hexdigest(),
        actor=actor,
        ctx={
            "case_id": case_id,
            "horizon": horizon.isoformat() if horizon is not None else None,
            "unbounded_hindsight": horizon is None,
            "disclosure_tiers": tiers,
            "lane": "evidence-native-weaviate",
            "kept": len(documents),
            "denied": 0,
            "prefiltered": True,
        },
        object_schema="knowledge/evidence-native",
    )
    return EvidenceSearchResult(documents, kept=len(documents), denied=0, audit_id=audit_id)


def _visible_from(meta: dict[str, Any]) -> str | None:
    """Return the raw-source boundary, failing closed on incomplete metadata."""
    if meta.get("source_availability_complete") is False:
        return None
    value = meta.get("source_available_from") or meta.get("visible_from")
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
    # Weaviate accepts dictionaries and drops FilterExpr lists. This exact
    # case predicate is therefore applied before ranking. Horizon range
    # prefiltering remains a release hold until the adapter exposes scalar
    # metadata properties instead of one JSON text property.
    raw = await engine.async_search(query, max_results=fetch, filters={"case_id": case_id})

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
