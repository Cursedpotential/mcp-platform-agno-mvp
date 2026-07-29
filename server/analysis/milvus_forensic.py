"""
evidence/milvus_forensic.py — FORENSIC Milvus collection schema DEFINITIONS.

*** SIDELINED (ADR-0040, owner-locked 2026-07; HANDOFF-2026-07-27): Milvus is no
longer the platform vector store — Weaviate is. Milvus stays up for memsearch
ONLY, with NO new platform writers. These schema definitions are retained for
the legacy lane and the Milvus->Weaviate export (handoff Phase-1 task 3); new
vector work goes through Weaviate (see server/analysis/semantica_wiring.py). ***

DEFINE-ONLY. This module declares the forensic vector collections as a
dependency-free field-spec SSOT (plain dataclasses) plus a lazy converter to
real pymilvus objects. It DOES NOT create anything on the server by default —
`create_forensic_collections()` returns a PLAN unless dry_run=False (which is
HITL/APPROVALS-gated: creating collections on the live Milvus is a prod-infra
write). The field-spec table can be validated offline with no pymilvus install.

Contract (source of truth = server/core/session.py, ADR-0010/0026/0027; embedder
contract revised — LIVE is nv-embed-v1 4096-d since 2026-07-19):
  * Contents/relational live in Postgres; legacy vectors in Milvus (sidelined).
  * ONE collection per embedder, dimension fixed at creation.
  * Text embedder -> EMBED_TEXT_DIM (nv-embed-v1 4096-d; bge-m3 1024-d retired).
  * Milvus at MILVUS_ADDRESS (default tailnet 100.119.96.29:19530),
    token MILVUS_TOKEN (user:pass, default root:Milvus). Metric = COSINE.
  * Hybrid dense+sparse (BM25 RRF) is the platform default; the sparse lane is
    added when ENABLE_SPARSE_BM25 is set (Milvus 2.5+ BM25 Function).

These forensic collections are the analysis/vector lane of the forensic-DB and
are DISTINCT from SORT's `casebible_ai_conversations` and PROCESS's
`casebible_evidence` (ownership boundary preserved — PIPELINE owns forensic_*).

Court-safety: every collection carries the scalar gate fields
(safe_for_legal_use / review_status / requires_human_review / bias_caution /
sensitivity_tier) so agents filter to review-approved, non-sealed vectors —
the same gates the Postgres pattern_finding / normalized_record enforce.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from os import getenv
from typing import Any, Optional

# --- dimension + connection contract (mirrors db/session.py) -----------------
EMBED_TEXT_DIM = int(getenv("EMBED_TEXT_DIM", "1024"))  # bge-m3
MILVUS_URI = getenv("MILVUS_ADDRESS", "http://100.119.96.29:19530")
MILVUS_TOKEN = getenv("MILVUS_TOKEN", "root:Milvus")
METRIC_TYPE = getenv("FORENSIC_MILVUS_METRIC", "COSINE")
ENABLE_SPARSE_BM25 = getenv("FORENSIC_MILVUS_HYBRID", "0").lower() in ("1", "true", "yes", "on")

# Milvus scalar field length caps
_ID_LEN = 64  # uuid text
_SHORT = 128
_TIER = 32
_TEXT_MAX = 8192  # matched_text/content snippet stored for BM25 + display


@dataclass(frozen=True)
class FieldSpec:
    name: str
    dtype: str  # 'int64'|'varchar'|'bool'|'float_vector'|'sparse_vector'|'json'|'double'
    is_primary: bool = False
    auto_id: bool = False
    dim: Optional[int] = None  # float_vector only
    max_length: Optional[int] = None  # varchar only
    enable_analyzer: bool = False  # varchar feeding BM25
    desc: str = ""


@dataclass(frozen=True)
class BM25Function:
    name: str
    input_field: str
    output_field: str


@dataclass(frozen=True)
class CollectionSpec:
    name: str
    description: str
    fields: list[FieldSpec]
    functions: list[BM25Function] = field(default_factory=list)
    enable_dynamic_field: bool = True

    # --- validation (offline, no pymilvus) -----------------------------------
    def validate(self) -> list[str]:
        errs: list[str] = []
        pks = [f for f in self.fields if f.is_primary]
        if len(pks) != 1:
            errs.append(f"{self.name}: exactly one primary key required, found {len(pks)}")
        v(self.name, errs, self.fields)
        names = [f.name for f in self.fields]
        if len(names) != len(set(names)):
            errs.append(f"{self.name}: duplicate field names")
        for fn in self.functions:
            if fn.input_field not in names or fn.output_field not in names:
                errs.append(f"{self.name}: BM25 function {fn.name} references missing field")
        return errs


def v(cname: str, errs: list[str], fields: list[FieldSpec]) -> None:
    for f in fields:
        if f.dtype == "float_vector" and not f.dim:
            errs.append(f"{cname}.{f.name}: float_vector needs dim")
        if f.dtype == "varchar" and not f.max_length:
            errs.append(f"{cname}.{f.name}: varchar needs max_length")


# --- shared court-safety scalar gate fields ----------------------------------
def _gate_fields() -> list[FieldSpec]:
    return [
        FieldSpec("review_status", "varchar", max_length=_TIER, desc="review_state enum text"),
        FieldSpec("safe_for_legal_use", "bool", desc="legal-gate; agents filter to true only for exhibits"),
        FieldSpec("requires_human_review", "bool"),
        FieldSpec("bias_caution", "bool", desc="hypothesis-not-conclusion flag"),
        FieldSpec("sensitivity_tier", "varchar", max_length=_TIER, desc="public|restricted|sealed"),
        FieldSpec("data_tier", "varchar", max_length=_TIER, desc="evidence_tier enum text"),
    ]


def _dense_and_text(text_desc: str) -> list[FieldSpec]:
    out = [
        FieldSpec("text", "varchar", max_length=_TEXT_MAX, enable_analyzer=ENABLE_SPARSE_BM25, desc=text_desc),
        FieldSpec("dense", "float_vector", dim=EMBED_TEXT_DIM, desc="bge-m3 1024-d embedding"),
    ]
    if ENABLE_SPARSE_BM25:
        out.append(FieldSpec("sparse", "sparse_vector", desc="BM25 sparse lane (hybrid RRF)"))
    return out


def _bm25() -> list[BM25Function]:
    return [BM25Function("text_bm25", "text", "sparse")] if ENABLE_SPARSE_BM25 else []


# --- the forensic collections ------------------------------------------------
def forensic_records_spec() -> CollectionSpec:
    """Semantic index over analysis.normalized_record content — powers evidence
    retrieval + the detection runner's semantic_similarity / priority_screener
    detection methods (complementing literal/regex)."""
    return CollectionSpec(
        name="forensic_records",
        description="normalized_record semantic index (message/transcript/ocr text)",
        fields=[
            FieldSpec("pk", "int64", is_primary=True, auto_id=True),
            FieldSpec("record_id", "varchar", max_length=_ID_LEN, desc="analysis.normalized_record.id (uuid)"),
            FieldSpec("subject_type", "varchar", max_length=_TIER),
            FieldSpec("conversation_id", "varchar", max_length=_SHORT),
            FieldSpec("source", "varchar", max_length=_SHORT),
            FieldSpec("occurred_at", "int64", desc="epoch seconds; 0 if unknown"),
            *_dense_and_text("normalized_record.content snippet"),
            *_gate_fields(),
        ],
        functions=_bm25(),
    )


def forensic_findings_spec() -> CollectionSpec:
    """Semantic index over analysis.pattern_finding matched_text+context — lets
    agents cluster/retrieve behavioral findings while honoring the legal gate."""
    return CollectionSpec(
        name="forensic_findings",
        description="pattern_finding semantic index (matched text + context)",
        fields=[
            FieldSpec("pk", "int64", is_primary=True, auto_id=True),
            FieldSpec("finding_id", "varchar", max_length=_ID_LEN),
            FieldSpec("subject_id", "varchar", max_length=_ID_LEN, desc="normalized_record.id"),
            FieldSpec("category_id", "varchar", max_length=_SHORT),
            FieldSpec("polarity", "varchar", max_length=_TIER),
            FieldSpec("detection_method", "varchar", max_length=_TIER),
            FieldSpec("severity", "int64"),
            *_dense_and_text("matched_text + context_before/after"),
            *_gate_fields(),
        ],
        functions=_bm25(),
    )


def forensic_patterns_spec() -> CollectionSpec:
    """Semantic index over analysis.detection_pattern description+keywords — the
    seed for semantic (embedding-similarity) screening beyond literal/regex."""
    return CollectionSpec(
        name="forensic_patterns",
        description="detection_pattern semantic index (description + keywords)",
        fields=[
            FieldSpec("pk", "int64", is_primary=True, auto_id=True),
            FieldSpec("pattern_id", "varchar", max_length=_ID_LEN),
            FieldSpec("category_id", "varchar", max_length=_SHORT),
            FieldSpec("match_type", "varchar", max_length=_TIER),
            FieldSpec("severity", "int64"),
            *_dense_and_text("detection_pattern.description + keywords"),
            *_gate_fields(),
        ],
        functions=_bm25(),
    )


def all_specs() -> list[CollectionSpec]:
    return [forensic_records_spec(), forensic_findings_spec(), forensic_patterns_spec()]


# --- index params ------------------------------------------------------------
def index_params_plan() -> dict[str, Any]:
    """AUTOINDEX keeps us version-robust; Milvus picks HNSW/IVF under the hood.
    Sparse (when hybrid) uses SPARSE_INVERTED_INDEX + BM25 metric."""
    plan = {"dense": {"index_type": "AUTOINDEX", "metric_type": METRIC_TYPE}}
    if ENABLE_SPARSE_BM25:
        plan["sparse"] = {"index_type": "SPARSE_INVERTED_INDEX", "metric_type": "BM25"}
    return plan


# --- lazy pymilvus conversion (only when actually creating) ------------------
def to_pymilvus_schema(spec: CollectionSpec):
    """Build a real pymilvus CollectionSchema. Imported lazily so the specs stay
    usable/validatable without pymilvus installed."""
    from pymilvus import CollectionSchema, DataType, FieldSchema, Function, FunctionType

    _DT = {
        "int64": DataType.INT64,
        "varchar": DataType.VARCHAR,
        "bool": DataType.BOOL,
        "double": DataType.DOUBLE,
        "json": DataType.JSON,
        "float_vector": DataType.FLOAT_VECTOR,
        "sparse_vector": DataType.SPARSE_FLOAT_VECTOR,
    }
    fields = []
    for f in spec.fields:
        kw: dict[str, Any] = {"name": f.name, "dtype": _DT[f.dtype]}
        if f.is_primary:
            kw["is_primary"] = True
            kw["auto_id"] = f.auto_id
        if f.dim:
            kw["dim"] = f.dim
        if f.max_length:
            kw["max_length"] = f.max_length
        if f.enable_analyzer:
            kw["enable_analyzer"] = True
        fields.append(FieldSchema(**kw))
    functions = [
        Function(
            name=fn.name,
            function_type=FunctionType.BM25,
            input_field_names=[fn.input_field],
            output_field_names=[fn.output_field],
        )
        for fn in spec.functions
    ]
    return CollectionSchema(
        fields=fields,
        description=spec.description,
        enable_dynamic_field=spec.enable_dynamic_field,
        functions=functions or None,
    )


def create_forensic_collections(client=None, dry_run: bool = True) -> dict[str, Any]:
    """PLAN (dry_run=True, default) or CREATE (dry_run=False — GATED prod-infra
    write; do not call unattended). Returns a plan/result dict.

    dry_run: validates every spec offline and returns the create plan WITHOUT
    touching Milvus. Passing a pymilvus MilvusClient with dry_run=False issues
    create_collection + create_index for any missing collection (idempotent:
    skips existing collections).
    """
    specs = all_specs()
    errs: list[str] = []
    for s in specs:
        errs.extend(s.validate())
    plan: dict[str, Any] = {
        "milvus_uri": MILVUS_URI,
        "metric": METRIC_TYPE,
        "hybrid_sparse_bm25": ENABLE_SPARSE_BM25,
        "text_dim": EMBED_TEXT_DIM,
        "collections": [
            {
                "name": s.name,
                "fields": [f.name for f in s.fields],
                "vector_dim": EMBED_TEXT_DIM,
                "functions": [fn.name for fn in s.functions],
            }
            for s in specs
        ],
        "index_params": index_params_plan(),
        "validation_errors": errs,
        "dry_run": dry_run,
        "created": [],
    }
    if not dry_run and client is None:
        raise ValueError("create_forensic_collections: dry_run=False requires a MilvusClient (GATED prod-infra write)")
    if dry_run:
        plan["note"] = "DRY-RUN — no server contact. Pass a MilvusClient + dry_run=False to create (GATED)."
        return plan
    if errs:
        raise ValueError(f"refusing to create with validation errors: {errs}")
    # GATED path — real creation
    for s in specs:
        if client.has_collection(s.name):
            continue
        schema = to_pymilvus_schema(s)
        client.create_collection(collection_name=s.name, schema=schema)
        ip = client.prepare_index_params()
        ip.add_index(field_name="dense", index_type="AUTOINDEX", metric_type=METRIC_TYPE)
        if ENABLE_SPARSE_BM25:
            ip.add_index(field_name="sparse", index_type="SPARSE_INVERTED_INDEX", metric_type="BM25")
        client.create_index(collection_name=s.name, index_params=ip)
        plan["created"].append(s.name)
    return plan


if __name__ == "__main__":  # pragma: no cover
    import json

    print(json.dumps(create_forensic_collections(dry_run=True), indent=2))
