"""Tests for evidence/milvus_forensic.py — forensic Milvus collection specs (define-only).

The load-bearing contracts: three forensic_* collections, each with exactly one
auto-id primary key and a dense vector dim-locked to EMBED_TEXT_DIM (bge-m3
1024-d); the court-safety gate fields present on EVERY collection; the sparse
BM25 hybrid lane appearing only under FORENSIC_MILVUS_HYBRID (flags are read at
import time, so env-sensitive tests reload the module); dry_run plans never
touching a client; and the GATED create path being unreachable without an
explicit client and refusing to run over validation errors.
"""

from __future__ import annotations

import importlib
from types import ModuleType
from typing import Any, Callable, Iterator, NoReturn

import pytest

import server.analysis.milvus_forensic as mf
import server.analysis.semantica_wiring as sw
from server.analysis.milvus_forensic import BM25Function, CollectionSpec, FieldSpec

COLLECTION_NAMES = ["forensic_records", "forensic_findings", "forensic_patterns"]

# The court-safety scalar gates every collection must carry (mirrors the
# Postgres pattern_finding / normalized_record gates — agents filter on these).
GATE_FIELDS = {
    "review_status",
    "safe_for_legal_use",
    "requires_human_review",
    "bias_caution",
    "sensitivity_tier",
    "data_tier",
}

_ENV_VARS = (
    "FORENSIC_MILVUS_HYBRID",
    "FORENSIC_MILVUS_METRIC",
    "EMBED_TEXT_DIM",
    "MILVUS_ADDRESS",
    "MILVUS_TOKEN",
)


@pytest.fixture
def reload_forensic(monkeypatch: pytest.MonkeyPatch) -> Iterator[Callable[..., ModuleType]]:
    """Reload evidence.milvus_forensic under a controlled env.

    The module reads its flags (ENABLE_SPARSE_BM25, METRIC_TYPE, dims) at import
    time, so exercising the env-driven branches requires a reload. Teardown
    restores the original env and reloads both this module and semantica_wiring
    (which copies its constants at import) so no state leaks across tests.
    """

    def load(**env: str) -> ModuleType:
        for var in _ENV_VARS:
            monkeypatch.delenv(var, raising=False)
        for key, val in env.items():
            monkeypatch.setenv(key, val)
        return importlib.reload(mf)

    yield load
    monkeypatch.undo()
    importlib.reload(mf)
    importlib.reload(sw)


# ---- spec table + validation ---------------------------------------------------


def test_all_specs_three_collections_all_valid() -> None:
    specs = mf.all_specs()
    assert [s.name for s in specs] == COLLECTION_NAMES
    for s in specs:
        assert s.validate() == [], f"{s.name}: {s.validate()}"


def test_every_spec_one_autoid_pk_and_dim_locked_dense() -> None:
    for s in mf.all_specs():
        pks = [f for f in s.fields if f.is_primary]
        assert len(pks) == 1, f"{s.name}: exactly one primary key"
        assert pks[0].name == "pk" and pks[0].dtype == "int64" and pks[0].auto_id

        dense = [f for f in s.fields if f.dtype == "float_vector"]
        assert len(dense) == 1 and dense[0].name == "dense"
        assert dense[0].dim == mf.EMBED_TEXT_DIM  # dim-locked to bge-m3

        # Milvus hard requirements the offline v() check enforces
        assert all(f.max_length for f in s.fields if f.dtype == "varchar")
        names = [f.name for f in s.fields]
        assert len(names) == len(set(names)), f"{s.name}: duplicate field names"


def test_court_safety_gate_fields_on_every_collection() -> None:
    for s in mf.all_specs():
        by_name = {f.name: f for f in s.fields}
        missing = GATE_FIELDS - set(by_name)
        assert not missing, f"{s.name} missing gate fields: {missing}"
        for flag in ("safe_for_legal_use", "requires_human_review", "bias_caution"):
            assert by_name[flag].dtype == "bool"
        for tier in ("review_status", "sensitivity_tier", "data_tier"):
            assert by_name[tier].dtype == "varchar" and by_name[tier].max_length


def test_validate_catches_broken_specs() -> None:
    pk = FieldSpec("pk", "int64", is_primary=True)

    def errs(fields: list[FieldSpec], functions: list[BM25Function] | None = None) -> list[str]:
        return CollectionSpec(name="broken", description="", fields=fields, functions=functions or []).validate()

    assert any("exactly one primary" in e for e in errs([FieldSpec("a", "int64")]))
    assert any("exactly one primary" in e for e in errs([pk, FieldSpec("b", "int64", is_primary=True)]))
    assert any("needs dim" in e for e in errs([pk, FieldSpec("dense", "float_vector")]))
    assert any("needs max_length" in e for e in errs([pk, FieldSpec("t", "varchar")]))
    assert any("duplicate field names" in e for e in errs([pk, FieldSpec("x", "int64"), FieldSpec("x", "int64")]))
    assert any(
        "references missing field" in e
        for e in errs([pk, FieldSpec("text", "varchar", max_length=8)], [BM25Function("f", "text", "sparse")])
    )


# ---- env-driven branches: dense-only default vs hybrid BM25 --------------------


