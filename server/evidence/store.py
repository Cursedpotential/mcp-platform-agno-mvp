"""
evidence/store.py — persist normalized records + feed the knowledge engine.

Two sinks (P2 scope):
  1. analysis.normalized_record — the relational home of every canonical record,
     carrying the bitemporal fields (occurred_at / knowledge_time / disclosure_tier).
  2. The domain-partitioned KNOWLEDGE engine (Milvus collection `platform_knowledge`,
     ADR-0027 — vectors in Milvus, contents in Postgres): transcripts are re-rendered
     as conversation markdown and inserted with a `domain` metadata tag
     (timeline_relationship | personal_history | platform_design | legal_strategy) so
     agents filter to their domains (native knowledge_filters — see docs/DEBT.md).

P3 extends this module with the Graphiti bitemporal episode writes; the
relational + vector sinks here are complete for P2.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text

from server.evidence.custody import ArtifactRef
from server.contracts.records import NormalizedRecord

_engine = None

KNOWLEDGE_DOMAINS = (
    "timeline_relationship",
    "personal_history",
    "platform_design",
    "legal_strategy",
)


def _get_engine():
    global _engine
    if _engine is None:
        from server.core.url import db_url

        _engine = create_engine(db_url, pool_pre_ping=True)
    return _engine


def store_records(records: list[NormalizedRecord], artifact: ArtifactRef) -> int:
    """Batch-insert canonical records into analysis.normalized_record."""
    if not records:
        return 0
    rows = [
        {
            "artifact_id": artifact.artifact_id,
            "record_type": r.record_type.value,
            "source": r.source,
            "conversation_id": r.conversation_id,
            "role": r.role,
            "participants": json.dumps(r.participants),
            "content": r.content,
            "occurred_at": r.occurred_at,
            "knowledge_time": r.knowledge_time,
            "disclosure_tier": r.disclosure_tier.value,
            "attrs": json.dumps(r.attrs),
        }
        for r in records
    ]
    with _get_engine().begin() as conn:
        conn.execute(
            text(
                "INSERT INTO analysis.normalized_record "
                "(artifact_id, record_type, source, conversation_id, role, participants, "
                " content, occurred_at, knowledge_time, disclosure_tier, attrs) "
                "VALUES (:artifact_id, :record_type, :source, :conversation_id, :role, "
                " CAST(:participants AS jsonb), :content, :occurred_at, :knowledge_time, "
                " :disclosure_tier, CAST(:attrs AS jsonb))"
            ),
            rows,
        )
    return len(rows)


def render_conversations_markdown(records: list[NormalizedRecord]) -> dict[str, str]:
    """Group records by conversation and render readable markdown per conversation
    (the document shape the knowledge engine chunks/embeds best)."""
    by_conv: dict[str, list[NormalizedRecord]] = defaultdict(list)
    for r in records:
        by_conv[r.conversation_id or "untitled"].append(r)

    docs: dict[str, str] = {}
    for conv_id, recs in by_conv.items():
        recs.sort(key=lambda r: r.occurred_at.isoformat() if r.occurred_at else "")
        title = recs[0].attrs.get("conversation_title") or conv_id
        lines = [f"# {title}", ""]
        if recs[0].occurred_at:
            lines += [f"_First message: {recs[0].occurred_at.isoformat()}_", ""]
        for r in recs:
            stamp = f" — {r.occurred_at.isoformat()}" if r.occurred_at else ""
            lines += [f"**{(r.role or 'unknown').upper()}{stamp}:**", "", r.content, "", "---", ""]
        docs[conv_id] = "\n".join(lines)
    return docs


async def ingest_into_knowledge(
    knowledge,
    records: list[NormalizedRecord],
    artifact: ArtifactRef,
    domain: str,
    derived_dir: str | Path = "knowledge/platform/transcripts",
) -> int:
    """Render per-conversation markdown, persist under knowledge/, and ainsert
    into the engine with the domain tag (agents filter on metadata.domain)."""
    if domain not in KNOWLEDGE_DOMAINS:
        raise ValueError(f"unknown knowledge domain {domain!r}; expected one of {KNOWLEDGE_DOMAINS}")
    docs = render_conversations_markdown(records)
    out_dir = Path(derived_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for conv_id, markdown in docs.items():
        safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in conv_id)[:80] or "conv"
        doc_path = out_dir / f"{artifact.sha256[:12]}-{safe}.md"
        doc_path.write_text(markdown, encoding="utf-8")
        await knowledge.ainsert(
            name=doc_path.stem,
            path=str(doc_path),
            metadata={
                "domain": domain,
                "category": "transcripts",
                "artifact_id": artifact.artifact_id,
                "sha256": artifact.sha256,
                "conversation_id": conv_id,
            },
        )
        count += 1
    return count


def record_counts(artifact_id: str) -> dict[str, Any]:
    """Quick verification helper: counts for one artifact."""
    with _get_engine().connect() as conn:
        row = (
            conn.execute(
                text(
                    "SELECT count(*) AS records, count(DISTINCT conversation_id) AS conversations "
                    "FROM analysis.normalized_record WHERE artifact_id = :a"
                ),
                {"a": artifact_id},
            )
            .mappings()
            .first()
        )
    return dict(row) if row else {"records": 0, "conversations": 0}
