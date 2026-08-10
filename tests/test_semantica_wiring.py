"""Tests for analysis/semantica_wiring.py — Semantica seed-first hybrid wiring config.

Byline: Claude Code · Fable 5 · 2026-07-29 (rewritten for the ADR-0040 Weaviate
cutover — the previous version tested the retired Milvus lane and imported the
deleted server.analysis.milvus_forensic).

The load-bearing contracts: Semantica targets OUR stores (Weaviate on the data
tier, 4096-d nv-embed-v1 — not Semantica's 768 default — and the DozerDB
`evidence` DB where Semantica is the RBAC-scoped writer, permission-isolated
from Graphiti's `memory` DB per ADR-0036); WEAVIATE_URL host/port parsing incl.
defaults; and — court-critical — the emitted configs reference secrets by
env-var NAME only, never inlining the secret values. Connection constants are
read per-call via getenv, but EMBED_PLATFORM_* are import-time, so env-sensitive
tests reload the module.
"""

from __future__ import annotations

import importlib
import json
from types import ModuleType
from typing import Callable, Iterator

import pytest

import server.analysis.semantica_wiring as sw

_ENV_VARS = (
    "WEAVIATE_URL",
    "WEAVIATE_GRPC_PORT",
    "WEAVIATE_API_KEY",
    "EMBED_PLATFORM_ID",
    "EMBED_PLATFORM_DIM",
    "NEO4J_URI",
    "SEMANTICA_NEO4J_DATABASE",
    "SEMANTICA_NEO4J_USER",
    "SEMANTICA_NEO4J_PASSWORD",
)


@pytest.fixture
def wiring(monkeypatch: pytest.MonkeyPatch) -> Iterator[Callable[..., ModuleType]]:
    """Reload the wiring under a controlled env; teardown restores and reloads."""

    def load(**env: str) -> ModuleType:
        for var in _ENV_VARS:
            monkeypatch.delenv(var, raising=False)
        for key, val in env.items():
            monkeypatch.setenv(key, val)
        return importlib.reload(sw)

    yield load
    monkeypatch.undo()
    importlib.reload(sw)


# ---- vector lane: OUR Weaviate, platform embed contract -------------------------


def test_vector_store_targets_our_weaviate_with_defaults(wiring: Callable[..., ModuleType]) -> None:
    # Host/port assert AGAINST the module's own default constant (not a second
    # hardcoded IP literal here) — see server/analysis/semantica_wiring.py's
    # _DEFAULT_WEAVIATE_HOST docstring: the previous version of this test
    # hardcoded the RETIRED ovh-data IP (100.119.96.29) and silently drifted
    # when the module's default moved to ovh-files on 2026-08-06. Asserting
    # against the constant means a future host move needs zero test edits.
    m = wiring()
    cfg = m.vector_store_config()
    assert cfg["default_backend"] == "weaviate"
    assert cfg["dimension"] == 4096  # nv-embed-v1, NOT Semantica's 768 default
    assert cfg["embedding_model"] == "nvidia/nv-embed-v1"
    assert cfg["metric"] == "cosine"
    assert cfg["enable_hybrid_search"] is True
    assert (cfg["weaviate_host"], cfg["weaviate_rest_port"]) == (m._DEFAULT_WEAVIATE_HOST, 8081)
    assert cfg["weaviate_grpc_port"] == 50051
    assert cfg["weaviate_api_key_env"] == "WEAVIATE_API_KEY"  # name, not value
    assert cfg["target_collections"] == ["forensic_records", "forensic_findings", "forensic_patterns"]
    assert cfg["namespace"] == "casebible"


def test_vector_store_env_override_wins_over_module_default(wiring: Callable[..., ModuleType]) -> None:
    """Monkeypatched env-override path: WEAVIATE_URL must beat the module
    default host, proving the default is a fallback and not the only thing
    ever asserted (2026-08-09 S2 build-and-test-green task 3)."""
    m = wiring(WEAVIATE_URL="http://weaviate-override.example:9999")
    cfg = m.vector_store_config()
    assert cfg["weaviate_host"] == "weaviate-override.example"
    assert cfg["weaviate_host"] != m._DEFAULT_WEAVIATE_HOST
    assert cfg["weaviate_rest_port"] == 9999


def test_weaviate_url_to_host_port_parsing(wiring: Callable[..., ModuleType]) -> None:
    # scheme://host:port
    m = wiring(WEAVIATE_URL="https://weaviate.example.com:9081")
    assert m._weaviate_host_ports() == ("weaviate.example.com", 9081, 50051)

    # scheme-less host:port
    m = wiring(WEAVIATE_URL="10.0.0.5:1234")
    assert m._weaviate_host_ports() == ("10.0.0.5", 1234, 50051)

    # bare host -> default REST port
    m = wiring(WEAVIATE_URL="http://bare-host")
    assert m._weaviate_host_ports() == ("bare-host", 8081, 50051)

    # empty/hostless URL -> default tailnet host + port (asserted against the
    # module's own default constant — see test_vector_store_targets_our_
    # weaviate_with_defaults above for why this isn't a second IP literal)
    m = wiring(WEAVIATE_URL="")
    assert m._weaviate_host_ports() == (m._DEFAULT_WEAVIATE_HOST, 8081, 50051)

    # trailing slash / path must not poison the port
    m = wiring(WEAVIATE_URL="http://weaviate.internal:8081/")
    assert m._weaviate_host_ports() == ("weaviate.internal", 8081, 50051)
    m = wiring(WEAVIATE_URL="http://weaviate.internal:8081/some/path")
    assert m._weaviate_host_ports() == ("weaviate.internal", 8081, 50051)

    # gRPC port override rides along
    m = wiring(WEAVIATE_URL="http://weaviate.internal:8081", WEAVIATE_GRPC_PORT="50099")
    assert m._weaviate_host_ports() == ("weaviate.internal", 8081, 50099)