def test_default_env_is_dense_only(reload_forensic: Callable[..., ModuleType]) -> None:
    m = reload_forensic()
    assert m.ENABLE_SPARSE_BM25 is False
    assert m.EMBED_TEXT_DIM == 1024 and m.METRIC_TYPE == "COSINE"
    for s in m.all_specs():
        assert all(f.dtype != "sparse_vector" for f in s.fields)
        assert s.functions == []
        assert next(f for f in s.fields if f.name == "text").enable_analyzer is False
    assert m.index_params_plan() == {"dense": {"index_type": "AUTOINDEX", "metric_type": "COSINE"}}


@pytest.mark.parametrize("flag", ["1", "true", "YES", "on"])
def test_hybrid_flag_adds_sparse_bm25_lane(reload_forensic: Callable[..., ModuleType], flag: str) -> None:
    m = reload_forensic(FORENSIC_MILVUS_HYBRID=flag)
    assert m.ENABLE_SPARSE_BM25 is True
    for s in m.all_specs():
        assert s.validate() == []
        assert any(f.dtype == "sparse_vector" and f.name == "sparse" for f in s.fields)
        assert next(f for f in s.fields if f.name == "text").enable_analyzer is True
        assert [(fn.name, fn.input_field, fn.output_field) for fn in s.functions] == [("text_bm25", "text", "sparse")]
    plan = m.index_params_plan()
    assert plan["dense"] == {"index_type": "AUTOINDEX", "metric_type": "COSINE"}
    assert plan["sparse"] == {"index_type": "SPARSE_INVERTED_INDEX", "metric_type": "BM25"}


def test_metric_env_flows_into_index_plan(reload_forensic: Callable[..., ModuleType]) -> None:
    m = reload_forensic(FORENSIC_MILVUS_METRIC="IP")
    assert m.index_params_plan()["dense"]["metric_type"] == "IP"


# ---- create_forensic_collections: plan vs GATED path ---------------------------


def test_dry_run_plan_without_client() -> None:
    plan = mf.create_forensic_collections(client=None, dry_run=True)
    assert plan["dry_run"] is True and plan["created"] == []
    assert plan["validation_errors"] == []
    assert "DRY-RUN" in plan["note"]
    assert [c["name"] for c in plan["collections"]] == COLLECTION_NAMES
    for c in plan["collections"]:
        assert c["vector_dim"] == mf.EMBED_TEXT_DIM
        assert GATE_FIELDS <= set(c["fields"])
    assert plan["index_params"]["dense"]["index_type"] == "AUTOINDEX"
    assert plan["text_dim"] == mf.EMBED_TEXT_DIM


def test_dry_run_false_without_client_refuses_loudly() -> None:
    # The GATED prod-infra write must be impossible to reach by accident:
    # dry_run=False with no client is a caller error, not a silent plan.
    with pytest.raises(ValueError, match="requires a MilvusClient"):
        mf.create_forensic_collections(client=None, dry_run=False)


class _ExistingOnlyClient:
    """Fake MilvusClient where every collection already exists.

    The gated path must be idempotent: probe has_collection and never call any
    create/index method for existing collections.
    """

    def __init__(self) -> None:
        self.checked: list[str] = []

    def has_collection(self, name: str) -> bool:
        self.checked.append(name)
        return True

    def create_collection(self, **kwargs: Any) -> NoReturn:
        raise AssertionError("must not create an existing collection")

    def prepare_index_params(self) -> NoReturn:
        raise AssertionError("must not index an existing collection")

    def create_index(self, **kwargs: Any) -> NoReturn:
        raise AssertionError("must not index an existing collection")


def test_gated_path_is_idempotent_over_existing_collections() -> None:
    client = _ExistingOnlyClient()
    plan = mf.create_forensic_collections(client=client, dry_run=False)
    assert plan["created"] == []
    assert client.checked == COLLECTION_NAMES


def test_gated_path_refuses_validation_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    broken = CollectionSpec(
        name="broken",
        description="deliberately invalid",
        fields=[FieldSpec("pk", "int64", is_primary=True), FieldSpec("t", "varchar")],  # varchar w/o max_length
    )
    monkeypatch.setattr(mf, "all_specs", lambda: [broken])

    # dry-run surfaces the errors in the plan instead of raising
    plan = mf.create_forensic_collections(client=None, dry_run=True)
    assert any("needs max_length" in e for e in plan["validation_errors"])

    # the real-create path refuses outright
    with pytest.raises(ValueError, match="refusing to create"):
        mf.create_forensic_collections(client=_ExistingOnlyClient(), dry_run=False)


# ---- lazy pymilvus conversion ---------------------------------------------------


def test_to_pymilvus_schema_maps_specs_faithfully() -> None:
    # pymilvus is an optional heavy dep — skip cleanly when it isn't installed.
    pymilvus = pytest.importorskip("pymilvus")

    for spec in mf.all_specs():
        schema = mf.to_pymilvus_schema(spec)
        assert isinstance(schema, pymilvus.CollectionSchema)
        by_name = {f.name: f for f in schema.fields}
        assert set(by_name) == {f.name for f in spec.fields}
        assert by_name["pk"].is_primary and by_name["pk"].auto_id
        assert by_name["dense"].dtype == pymilvus.DataType.FLOAT_VECTOR
        assert by_name["dense"].params["dim"] == mf.EMBED_TEXT_DIM
        assert by_name["review_status"].params["max_length"] == 32
        assert schema.enable_dynamic_field is True
