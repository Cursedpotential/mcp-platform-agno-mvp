"""
Database Session
================

PostgreSQL connection helpers.
``get_postgres_db()`` for agent storage backed by Postgres.
``create_knowledge()`` for agent knowledge backed by PgVector.

Embedder: NVIDIA NIM (llama-nemotron-embed-vl-1b-v2, 2048-d — multimodal text+image).
Reranker: NVIDIA NIM (nv-rerankqa-mistral-4b-v3) — verify import path in the built image.

DIMENSION CONTRACT: pgvector column dim = 2048 (llama-nemotron-embed-vl-1b-v2, verified 2026-06-07).
Changing the embedder means dropping and re-creating the vector table.
No OPENAI_API_KEY required; only NVIDIA_API_KEY.

NIM extra_body params for this embedder:
  indexing (passage): modality=["text"], input_type="passage", truncate="NONE"
  querying:           modality=["text"], input_type="query",   truncate="NONE"
Agno OpenAIEmbedder may not support extra_body — verify in image; if not, subclass or use passage mode as default.
"""

from os import getenv

from agno.db.postgres import PostgresDb
from agno.knowledge import Knowledge
from agno.vectordb.pgvector import PgVector, SearchType

from db.url import db_url

DB_ID = "agentos-db"

# NVIDIA NIM endpoints (shared by embedder and reranker)
_NVIDIA_BASE_URL = getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
_NVIDIA_API_KEY = getenv("NVIDIA_API_KEY", "")

# Embedding model IDs (ADR-0010: one collection per embedder)
EMBED_TEXT_ID = getenv("NVIDIA_EMBED_TEXT_ID", "nvidia/llama-nemotron-embed-vl-1b-v2")
EMBED_CODE_ID = getenv("NVIDIA_EMBED_CODE_ID", "nvidia/nv-embedcode-7b-v1")

# Output dimensions — verified against NIM API 2026-06-07:
# llama-nemotron-embed-vl-1b-v2: 2048-d  ✓ confirmed
# nv-embedcode-7b-v1:            4096-d  (confirm before first use)
EMBED_TEXT_DIM = int(getenv("NVIDIA_EMBED_TEXT_DIM", "2048"))
EMBED_CODE_DIM = int(getenv("NVIDIA_EMBED_CODE_DIM", "4096"))

# Rerank model — the ranking function this account can invoke
# (probed 2026-06-10: nv-rerankqa-mistral-4b-v3 not enabled for this key).
RERANK_MODEL_ID = getenv("NVIDIA_RERANK_ID", "nvidia/rerank-qa-mistral-4b")


def _nim_embedder(model_id: str, dimensions: int):
    """NVIDIA NIM embedder via OpenAI-compatible /v1/embeddings endpoint.

    NIM embedqa models are ASYMMETRIC: documents need input_type="passage",
    queries need input_type="query". NimEmbedder (db/embedder.py) carries
    PASSAGE as the default (document path) and overrides the query-path
    methods to QUERY. Fixed 2026-06-11; previously queries used passage mode
    (silent retrieval degradation).
    """
    from db.embedder import NimEmbedder
    return NimEmbedder(
        id=model_id,
        api_key=_NVIDIA_API_KEY,
        base_url=_NVIDIA_BASE_URL,
        dimensions=dimensions,
        # Default = PASSAGE for every document/index path (incl. batch).
        request_params={"extra_body": {"input_type": "passage", "truncate": "NONE"}},
    )


def _nim_reranker():
    """NVIDIA NIM reranker (nv-rerankqa-mistral-4b-v3) via the native ranking API.

    Agno's CohereReranker ignores base_url (requests leak to api.cohere.com —
    verified 2026-06-10), so we use our own NvidiaReranker (db/reranker.py)
    that posts to NIM's retrieval/ranking endpoint directly.
    Returns None on construction failure so Knowledge still boots without reranking.
    """
    try:
        from db.reranker import NvidiaReranker
        return NvidiaReranker(
            model=RERANK_MODEL_ID,
            api_key=_NVIDIA_API_KEY,
            url=getenv("NVIDIA_RERANK_URL", "https://ai.api.nvidia.com/v1/retrieval/nvidia/reranking"),
        )
    except Exception:
        # Reranker is an enhancement; fall back gracefully if not available
        return None


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


def create_knowledge(name: str, table_name: str, use_code_embedder: bool = False) -> Knowledge:
    """PgVector knowledge base with NVIDIA NIM hybrid search + reranking.

    ``use_code_embedder=True`` for code-artifact collections (nv-embedcode-7b-v1, 4096-d).
    Default is the text embedder (llama-nemotron-embed-vl-1b-v2, 2048-d) for docs/transcripts/notes.
    See ADR-0011 for the pinned embedder dimension contract.

    Vectors land in ``table_name``; document contents in ``{table_name}_contents``.
    The vector column dimension is fixed at creation — do not change the embedder
    after first boot without dropping and re-creating the table.
    """
    if use_code_embedder:
        embedder = _nim_embedder(EMBED_CODE_ID, EMBED_CODE_DIM)
    else:
        embedder = _nim_embedder(EMBED_TEXT_ID, EMBED_TEXT_DIM)

    reranker = _nim_reranker()

    vector_db_kwargs = dict(
        db_url=db_url,
        table_name=table_name,
        search_type=SearchType.hybrid,
        embedder=embedder,
    )
    if reranker is not None:
        vector_db_kwargs["reranker"] = reranker

    return Knowledge(
        name=name,
        vector_db=PgVector(**vector_db_kwargs),
        contents_db=get_postgres_db(contents_table=f"{table_name}_contents"),
    )