def test_dimension_follows_platform_embed_contract(wiring: Callable[..., ModuleType]) -> None:
    m = wiring(EMBED_PLATFORM_DIM="1536", EMBED_PLATFORM_ID="mistralai/codestral-embed-2505")
    cfg = m.vector_store_config()
    assert cfg["dimension"] == 1536
    assert cfg["embedding_model"] == "mistralai/codestral-embed-2505"


# ---- graph lane: DozerDB evidence DB, Semantica as RBAC-scoped writer -----------


def test_graph_store_defaults_and_isolation(wiring: Callable[..., ModuleType]) -> None:
    # uri asserted AGAINST the module's own default constant — see
    # test_vector_store_targets_our_weaviate_with_defaults above for why this
    # isn't a second hardcoded IP literal.
    m = wiring()
    cfg = m.graph_store_config()
    assert cfg["backend"] == "neo4j"  # DozerDB = Neo4j Community + multi-DB/RBAC
    assert cfg["uri"] == f"bolt://{m._DEFAULT_NEO4J_HOST}:7687"
    assert cfg["database"] == "evidence"  # ADR-0036 split — NOT graphiti's memory DB
    assert cfg["user"] == "semantica_writer"  # RBAC-scoped writer role
    assert cfg["password_env"] == "SEMANTICA_NEO4J_PASSWORD"  # name, not value
    assert cfg["role"] == "writer"
    assert "0036" in cfg["isolation"]


def test_graph_store_reads_env_overrides(wiring: Callable[..., ModuleType]) -> None:
    cfg = wiring(
        NEO4J_URI="bolt://other-host:7688",
        SEMANTICA_NEO4J_USER="svc",
        SEMANTICA_NEO4J_DATABASE="forensics",
    ).graph_store_config()
    assert (cfg["uri"], cfg["user"], cfg["database"]) == ("bolt://other-host:7688", "svc", "forensics")


# ---- seed-first + full wiring ----------------------------------------------------


def test_seed_config_seeds_from_postgres_ontology(wiring: Callable[..., ModuleType]) -> None:
    cfg = wiring().seed_config()
    assert cfg["seed_from"] == "postgres"
    assert set(cfg["ontology_tables"]) == {
        "reference.behavior_category",
        "reference.detection_pattern",
        "reference.pattern_lexicon",
    }
    assert cfg["entity_tables"] == ["working.entity", "working.entity_alias"]
    assert cfg["seal_policy"] == "skip_sealed_lexicon"  # sealed REDACTED rows never enter the graph
    assert cfg["extend_not_replace"] is True


def test_full_wiring_nests_all_three_lanes(wiring: Callable[..., ModuleType]) -> None:
    m = wiring()
    w = m.full_wiring()
    assert w["mode"] == "seed_first_hybrid"
    assert "semantica" in w["graph_writer"]  # evidence DB only; memory DB is graphiti's
    assert w["vector_store"] == m.vector_store_config()
    assert w["graph_store"] == m.graph_store_config()
    assert w["seed"] == m.seed_config()


# ---- secrets: referenced by NAME, never inlined ----------------------------------


def test_secrets_referenced_by_name_and_values_never_inlined(wiring: Callable[..., ModuleType]) -> None:
    m = wiring(
        WEAVIATE_URL="http://weaviate.internal:8081",
        WEAVIATE_API_KEY="WEAVIATE-SECRET-VALUE-9x7",
        SEMANTICA_NEO4J_PASSWORD="NEO4J-SECRET-VALUE-3q1",
    )
    assert m.secrets_referenced() == ["WEAVIATE_API_KEY", "SEMANTICA_NEO4J_PASSWORD"]

    dump = json.dumps(m.full_wiring())
    for secret in ("WEAVIATE-SECRET-VALUE-9x7", "NEO4J-SECRET-VALUE-3q1"):
        assert secret not in dump, f"secret value leaked into wiring config: {secret}"

    w = m.full_wiring()
    assert w["vector_store"]["weaviate_api_key_env"] == "WEAVIATE_API_KEY"
    assert w["graph_store"]["password_env"] == "SEMANTICA_NEO4J_PASSWORD"

    # Honest pin: the identifier half (user) IS embedded — it's an identifier,
    # not the secret; the password/key values never are.
    assert w["graph_store"]["user"] == "semantica_writer"
