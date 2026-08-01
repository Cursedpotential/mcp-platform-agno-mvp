"""analysis/semantica_wiring.py — Semantica seed-first hybrid WIRING CONFIG (design/local).

Placement decision (BOARD 2026-07-01, ADR ~0035), REVISED per ADR-0036
(accepted 2026-07-29) and ADR-0040 / HANDOFF-2026-07-27:

  * Vector lane   → OUR Weaviate (data-weaviate on ovh-data, REST :8081 /
    gRPC :50051, `vectorizer: none` — we bring embeddings). Platform vector
    contract is nv-embed-v1 4096-d. Milvus is SIDELINED (ADR-0040): it stays
    up for memsearch only — no new platform writers, Semantica included.
  * Graph lane    → OUR Neo4j (DozerDB multi-database, ADR-0036). Semantica
    OWNS and WRITES the `evidence` database under the RBAC-scoped
    `semantica_writer` role. Graphiti owns and writes the `memory` database
    (agent memory) under `graphiti_writer` — and NOTHING else. The two graphs
    are permission-isolated and MUST stay separate; neither writes through
    the other, and no Graphiti coupling exists on this path.
  * Seed-first    → before Semantica extracts, we SEED it from Postgres: the
    behavioral ontology (analysis.behavior_category / detection_pattern) and any
    resolved analysis.entity rows. Semantica extends the seeded ontology rather
    than inventing a parallel one.

NET-NEW VALUE Semantica adds (why wire it at all): cross-source CONFLICT
detection, dedup, and decision-provenance over the evidence — lanes the current
custody->parse->normalize path does not cover.

This module builds config DICTS from env only. It performs NO writes and bakes
NO secrets (passwords/tokens are read from env at runtime, never hardcoded).
The actual Semantica deploy / any store creation is APPROVALS-gated.

> Byline: Claude Code · Fable 5 · 2026-07-29 — ADR-0036/0040 rewrite: Weaviate
> vector lane (4096-d), Semantica writes its own `evidence` DB, Graphiti
> decoupled (memory DB only).
"""

from __future__ import annotations

from os import getenv
from typing import Any

# Platform embedding contract for the vector lane (ADR-0040 / handoff):
# nv-embed-v1, 4096-d, embeddings supplied by us (Weaviate vectorizer=none).
EMBED_PLATFORM_ID = getenv("EMBED_PLATFORM_ID", "nvidia/nv-embed-v1")
EMBED_PLATFORM_DIM = int(getenv("EMBED_PLATFORM_DIM", "4096"))


def _weaviate_host_ports() -> tuple[str, int, int]:
    """Host + REST/gRPC ports for data-weaviate (compose exposes 8081/50051)."""
    url = getenv("WEAVIATE_URL", "http://100.119.96.29:8081")
    hostport = url.split("://", 1)[-1].split("/", 1)[0]
    host, _, port = hostport.partition(":")
    return host or "100.119.96.29", int(port or "8081"), int(getenv("WEAVIATE_GRPC_PORT", "50051"))


def vector_store_config() -> dict[str, Any]:
    """Semantica vector_store config → OUR Weaviate (ADR-0040), 4096-d nv-embed-v1.

    Milvus is deliberately absent: sidelined for memsearch only, no new writers.
    """
    host, rest_port, grpc_port = _weaviate_host_ports()
    return {
        "default_backend": "weaviate",  # VECTOR_STORE_DEFAULT_BACKEND
        "dimension": EMBED_PLATFORM_DIM,  # MUST match the platform contract (4096)
        "embedding_model": EMBED_PLATFORM_ID,  # we bring embeddings; vectorizer=none
        "metric": "cosine",  # VECTOR_STORE_METRIC
        "enable_hybrid_search": True,  # Weaviate-native BM25 + vector
        "weaviate_host": host,
        "weaviate_rest_port": rest_port,  # 8081 (8080 is coolify-proxy)
        "weaviate_grpc_port": grpc_port,
        "weaviate_api_key_env": "WEAVIATE_API_KEY",  # SECRET read at runtime (Phase-1 auth hardening)
        # Semantica writes its derived vectors into these forensic collections
        # (mirrors the two-collection design of ADR-0010/0011; dims carry over).
        "target_collections": ["forensic_records", "forensic_findings", "forensic_patterns"],
        "namespace": "casebible",
    }


def graph_store_config() -> dict[str, Any]:
    """Semantica graph_store config → the `evidence` DB on DozerDB (ADR-0036).

    Semantica is the WRITER of this database, scoped by the `semantica_writer`
    RBAC role. It is permission-isolated from Graphiti's `memory` database
    (`graphiti_writer` role) — the two graphs stay separate BY MECHANISM, and
    Semantica never writes through (or to) Graphiti.
    """
    return {
        "backend": "neo4j",  # DozerDB = Neo4j Community + multi-DB/RBAC plugin
        # Tailnet bolt to the ovh3 data-tier Neo4j (compose exposes 7687).
        "uri": getenv("NEO4J_URI", "bolt://100.119.96.29:7687"),
        "database": getenv("SEMANTICA_NEO4J_DATABASE", "evidence"),  # ADR-0036 split
        "user": getenv("SEMANTICA_NEO4J_USER", "semantica_writer"),  # RBAC-scoped writer
        "password_env": "SEMANTICA_NEO4J_PASSWORD",  # SECRET read at runtime, never inlined
        "role": "writer",  # Semantica owns the evidence graph; agents read, never write
        "isolation": "adr-0036 (DozerDB multi-DB: memory=graphiti, evidence=semantica)",
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
        "adr": "~0035 (placement) + 0036 (graph isolation) + 0040 (Weaviate vector lane)",
        "mode": "seed_first_hybrid",
        "graph_writer": "semantica (evidence DB only; memory DB is graphiti's)",
        "vector_store": vector_store_config(),
        "graph_store": graph_store_config(),
        "seed": seed_config(),
        "deploy": "APPROVALS-gated (prod-infra); this config is design/local only",
    }


def secrets_referenced() -> list[str]:
    """Env vars this wiring reads at runtime — asserted NOT inlined anywhere."""
    return ["WEAVIATE_API_KEY", "SEMANTICA_NEO4J_PASSWORD"]


if __name__ == "__main__":  # pragma: no cover
    import json

    print(json.dumps(full_wiring(), indent=2))
