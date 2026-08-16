"""Semantica worker and downstream projection wiring (design/local).

Placement decision (BOARD 2026-07-01, ADR ~0035), REVISED per ADR-0036
(accepted 2026-07-29) and ADR-0040 / HANDOFF-2026-07-27:

ADR-0043 is authoritative: the Semantica WORKER accepts immutable normalized
batches and emits candidates only. It receives no store credentials. The
historical graph/vector helpers below describe later platform-owned projectors;
they are not passed to ``server.analysis.semantica_worker``.

  * Vector projection → OUR Weaviate (data-weaviate on ovh-files, REST :8081 /
    gRPC :50051, `vectorizer: none` — we bring embeddings). Platform vector
    contract is nv-embed-v1 4096-d. Milvus is SIDELINED (ADR-0040): it stays
    up for memsearch only — no new platform writers, Semantica included.
  * Graph projection → OUR Neo4j `evidence` database only after candidate
    approval. Graphiti owns `memory`. The extraction worker writes neither.
  * Seed-first    → before Semantica extracts, we SEED it from Postgres: the
    behavioral ontology (reference.behavior_category / detection_pattern) and any
    resolved working.entity rows. Semantica extends the seeded ontology rather
    than inventing a parallel one.

NET-NEW VALUE Semantica adds (why wire it at all): cross-source CONFLICT
detection, dedup, and decision-provenance over the evidence — lanes the current
custody->parse->normalize path does not cover.

This module builds config DICTS only. It performs NO writes and bakes NO
secrets. Worker deployment and all projection activation remain approval-gated.

> Byline: Claude Code · Fable 5 · 2026-07-29 — ADR-0036/0040 rewrite: Weaviate
> vector lane (4096-d) and isolated evidence/memory databases. Its original
> direct-writer assignment is superseded by ADR-0043 and the correction below.
> Byline: Codex · GPT-5 · 2026-08-16 — ADR-0043 correction: worker is
> credential-free and candidate-only; graph/vector configs are projector-only.
"""

from __future__ import annotations

from os import getenv
from typing import Any

# Platform embedding contract for the vector lane (ADR-0040 / handoff):
# nv-embed-v1, 4096-d, embeddings supplied by us (Weaviate vectorizer=none).
EMBED_PLATFORM_ID = getenv("EMBED_PLATFORM_ID", "nvidia/nv-embed-v1")
EMBED_PLATFORM_DIM = int(getenv("EMBED_PLATFORM_DIM", "4096"))

# Named default-host constants (2026-08-09, S2 build-and-test-green task 3):
# extracted out of the getenv() calls below so tests can assert AGAINST these
# constants instead of hardcoding the IP a second time. The prior test file
# hardcoded the RETIRED host (100.119.96.29, ovh-data) and went stale silently
# when the defaults below were corrected to ovh-files on 2026-08-06 — the same
# stale-host failure shape this module's own docstrings warn about. Asserting
# against the constant means a future host move is a one-line change here with
# zero test edits, instead of re-arming the same trap with a second literal.
_DEFAULT_WEAVIATE_HOST = "100.91.190.107"  # ovh-files (data-weaviate-files)
_DEFAULT_NEO4J_HOST = "100.91.190.107"  # ovh-files (data-neo4j-files)


def _weaviate_host_ports() -> tuple[str, int, int]:
    """Host + REST/gRPC ports for data-weaviate (compose exposes 8081/50051).

    Defaults corrected 2026-08-06: ~~100.119.96.29 (ovh-data)~~ -> 100.91.190.107
    (ovh-files). Same stale-host bug that silently broke the platform Weaviate
    client — `data-weaviate` on ovh-data is exited:unhealthy, `data-weaviate-files`
    on ovh-files is the live one. See server/core/session.py::WEAVIATE_HTTP_HOST.
    """
    url = getenv("WEAVIATE_URL", f"http://{_DEFAULT_WEAVIATE_HOST}:8081")
    hostport = url.split("://", 1)[-1].split("/", 1)[0]
    host, _, port = hostport.partition(":")
    return host or _DEFAULT_WEAVIATE_HOST, int(port or "8081"), int(getenv("WEAVIATE_GRPC_PORT", "50051"))


