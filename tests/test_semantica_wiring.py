"""Tests for evidence/semantica_wiring.py — Semantica seed-first hybrid wiring config.

The load-bearing contracts: Semantica targets OUR stores (Milvus dim-locked to
bge-m3 1024-d — not Semantica's 768 default — and Neo4j read/derive-side with
Graphiti staying the sole graph writer per ADR-0014); MILVUS_ADDRESS URI ->
host/port parsing incl. defaults; and — court-critical — the emitted configs
reference secrets by env-var NAME only, never inlining the secret values.
Connection constants are read at import time, so env-sensitive tests reload
both this module and evidence.milvus_forensic (which it imports them from).
"""

from __future__ import annotations

import importlib
import json
from types import ModuleType
from typing import Callable, Iterator

import pytest

import server.analysis.milvus_forensic as mf
import server.analysis.semantica_wiring as sw

_ENV_VARS = (
    "MILVUS_ADDRESS",
    "MILVUS_TOKEN",
    "EMBED_TEXT_DIM",
    "FORENSIC_MILVUS_HYBRID",
    "FORENSIC_MILVUS_METRIC",
    "NEO4J_URI",
    "NEO4J_USER",
    "NEO4J_PASSWORD",
    "NEO4J_DATABASE",
    "GRAPHITI_MCP_URL",
)


@pytest.fixture
def wiring(monkeypatch: pytest.MonkeyPatch) -> Iterator[Callable[..., ModuleType]]:
    """Reload the wiring under a controlled env.

    semantica_wiring copies MILVUS_URI/MILVUS_TOKEN/EMBED_TEXT_DIM from
    milvus_forensic at import time, so both modules are reloaded. Teardown
    restores the original env and reloads them back so nothing leaks.
    """

    def load(**env: str) -> ModuleType:
        for var in _ENV_VARS:
            monkeypatch.delenv(var, raising=False)
        for key, val in env.items():
            monkeypatch.setenv(key, val)
        importlib.reload(mf)
        return importlib.reload(sw)

    yield load
    monkeypatch.undo()
    importlib.reload(mf)
    importlib.reload(sw)


# ---- vector lane: OUR Milvus, dim-locked ---------------------------------------


def test_vector_store_targets_our_milvus_with_defaults(wiring: Callable[..., ModuleType]) -> None:
    cfg = wiring().vector_store_config()
    assert cfg["default_backend"] == "milvus"
    assert cfg["dimension"] == 1024  # bge-m3, NOT Semantica's 768 default
    assert cfg["metric"] == "cosine"
    assert cfg["enable_hybrid_search"] is True
    assert (cfg["milvus_host"], cfg["milvus_port"]) == ("100.119.96.29", 19530)
    assert cfg["milvus_user"] == "root"
    assert cfg["milvus_password_env"] == "MILVUS_TOKEN"  # name, not value
    assert cfg["target_collections"] == ["forensic_records", "forensic_findings", "forensic_patterns"]
    assert cfg["namespace"] == "casebible"


def test_target_collections_match_forensic_specs(wiring: Callable[..., ModuleType]) -> None:
    m = wiring()
    assert m.vector_store_config()["target_collections"] == [s.name for s in mf.all_specs()]
    assert m.vector_store_config()["dimension"] == mf.EMBED_TEXT_DIM


def test_milvus_uri_to_host_port_parsing(wiring: Callable[..., ModuleType]) -> None:
    # scheme://host:port
    m = wiring(MILVUS_ADDRESS="https://milvus.example.com:29530")
    assert m._milvus_host_port() == ("milvus.example.com", 29530)

    # scheme-less host:port
    m = wiring(MILVUS_ADDRESS="10.0.0.5:1234")
    assert m._milvus_host_port() == ("10.0.0.5", 1234)

    # bare host -> default port
    m = wiring(MILVUS_ADDRESS="http://bare-host")
    assert m._milvus_host_port() == ("bare-host", 19530)

    # empty/hostless URI -> default tailnet host + port
    m = wiring(MILVUS_ADDRESS="")
    assert m._milvus_host_port() == ("100.119.96.29", 19530)

    # trailing slash / path must not poison the port (was: int("19530/") crash)
    m = wiring(MILVUS_ADDRESS="http://milvus.internal:19530/")
    assert m._milvus_host_port() == ("milvus.internal", 19530)
    m = wiring(MILVUS_ADDRESS="http://milvus.internal:19530/some/path")
    assert m._milvus_host_port() == ("milvus.internal", 19530)


