"""
Database Session
================

``get_agno_db()``  — Agno OPERATIONAL store (sessions/memory/metrics/eval/culture/traces/spans)
                     on **SurrealDB** (WS transport, /rpc, lazy-connect via agno.db.surrealdb).
``get_postgres_db()`` — Postgres for Knowledge *contents* rows and pg_duckdb / evidence work.
``create_knowledge()`` — agent Knowledge vectors. CURRENT CONTRACT (ADR-0040, owner-locked
2026-07; HANDOFF-2026-07-27): **Weaviate is the platform vector store** — CUTOVER DONE
2026-07-29 (Phase-1 task 4): vectors write to data-weaviate; Milvus (ADR-0026/0027) is
SIDELINED for memsearch only and no longer referenced here. pgvector remains in the PG
image but is NOT the Knowledge store.

Embedder: **SYMMETRIC models only** — no query/passage modes (asymmetric NIM embedqa models
silently degrade retrieval; owner rule). LIVE contract since 2026-07-19: ``nvidia/nv-embed-v1``
(4096-d) for text — the live store already holds 4096-d nv-embed-v1 vectors (handoff
verified-live table). Code = ``codestral-embed-2505`` (1536-d). One collection per embedder
(ADR-0010); the embedder/dim is fixed at collection creation — changing it means dropping +
re-creating (re-embedding) the collection. (NVIDIA ``NimEmbedder`` fallback retained.)

Config via env:
  SurrealDB (operational): ``SURREALDB_URL`` / ``SURREALDB_USER`` / ``SURREALDB_PASS`` /
    ``SURREALDB_NS`` / ``SURREALDB_DB``.
  Weaviate (vectors): ``WEAVIATE_HTTP_HOST`` / ``WEAVIATE_HTTP_PORT`` / ``WEAVIATE_GRPC_PORT``
    / ``WEAVIATE_API_KEY`` (empty = anonymous until Phase-1 task 5).
  Embedder: ``OPENROUTER_API_KEY`` (+ optional ``OPENROUTER_BASE_URL``), ``EMBED_*`` overrides.
"""
# Byline: Claude Code · Fable 5 · 2026-07-31 (distinct db registry ids (agentos-admin-db / agentos-contents-db) — HANDOFF-2026-07-30 audit #1 fix)

from os import getenv

from agno.db.postgres import PostgresDb
from agno.db.surrealdb import SurrealDb
from agno.knowledge import Knowledge
from agno.knowledge.embedder.openai import OpenAIEmbedder
from agno.vectordb.search import SearchType
from agno.vectordb.weaviate import Weaviate

from server.core.url import db_url

# Distinct registry ids per backend (fix 2026-07-31, HANDOFF-2026-07-30 audit #1):
# agno's AgentOS registers dbs keyed by `db.id` (os/app.py) and its route resolver
# only detects a multi-db setup by counting registry KEYS (os/utils.py). Sharing
# one id across SurrealDb + PostgresDb merged both backends into a single bucket,
# so memory/session/knowledge routes hit whichever backend won registration —
# the root cause of the "memory/knowledge broken on first open" breakage.
DB_ID = "agentos-db"  # SurrealDb — the operational store (sessions/memory/traces)
ADMIN_DB_ID = "agentos-admin-db"  # PostgresDb — AgentOS admin plane
CONTENTS_DB_ID = "agentos-contents-db"  # PostgresDb — Knowledge contents rows

# --- SurrealDB: the Agno OPERATIONAL store (sessions/memory/metrics/eval/
# knowledge-content/culture/traces/spans). Reached from the exec tier on OVH-1 ->
# data tier on OVH-3. Default = OVH-3 tailnet IP (matches compose OVH3_HOST);
# salem private fast-path alt = ws://10.1.2.101:8000/rpc. WS transport, /rpc path.
SURREALDB_URL = getenv("SURREALDB_URL", "ws://100.119.96.29:8000/rpc")
SURREALDB_USER = getenv("SURREALDB_USER", "root")
SURREALDB_PASS = getenv("SURREALDB_PASS", "root")
SURREALDB_NS = getenv("SURREALDB_NS", "agno")
SURREALDB_DB = getenv("SURREALDB_DB", "platform")

