"""
Database Session
================

``get_agno_db()``  — Agno OPERATIONAL store (sessions/memory/metrics/eval/culture/traces/spans)
                     on **SurrealDB** (WS transport, /rpc, lazy-connect via agno.db.surrealdb).
``get_postgres_db()`` — Postgres for Knowledge *contents* rows and pg_duckdb / evidence work.
``create_knowledge()`` — agent Knowledge with **vectors in Milvus** (ADR-0026/0027), the
platform-wide vector substrate. pgvector remains in the PG image but is NO LONGER the
Knowledge store.

Embedder: **OpenRouter (OpenAI-compatible), SYMMETRIC models** — no query/passage modes, so
none of the NVIDIA-NIM asymmetric shim PgVector needed (which would silently degrade retrieval
on Milvus). Text = ``bge-m3`` (1024-d); code = ``codestral-embed-2505`` (1536-d). One collection
per embedder (ADR-0010); Milvus creates each collection at the embedder's dimension. The
embedder/dim is fixed at collection creation — changing it means dropping + re-creating the
collection. (NVIDIA ``NimEmbedder`` is retained in ``db/embedder.py`` as an opt-in fallback.)

Reranking: Milvus **hybrid** search fuses dense+sparse natively (RRF) — no external reranker.

Config via env:
  SurrealDB (operational): ``SURREALDB_URL`` / ``SURREALDB_USER`` / ``SURREALDB_PASS`` /
    ``SURREALDB_NS`` / ``SURREALDB_DB``.
  Milvus (vectors): ``MILVUS_ADDRESS`` / ``MILVUS_TOKEN`` (token = ``user:pass``).
  Embedder: ``OPENROUTER_API_KEY`` (+ optional ``OPENROUTER_BASE_URL``), ``EMBED_*`` overrides.
"""

from os import getenv

from agno.db.postgres import PostgresDb
from agno.db.surrealdb import SurrealDb
from agno.knowledge import Knowledge
from agno.knowledge.embedder.openai import OpenAIEmbedder
from agno.vectordb.milvus import Milvus, SearchType

from server.core.url import db_url

DB_ID = "agentos-db"

# --- SurrealDB: the Agno OPERATIONAL store (sessions/memory/metrics/eval/
# knowledge-content/culture/traces/spans). Reached from the exec tier on OVH-1 ->
# data tier on OVH-3. Default = OVH-3 tailnet IP (matches compose OVH3_HOST);
# salem private fast-path alt = ws://10.1.2.101:8000/rpc. WS transport, /rpc path.
SURREALDB_URL = getenv("SURREALDB_URL", "ws://100.119.96.29:8000/rpc")
SURREALDB_USER = getenv("SURREALDB_USER", "root")
SURREALDB_PASS = getenv("SURREALDB_PASS", "root")
SURREALDB_NS = getenv("SURREALDB_NS", "agno")
SURREALDB_DB = getenv("SURREALDB_DB", "platform")

# --- Milvus: the platform-wide vector substrate (ADR-0026/0027) --------------
# Lives on the OVH-3 data tier (relocated off the decommissioned OVH-2). Default =
# OVH-3 tailnet IP (matches compose OVH3_HOST :19530); compose passes MILVUS_ADDRESS
# at runtime so this default only fires in a bare local run. Token = user:pass.
MILVUS_URI = getenv("MILVUS_ADDRESS", "http://100.119.96.29:19530")
MILVUS_TOKEN = getenv("MILVUS_TOKEN", "root:Milvus")

# --- Embedder: OpenRouter, OpenAI-compatible, SYMMETRIC ----------------------
_OR_BASE_URL = getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
_OR_API_KEY = getenv("OPENROUTER_API_KEY", "")

# Embedding model IDs + dims (ADR-0010: one collection per embedder). Defaults are
# symmetric OpenRouter models; override via env. Dim MUST match the model's output.
EMBED_TEXT_ID = getenv("EMBED_TEXT_ID", "baai/bge-m3")
EMBED_TEXT_DIM = int(getenv("EMBED_TEXT_DIM", "1024"))
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
        api_key=_OR_API_KEY,
        base_url=_OR_BASE_URL,
        dimensions=dimensions,
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
    For plain agent persistence (sessions, memory) leave it unset.
    """
    if contents_table is not None:
        return PostgresDb(id=DB_ID, db_url=db_url, knowledge_table=contents_table)
    return PostgresDb(id=DB_ID, db_url=db_url)


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
    """Knowledge base with **vectors in Milvus** (hybrid) + contents in Postgres.

    ``use_code_embedder=True`` selects the code embedder (codestral-embed-2505, 1536-d) for
    code-artifact collections; default is the text embedder (bge-m3, 1024-d) for
    docs/transcripts/notes (ADR-0010: one collection per embedder).

    ``table_name`` is used as the **Milvus collection** name; document contents persist in
    Postgres ``{table_name}_contents``. The collection dimension is fixed at creation —
    changing the embedder requires dropping + re-creating the collection.
    """
    if use_code_embedder:
        embedder = _embedder(EMBED_CODE_ID, EMBED_CODE_DIM)
    else:
        embedder = _embedder(EMBED_TEXT_ID, EMBED_TEXT_DIM)

    return Knowledge(
        name=name,
        vector_db=Milvus(
            collection=table_name,
            uri=MILVUS_URI,
            token=MILVUS_TOKEN,
            search_type=SearchType.hybrid,
            embedder=embedder,
        ),
        contents_db=get_postgres_db(contents_table=f"{table_name}_contents"),
    )