def vector_store_config() -> dict[str, Any]:
    """Approval-gated downstream vector-projector config, never worker config.

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
        # A separately approved platform projector may write promoted outputs
        # into these collections. The Semantica worker never receives this config.
        "target_collections": ["forensic_records", "forensic_findings", "forensic_patterns"],
        "namespace": "casebible",
    }


def graph_store_config() -> dict[str, Any]:
    """Approval-gated downstream graph-projector config, never worker config.

    A platform-owned projector is the eventual writer, permission-isolated from
    Graphiti's ``memory`` database. Semantica emits pending PostgreSQL candidates
    only and never receives this credential or writes either graph directly.
    """
    return {
        "backend": "neo4j",  # DozerDB = Neo4j Community + multi-DB/RBAC plugin
        # Tailnet bolt to the data-tier Neo4j (compose exposes 7687).
        # Default corrected 2026-08-06: ~~100.119.96.29 (ovh-data)~~ ->
        # 100.91.190.107 (ovh-files). Verified live from inside agentos-api the
        # same day: ovh-data:7687 UNREACHABLE, ovh-files:7687 OPEN. `data-neo4j`
        # on ovh-data is exited:unhealthy; the healthy one runs on ovh-files.
        "uri": getenv("NEO4J_URI", f"bolt://{_DEFAULT_NEO4J_HOST}:7687"),
        "database": getenv("PLATFORM_NEO4J_PROJECTOR_DATABASE", "evidence"),
        "user": getenv("PLATFORM_NEO4J_PROJECTOR_USER", "platform_projector"),
        "password_env": "PLATFORM_NEO4J_PROJECTOR_PASSWORD",
        "role": "writer",  # held platform projector role; agents read, never write
        "isolation": "adr-0036/0043 (memory=graphiti; evidence=approved platform projection)",
    }


def seed_config() -> dict[str, Any]:
    """Seed-first: Postgres ontology/entities feed Semantica before extraction."""
    return {
        "seed_from": "postgres",
        "ontology_tables": [
            "reference.behavior_category",  # 153 categories (polarity/severity/mcl)
            "reference.detection_pattern",  # 512 patterns
            "reference.pattern_lexicon",  # 51 terms (sealed stay REDACTED until out-of-band loader)
        ],
        "entity_tables": ["working.entity", "working.entity_alias"],
        "seal_policy": "skip_sealed_lexicon",  # never pull REDACTED placeholders into the graph
        "extend_not_replace": True,
    }


def worker_wiring() -> dict[str, Any]:
    """Credential-free governed extraction worker contract (ADR-0043)."""
    return {
        "adr": "0043 (governed extraction worker)",
        "mode": "candidate_only",
        "input": "immutable_normalized_batch",
        "runtime": "server.analysis.semantica_worker.SemanticaPatternWorker",
        "candidate_tables": [
            "working.candidate_entity",
            "working.candidate_fact",
            "working.candidate_event",
        ],
        "store_credentials": [],
        "forbidden_writes": ["evidence.*", "neo4j", "weaviate", "surrealdb", "graphiti"],
        "fabricated_adjacency": False,
        "deploy": "APPROVALS-gated; fixture/in-process adapter only",
    }


def projection_wiring() -> dict[str, Any]:
    """Later approved projectors; not imported or passed to the worker."""
    return {
        "adr": "0036 (graph isolation) + 0040 (Weaviate) + 0043 (approval first)",
        "mode": "approved_candidate_projection",
        "vector_store": vector_store_config(),
        "graph_store": graph_store_config(),
        "seed": seed_config(),
        "deploy": "APPROVALS-gated; worker cannot load this config",
    }


def full_wiring() -> dict[str, Any]:
    """Back-compatible name now resolving to the safe worker contract."""
    return worker_wiring()


def secrets_referenced() -> list[str]:
    """The worker contract references no secret or credential."""
    return []


def projection_secrets_referenced() -> list[str]:
    """Credential env names reserved for separately approved projectors."""
    return ["WEAVIATE_API_KEY", "PLATFORM_NEO4J_PROJECTOR_PASSWORD"]


if __name__ == "__main__":  # pragma: no cover
    import json

    print(json.dumps(full_wiring(), indent=2))