# --- Weaviate: THE platform vector store (ADR-0040, cutover 2026-07-29) ------
# data-weaviate on the OVH-3 data tier: REST :8081 (host 8080 = coolify-proxy),
# gRPC :50051, tailnet/BIND_IP-scoped. Anonymous auth until Phase-1 task 5
# (WEAVIATE_API_KEY wired here already — empty = anonymous). agno's Weaviate
# `local=True` hardcodes connect_to_local() (localhost), so we always hand it a
# preconstructed connect_to_custom() client.
WEAVIATE_HTTP_HOST = getenv("WEAVIATE_HTTP_HOST", "100.119.96.29")
WEAVIATE_HTTP_PORT = int(getenv("WEAVIATE_HTTP_PORT", "8081"))
WEAVIATE_GRPC_PORT = int(getenv("WEAVIATE_GRPC_PORT", "50051"))
WEAVIATE_API_KEY = getenv("WEAVIATE_API_KEY", "")


def get_weaviate_client():
    """Fresh v4 client to the platform Weaviate (connect_to_custom — see above).

    skip_init_checks: the readiness probe hits gRPC health before REST is up in
    some boot orders; the lazy connect on first op surfaces real failures.
    """
    import weaviate
    from weaviate.classes.init import Auth

    return weaviate.connect_to_custom(
        http_host=WEAVIATE_HTTP_HOST,
        http_port=WEAVIATE_HTTP_PORT,
        http_secure=False,
        grpc_host=WEAVIATE_HTTP_HOST,
        grpc_port=WEAVIATE_GRPC_PORT,
        grpc_secure=False,
        auth_credentials=Auth.api_key(WEAVIATE_API_KEY) if WEAVIATE_API_KEY else None,
        skip_init_checks=True,
    )


# --- Embedder: OpenAI-compatible /embeddings, SYMMETRIC ----------------------
# Dedicated EMBED_BASE_URL / EMBED_API_KEY override the OpenRouter defaults so
# the embedding lane can move providers (e.g. NVIDIA NIM) WITHOUT touching
# OPENROUTER_API_KEY, which settings.py also reads for LLM provider selection.
_OR_BASE_URL = getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
_OR_API_KEY = getenv("OPENROUTER_API_KEY", "")
_EMBED_BASE_URL = getenv("EMBED_BASE_URL") or _OR_BASE_URL
_EMBED_API_KEY = getenv("EMBED_API_KEY") or _OR_API_KEY

# Embedding model IDs + dims (ADR-0010: one collection per embedder). Defaults match the
# LIVE platform contract (nv-embed-v1 4096-d since 2026-07-19 — handoff verified-live);
# override via env. Dim MUST match the model's output. (Old default was bge-m3/1024,
# retired: bge-m3 500ing on NIM since 2026-07-04, store re-embedded to nv-embed-v1.)
EMBED_TEXT_ID = getenv("EMBED_TEXT_ID", "nvidia/nv-embed-v1")
EMBED_TEXT_DIM = int(getenv("EMBED_TEXT_DIM", "4096"))
EMBED_CODE_ID = getenv("EMBED_CODE_ID", "mistralai/codestral-embed-2505")
EMBED_CODE_DIM = int(getenv("EMBED_CODE_DIM", "1536"))


def _embedder(model_id: str, dimensions: int) -> OpenAIEmbedder:
    """Symmetric OpenRouter embedder via the OpenAI-compatible /embeddings endpoint.

    Symmetric => the same vector space for documents and queries, so there is no
    query/passage mode to manage (unlike the NVIDIA-NIM asymmetric models, which
    required the PgVector-specific NimEmbedder shim and don't map cleanly to Milvus).
    """
    return OpenAIEmbedder(
        id=model_id,
        api_key=_EMBED_API_KEY,
        dimensions=dimensions,
        # base_url goes via client_params ON PURPOSE: agno's OpenAIEmbedder
        # injects a `dimensions` request param whenever self.base_url is set,
        # and NIM /embeddings hard-400s on extra params (extra_forbidden).
        # Symmetric models emit their native dim anyway; `dimensions` here is
        # still read by the vector store for collection schema.
        client_params={"base_url": _EMBED_BASE_URL},
    )