def test_milvus_token_user_pass_parsing(wiring: Callable[..., ModuleType]) -> None:
    m = wiring(MILVUS_TOKEN="alice:pw1")
    assert m._milvus_user_pass() == ("alice", "pw1")
    assert m.vector_store_config()["milvus_user"] == "alice"

    # token without a colon -> user as given, default password
    m = wiring(MILVUS_TOKEN="justuser")
    assert m._milvus_user_pass() == ("justuser", "Milvus")

    # unset -> root:Milvus default
    m = wiring()
    assert m._milvus_user_pass() == ("root", "Milvus")


# ---- graph lane: OUR Neo4j, Graphiti stays the writer ---------------------------


def test_graph_store_defaults_and_graphiti_ownership(wiring: Callable[..., ModuleType]) -> None:
    cfg = wiring().graph_store_config()
    assert cfg["backend"] == "neo4j"
    assert cfg["uri"] == "bolt://100.119.96.29:7687"
    assert cfg["user"] == "neo4j" and cfg["database"] == "neo4j"
    assert cfg["password_env"] == "NEO4J_PASSWORD"  # name, not value
    assert cfg["group_id"] == "casebible"
    # ADR-0014: Semantica proposes, Graphiti persists
    assert cfg["role"] == "read_derive"
    assert cfg["writer"] == "graphiti" and cfg["write_via_graphiti"] is True
    assert cfg["graphiti_mcp_url_env"] == "GRAPHITI_MCP_URL"


def test_graph_store_reads_env_overrides(wiring: Callable[..., ModuleType]) -> None:
    cfg = wiring(
        NEO4J_URI="bolt://other-host:7688",
        NEO4J_USER="svc",
        NEO4J_DATABASE="forensics",
    ).graph_store_config()
    assert (cfg["uri"], cfg["user"], cfg["database"]) == ("bolt://other-host:7688", "svc", "forensics")


# ---- seed-first + full wiring ----------------------------------------------------


def test_seed_config_seeds_from_postgres_ontology(wiring: Callable[..., ModuleType]) -> None:
    cfg = wiring().seed_config()
    assert cfg["seed_from"] == "postgres"
    assert set(cfg["ontology_tables"]) == {
        "analysis.behavior_category",
        "analysis.detection_pattern",
        "analysis.pattern_lexicon",
    }
    assert cfg["entity_tables"] == ["analysis.entity", "analysis.entity_alias"]
    assert cfg["seal_policy"] == "skip_sealed_lexicon"  # sealed REDACTED rows never enter the graph
    assert cfg["extend_not_replace"] is True


def test_full_wiring_nests_all_three_lanes(wiring: Callable[..., ModuleType]) -> None:
    m = wiring()
    w = m.full_wiring()
    assert w["mode"] == "seed_first_hybrid"
    assert w["graph_writer"] == "graphiti"
    assert w["vector_store"] == m.vector_store_config()
    assert w["graph_store"] == m.graph_store_config()
    assert w["seed"] == m.seed_config()


# ---- secrets: referenced by NAME, never inlined ----------------------------------


def test_secrets_referenced_by_name_and_values_never_inlined(wiring: Callable[..., ModuleType]) -> None:
    m = wiring(
        MILVUS_ADDRESS="http://milvus.internal:19530",
        MILVUS_TOKEN="svc-user:MILVUS-SECRET-VALUE-9x7",
        NEO4J_PASSWORD="NEO4J-SECRET-VALUE-3q1",
        GRAPHITI_MCP_URL="http://graphiti.internal/token/GRAPHITI-SECRET-8z2",
    )
    assert m.secrets_referenced() == ["MILVUS_TOKEN", "NEO4J_PASSWORD", "GRAPHITI_MCP_URL"]

    dump = json.dumps(m.full_wiring())
    for secret in ("MILVUS-SECRET-VALUE-9x7", "NEO4J-SECRET-VALUE-3q1", "GRAPHITI-SECRET-8z2"):
        assert secret not in dump, f"secret value leaked into wiring config: {secret}"

    w = m.full_wiring()
    assert w["vector_store"]["milvus_password_env"] == "MILVUS_TOKEN"
    assert w["graph_store"]["password_env"] == "NEO4J_PASSWORD"
    assert w["graph_store"]["graphiti_mcp_url_env"] == "GRAPHITI_MCP_URL"

    # Honest pin: the USER half of MILVUS_TOKEN (and NEO4J_USER) IS embedded in
    # the config — it's an identifier, not the secret; the password half never is.
    assert w["vector_store"]["milvus_user"] == "svc-user"
