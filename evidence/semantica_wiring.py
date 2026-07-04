"""
evidence/semantica_wiring.py — Semantica seed-first hybrid WIRING CONFIG (design/local).

Placement decision (BOARD 2026-07-01, ADR ~0035): Semantica runs as a
**seed-first hybrid** whose stores target OUR infra — it does NOT stand up a
second graph or a second vector index, and it is NOT the graph writer.

  * Vector lane   → OUR Milvus (MILVUS_ADDRESS). Semantica's milvus_store writes
    its derived/semantic vectors into the forensic_* collections defined in
    evidence/milvus_forensic.py (dim-locked to bge-m3 1024-d). No 2nd index.
  * Graph lane    → OUR Neo4j (bolt). Semantica's neo4j_store is READ/derive-side
    (entity-linking, conflict detection, decision-provenance). The GRAPH WRITER
    STAYS GRAPHITI (ADR-0014): Graphiti owns bitemporal writes to Neo4j under
    group_id="casebible". Semantica proposes; Graphiti persists.
  * Seed-first    → before Semantica extracts, we SEED it from Postgres: the
    behavioral ontology (analysis.behavior_category / detection_pattern) and any
    resolved analysis.entity rows. Semantica extends the seeded ontology rather
    than inventing a parallel one.

NET-NEW VALUE Semantica adds (why wire it at all): cross-source CONFLICT
detection, dedup, and decision-provenance over the evidence — lanes the current
custody->parse->normalize->Graphiti path does not cover.

This module builds config DICTS from env only. It performs NO writes and bakes
NO secrets (passwords/tokens are read from env at runtime, never hardcoded).
The actual Semantica deploy / any store creation is APPROVALS-gated.
"""

from __future__ import annotations

from os import getenv
from typing import Any

# Reuse the exact dimension/URI contract the platform already fixed.
from evidence.milvus_forensic import EMBED_TEXT_DIM, MILVUS_TOKEN, MILVUS_URI


def _milvus_host_port() -> tuple[str, int]:
    """Semantica's MilvusStore takes host/port (not a URI). Derive from ours."""
    uri = MILVUS_URI.split("://", 1)[-1]
    host, _, port = uri.partition(":")
    return host or "100.119.96.29", int(port or "19530")


def _milvus_user_pass() -> tuple[str, str]:
    user, _, pw = MILVUS_TOKEN.partition(":")
    return user or "root", pw or "Milvus"


def vector_store_config() -> dict[str, Any]:
    """Semantica vector_store config → OUR Milvus, dim-locked to bge-m3 1024.
    Keys mirror semantica.vector_store.config env mappings."""
    host, port = _milvus_host_port()
    user, pw = _milvus_user_pass()
    return {
        "default_backend": "milvus",  # VECTOR_STORE_DEFAULT_BACKEND
        "dimension": EMBED_TEXT_DIM,  # VECTOR_STORE_DIMENSION — MUST match ours (not the 768 default)
        "metric": "cosine",  # VECTOR_STORE_METRIC
        "enable_hybrid_search": True,  # VECTOR_STORE_ENABLE_HYBRID_SEARCH
        "milvus_host": host,  # VECTOR_STORE_MILVUS_HOST
        "milvus_port": port,  # VECTOR_STORE_MILVUS_PORT
        "milvus_user": user,  # from MILVUS_TOKEN
        "milvus_password_env": "MILVUS_TOKEN",  # SECRET read at runtime, never inlined
        # Semantica writes its derived vectors into these forensic collections.
        "target_collections": ["forensic_records", "forensic_findings", "forensic_patterns"],
        "namespace": "casebible",
    }


def graph_store_config() -> dict[str, Any]:
    """Semantica graph_store config → OUR Neo4j, READ/derive-side only.
    Graphiti remains the sole writer (group_id='casebible')."""
    return {
        "backend": "neo4j",
        # Tailnet bolt to the ovh3 data-tier Neo4j (compose exposes 7687).
        "uri": getenv("NEO4J_URI", "bolt://100.119.96.29:7687"),
        "user": getenv("NEO4J_USER", "neo4j"),
        "password_env": "NEO4J_PASSWORD",  # SECRET read at runtime, never inlined
        "database": getenv("NEO4J_DATABASE", "neo4j"),
        "group_id": "casebible",
        "role": "read_derive",  # entity-link / conflict / provenance
        "writer": "graphiti",  # ADR-0014 — Graphiti persists; Semantica proposes
        "write_via_graphiti": True,
        "graphiti_mcp_url_env": "GRAPHITI_MCP_URL",
    }


def seed_config() -> dict[str, Any]:
    """Seed-first: Postgres ontology/entities feed Semantica before extraction."""
    return {
        "seed_from": "postgres",
        "ontology_tables": [
            "analysis.behavior_category",  # 153 categories (polarity/severity/mcl)
            "analysis.detection_pattern",  # 512 patterns
            "analysis.pattern_lexicon",  # 51 terms (sealed stay REDACTED until out-of-band loader)
        ],
        "entity_tables": ["analysis.entity", "analysis.entity_alias"],
        "seal_policy": "skip_sealed_lexicon",  # never pull REDACTED placeholders into the graph
        "extend_not_replace": True,
    }


def full_wiring() -> dict[str, Any]:
    """Complete seed-first hybrid wiring config (design/local; no writes)."""
    return {
        "adr": "~0035 (Semantica placement)",
        "mode": "seed_first_hybrid",
        "graph_writer": "graphiti",
        "vector_store": vector_store_config(),
        "graph_store": graph_store_config(),
        "seed": seed_config(),
        "deploy": "APPROVALS-gated (prod-infra); this config is design/local only",
    }


def secrets_referenced() -> list[str]:
    """Env vars this wiring reads at runtime — asserted NOT inlined anywhere."""
    return ["MILVUS_TOKEN", "NEO4J_PASSWORD", "GRAPHITI_MCP_URL"]


if __name__ == "__main__":  # pragma: no cover
    import json

    print(json.dumps(full_wiring(), indent=2))