def ensure_duckdb_r2_secret() -> bool:
    """Idempotently (re)create the pg_duckdb S3 secret for the R2 bucket.

    Called at API startup so the secret survives a DB recreate (`down -v`) —
    the init-SQL path can't, since it doesn't substitute env and only runs on
    an empty data dir. Reads R2_* from THIS container's env. Returns True if
    the secret is in place, False if skipped (pg_duckdb absent / creds unset).
    """
    key = getenv("R2_ACCESS_KEY_ID")
    secret = getenv("R2_SECRET_ACCESS_KEY")
    account = getenv("R2_ACCOUNT_ID")
    if not (key and secret and account):
        return False
    from sqlalchemy import create_engine, text

    engine = create_engine(db_url, pool_pre_ping=True)
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "SELECT duckdb.create_simple_secret(type := 'S3', key_id := :k, "
                    "secret := :s, region := 'auto', endpoint := :e)"
                ),
                {"k": key, "s": secret, "e": f"{account}.r2.cloudflarestorage.com"},
            )
        return True
    except Exception:
        # secret already exists, or pg_duckdb not present — both non-fatal
        return False
    finally:
        engine.dispose()


def get_postgres_db(contents_table: str | None = None) -> PostgresDb:
    """Create a PostgresDb instance.

    Pass ``contents_table`` only when this database is the ``contents_db``
    of a Knowledge base — it tells agno where to persist document contents.
    Without it, the instance is the AgentOS admin-plane db.

    Each role gets its OWN registry id (never ``DB_ID``): agno's AgentOS
    resolver merges same-id dbs into one bucket, and sharing SurrealDb's id
    here made memory/session/knowledge routes resolve to a backend lottery
    (HANDOFF-2026-07-30 audit #1, confirmed live 2026-07-31).
    """
    if contents_table is not None:
        return PostgresDb(id=CONTENTS_DB_ID, db_url=db_url, knowledge_table=contents_table)
    return PostgresDb(id=ADMIN_DB_ID, db_url=db_url)


def get_agno_db() -> SurrealDb:
    """Agno operational store on SurrealDB (sessions/memory/metrics/eval/traces/
    spans/culture/knowledge-content). client=None -> agno builds the WS connection
    from db_url/db_creds/db_ns/db_db on first use (agno.db.surrealdb.utils.build_client).
    """
    return SurrealDb(
        client=None,
        db_url=SURREALDB_URL,
        db_creds={"username": SURREALDB_USER, "password": SURREALDB_PASS},
        db_ns=SURREALDB_NS,
        db_db=SURREALDB_DB,
        id=DB_ID,
    )


def create_knowledge(name: str, table_name: str, use_code_embedder: bool = False) -> Knowledge:
    """Knowledge base with **vectors in Weaviate** (hybrid BM25+vector) + contents in Postgres.

    ``use_code_embedder=True`` selects the code embedder (codestral-embed-2505, 1536-d) for
    code-artifact collections; default is the text embedder (nv-embed-v1, 4096-d) for
    docs/transcripts/notes (ADR-0010: one collection per embedder).

    ``table_name`` is used as the **Weaviate collection** name (Weaviate capitalizes the
    first letter internally — ``platform_knowledge`` is served as ``Platform_knowledge``);
    document contents persist in Postgres ``{table_name}_contents``. Weaviate stores vectors
    per-object without a declared dim, but the embedder stays a pinned contract (ADR-0010):
    mixing embedders in one collection silently corrupts retrieval — changing the embedder
    means a new collection + re-embed.
    """
    if use_code_embedder:
        embedder = _embedder(EMBED_CODE_ID, EMBED_CODE_DIM)
    else:
        embedder = _embedder(EMBED_TEXT_ID, EMBED_TEXT_DIM)

    return Knowledge(
        name=name,
        vector_db=Weaviate(
            client=get_weaviate_client(),
            collection=table_name,
            search_type=SearchType.hybrid,
            embedder=embedder,
        ),
        contents_db=get_postgres_db(contents_table=f"{table_name}_contents"),
    )
