"""
Database Session
================

``get_agno_db()``  — Agno OPERATIONAL store (sessions/memory/metrics/eval/culture/traces/spans)
                     on **PostgresDb** (ONE ``db_id="agentos-db"``; flatten executed 2026-08-04
                     per ADR-0043 decision 3). SurrealDB is parked read-only, off the critical
                     path (docstring corrected 2026-08-09 to match the code below).
``get_postgres_db()`` — Postgres for Knowledge *contents* rows and pg_duckdb / evidence work.
``create_knowledge()`` — agent Knowledge vectors. CURRENT CONTRACT (ADR-0040, owner-locked
2026-07; HANDOFF-2026-07-27): **Weaviate is the platform vector store** — CUTOVER DONE
2026-07-29 (Phase-1 task 4): vectors write to data-weaviate; Milvus (ADR-0026/0027) is
SIDELINED for memsearch only and no longer referenced here. pgvector remains in the PG
image but is NOT the Knowledge store.

Embedder: the live text contract is a symmetric model, so no query/passage modes are sent
here. (Asymmetric NIM embedqa models are NOT banned — owner correction 2026-08-07: they
require a per-call ``input_type``; this Agno client path cannot pass one, so they are
inapplicable *here* only.) LIVE contract since 2026-07-19: ``nvidia/nv-embed-v1``
(4096-d) for text — the live store already holds 4096-d nv-embed-v1 vectors (handoff
verified-live table). Code = ``codestral-embed-2505`` (1536-d). One collection per embedder
(ADR-0010); the embedder/dim is fixed at collection creation — changing it means dropping +
re-creating (re-embedding) the collection. (NVIDIA ``NimEmbedder`` fallback retained.)

Config via env:
  SurrealDB (parked read-only since 2026-08-04, legacy access only): ``SURREALDB_URL`` /
    ``SURREALDB_USER`` / ``SURREALDB_PASS`` / ``SURREALDB_NS`` / ``SURREALDB_DB``.
  Weaviate (vectors): ``WEAVIATE_HTTP_HOST`` / ``WEAVIATE_HTTP_PORT`` / ``WEAVIATE_GRPC_PORT``
    / ``WEAVIATE_API_KEY`` (empty = anonymous until Phase-1 task 5).
  Embedder: text defaults to NVIDIA NIM (``NVIDIA_BASE_URL`` / ``NVIDIA_API_KEY``); code
    defaults to OpenRouter (``OPENROUTER_API_KEY`` + optional ``OPENROUTER_BASE_URL``).
    ``EMBED_BASE_URL`` / ``EMBED_API_KEY`` override BOTH when set (2026-08-01 fix — see
    the comment above ``_EMBED_TEXT_BASE_URL`` for the live-verified incident this closes).
"""
# Byline: Claude Code · Fable 5 · 2026-07-31 (distinct db registry ids (agentos-admin-db / agentos-contents-db) — HANDOFF-2026-07-30 audit #1 fix)
# Byline: Claude Code · Sonnet (agent) · 2026-08-01 (embedder default routing fixed:
# text embedder now defaults to NVIDIA NIM, not dead OpenRouter; VerifiedWeaviate wired
# in so a dead embedder reports FAILED instead of silently reporting COMPLETED)

from os import getenv

from agno.db.postgres import PostgresDb
from agno.db.surrealdb import SurrealDb
from agno.knowledge import Knowledge
from agno.knowledge.embedder.openai import OpenAIEmbedder
from agno.vectordb.search import SearchType

from server.core.knowledge_vectordb import VerifiedWeaviate
from server.core.url import db_url

# ONE registry id, ONE backend (2026-08-04 flatten — ADR-0043 decision 3, plus
# Codex: "consolidate AgentOS operational/admin/content/learning state behind one
# PostgreSQL-backed Agno database object").
#
# History, so the reversal is understood rather than repeated: three ids existed
# because agno registers dbs keyed by `db.id` (os/app.py) and its resolver counts
# registry KEYS (os/utils.py) — sharing ONE id across a SurrealDb and a PostgresDb
# merged two different backends into one bucket and made memory/session/knowledge
# routes resolve by registration lottery (HANDOFF-2026-07-30 audit #1). Splitting
# the ids fixed that but left three registered, which armed agno's `len(dbs) > 1`
# gate: every route omitting `db_id` returned 400, papered over by
# install_db_id_default().
#
# Collapsing onto ONE PostgresDb removes the whole class of problem: one backend
# cannot lose a lottery, and one id cannot arm the multi-db gate. SurrealDB leaves
# the critical path — its 359 operational rows (200 spans, 139 traces, 17
# sessions, 3 memories, 0 users) were exported with sha256 manifests to
# _stale/surreal-export-20260804 and /data/agno/backups/ on 2026-08-04; the
# container keeps running, read-only. Nothing deleted.
DB_ID = "agentos-db"  # THE database id — one PostgresDb behind every domain
ADMIN_DB_ID = DB_ID  # retained as a readable alias; same id, same instance
CONTENTS_DB_ID = DB_ID  # Knowledge contents ride the same db (own table)

# --- SurrealDB: ~~the Agno OPERATIONAL store~~ **PARKED / READ-ONLY** since the
# 2026-08-04 flatten (ADR-0043 decision 3). Those roles (sessions/memory/metrics/
# eval/knowledge-content/culture/traces/spans) all moved to PostgresDb above.
# These settings survive ONLY to construct get_surrealdb_legacy() for a
# read-only parity check — which currently has no callers. Retirement is
# deliberately reversible and DELETION IS THE OWNER'S CALL, so neither the vars
# nor the container are removed here.
# Reached from the exec tier on OVH-1 -> data tier on OVH-3. Default = OVH-3
# tailnet IP (matches compose OVH3_HOST); salem private fast-path alt =
# ws://10.1.2.101:8000/rpc. WS transport, /rpc path.
# NOTE (owner ruling 2026-08-06): SurrealDB is RETIRED. Nothing in the platform
# uses it — get_agno_db() is Postgres, and get_surrealdb_legacy() below has ZERO
# callers. These five settings exist only so that legacy handle can still be
# constructed for a one-off read-only reconciliation against the parked
# container. That container happens to still answer on ovh-data (100.119.96.29,
# verified 2026-08-06) — the ONE host default that legitimately still points
# there, since Surreal never moved to ovh-files with the rest of the data tier.
# Do not "consistency-fix" the IP (there is no Surreal on ovh-files), and do not
# read this note as "Surreal is alive": dead dependency, parked container,
# owner-gated deletion (ADR-0043).
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
# ⚠ Default corrected 2026-08-06: ~~100.119.96.29 (ovh-data)~~ -> 100.91.190.107
# (ovh-files). The data tier migrated and `data-weaviate` on ovh-data is
# exited:unhealthy, so this default pointed at a dead host. Nothing overrode it,
# and `skip_init_checks` below means the client CONSTRUCTS fine and only fails on
# first real use — which KnowledgeHandle then swallows. Net effect: the boot log
# said "knowledge base 'legal': connected" while every vector op failed. Proven
# live from inside agentos-api, and fixed by adding WEAVIATE_HTTP_HOST to the
# exec-tier Coolify env (the env is what production actually reads; this default
# is the safety net for a fresh deploy).
WEAVIATE_HTTP_HOST = getenv("WEAVIATE_HTTP_HOST", "100.91.190.107")
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


def get_weaviate_async_client():
    """ASYNC twin of :func:`get_weaviate_client` — required, not optional.

    agno's ``Weaviate.__init__`` takes ``client=`` but has no ``async_client``
    parameter, and its ``get_async_client()`` falls back to
    ``weaviate.use_async_with_local()`` → **localhost:8080**. Since agno's
    entire ingest path is async (``ainsert`` → ``async_upsert`` →
    ``async_insert``), a sync-only custom client means every WRITE silently
    targets localhost while sync search keeps working — which is exactly how
    "knowledge never populates" presented (live 2026-08-01).

    Returned unconnected; ``VerifiedWeaviate.get_async_client()`` connects it
    lazily, mirroring the sync client's lazy-connect behavior.
    """
    import weaviate
    from weaviate.classes.init import Auth

    return weaviate.use_async_with_custom(
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
# Dedicated EMBED_BASE_URL / EMBED_API_KEY, when set, override EVERYTHING below
# for BOTH embedders — an explicit operator escape hatch that moves the whole
# embedding lane to a single provider WITHOUT touching OPENROUTER_API_KEY
# (settings.py also reads that var for LLM provider selection).
#
# Per-embedder PROVIDER DEFAULTS (bug fixed 2026-08-01 — see incident note
# below): the text embedder (``nvidia/nv-embed-v1``) is an NVIDIA NIM model;
# OpenRouter does NOT host it. The code embedder (``codestral-embed-2505``)
# IS OpenRouter-hosted. Before this fix, BOTH embedders defaulted to
# OpenRouter (settings.py's own docstring already documented text=NVIDIA,
# code=OpenRouter — session.py just didn't implement it), so every text-embed
# call with no EMBED_BASE_URL override hit OpenRouter, which 400s
# ``Model nvidia/nv-embed-v1 does not exist`` (verified live 2026-08-01) —
# and separately the configured OpenRouter key had no credits either (402 on
# an OpenRouter-native embedding model, verified same day). agno's embedder
# swallows that failure and returns (None, None) instead of raising (see
# ``agno.knowledge.embedder.openai.OpenAIEmbedder.get_embedding_and_usage``),
# so every knowledge ingest silently wrote ZERO vectors while still reporting
# ContentStatus.COMPLETED — the "COMPLETED with no vectors" bug. Direct calls
# to NVIDIA NIM (``NVIDIA_BASE_URL`` + ``NVIDIA_API_KEY``) for nv-embed-v1
# verified live 2026-08-01: HTTP 200, real 4096-d vector, matching the store's
# existing embedded rows exactly.
#
# TODO (owner decision 2026-08-01, tracked docs/DEBT.md): this hits NVIDIA NIM
# DIRECT, not through the Portkey gateway. Direct is deliberate for now —
# Portkey embeddings routing needs its own wiring pass. When that lands, this
# is a straight repoint, no new mechanism required: agno's OpenAIEmbedder
# already forwards ``client_params`` into the underlying OpenAI client
# constructor, which accepts ``default_headers`` — the exact hook Portkey's
# own `graphiti-portkeyfix` sidecar exists to work around for graphiti_core
# (which has NO such hook; agno's client DOES, so we don't need a sidecar).
# The target config already exists and is verified live: `docker/gateway/
# portkey/configs/embed.json` (NVIDIA nv-embed-v1, 4096-d, dimension-locked,
# same model/dim this module already pins) — reused as-is by Graphiti's own
# Portkey cutover (docker/gateway/portkey/README.md, "Graphiti cutover" §).
# Migration shape: point ``_EMBED_TEXT_BASE_URL`` at the Portkey gateway
# (``http://100.72.169.40:8787/v1``, ADR-0042) and pass
# ``client_params={"base_url": ..., "default_headers": {"x-portkey-config":
# json.dumps(<embed.json contents>)}}`` from ``_embedder()``. Do this only
# once Portkey's own embeddings passthrough is verified for OUR call shape
# (not just Graphiti's), since Portkey is stateless/no-DB and every route is
# a per-request header, not a stored config.
_OR_BASE_URL = getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
_OR_API_KEY = getenv("OPENROUTER_API_KEY", "")
_NVIDIA_BASE_URL = getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
_NVIDIA_API_KEY = getenv("NVIDIA_API_KEY", "")

# Text embedder (nv-embed-v1): NVIDIA NIM by default.
_EMBED_TEXT_BASE_URL = getenv("EMBED_BASE_URL") or _NVIDIA_BASE_URL
_EMBED_TEXT_API_KEY = getenv("EMBED_API_KEY") or _NVIDIA_API_KEY

# Code embedder (codestral-embed-2505): OpenRouter by default (unchanged).
_EMBED_CODE_BASE_URL = getenv("EMBED_BASE_URL") or _OR_BASE_URL
_EMBED_CODE_API_KEY = getenv("EMBED_API_KEY") or _OR_API_KEY

# Embedding model IDs + dims (ADR-0010: one collection per embedder). Defaults match the
# LIVE platform contract (nv-embed-v1 4096-d since 2026-07-19 — handoff verified-live);
# override via env. Dim MUST match the model's output. (Old default was bge-m3/1024,
# retired: bge-m3 500ing on NIM since 2026-07-04, store re-embedded to nv-embed-v1.)
EMBED_TEXT_ID = getenv("EMBED_TEXT_ID", "nvidia/nv-embed-v1")
EMBED_TEXT_DIM = int(getenv("EMBED_TEXT_DIM", "4096"))
EMBED_CODE_ID = getenv("EMBED_CODE_ID", "mistralai/codestral-embed-2505")
EMBED_CODE_DIM = int(getenv("EMBED_CODE_DIM", "1536"))


def _embedder(model_id: str, dimensions: int, base_url: str, api_key: str) -> OpenAIEmbedder:
    """Symmetric embedder via an OpenAI-compatible /embeddings endpoint.

    Symmetric => the same vector space for documents and queries, so there is no
    query/passage mode to manage (unlike the NVIDIA-NIM asymmetric models, which
    required the PgVector-specific NimEmbedder shim and don't map cleanly to Milvus).

    ``base_url``/``api_key`` are caller-supplied (not read from module globals here)
    so the text and code embedders can each get their own provider default — see the
    module-level comment above ``_EMBED_TEXT_BASE_URL``/``_EMBED_CODE_BASE_URL``.
    """
    return OpenAIEmbedder(
        id=model_id,
        api_key=api_key,
        dimensions=dimensions,
        # base_url goes via client_params ON PURPOSE: agno's OpenAIEmbedder
        # injects a `dimensions` request param whenever self.base_url is set,
        # and NIM /embeddings hard-400s on extra params (extra_forbidden).
        # Symmetric models emit their native dim anyway; `dimensions` here is
        # still read by the vector store for collection schema.
        client_params={"base_url": base_url},
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


# The knowledge-contents table the single db instance is built with. Matches
# create_knowledge("platform", "platform_knowledge") -> "<table>_contents".
_CONTENTS_TABLE = "platform_knowledge_contents"
_PG_DB: PostgresDb | None = None


def get_postgres_db(contents_table: str | None = None) -> PostgresDb:
    """THE database. ONE PostgresDb instance behind every AgentOS domain.

    Returns the same object every call — a genuine singleton, not merely a
    shared id. Both matter: sharing an id across two *distinct* PostgresDb
    objects (one carrying ``knowledge_table``, one not) makes agno log
    "multiple distinct databases share id ...; keeping the first" and silently
    drop one, which is the same shadowing hazard the old three-id split
    existed to avoid. One object cannot shadow itself.

    ``contents_table`` is accepted for call-site compatibility. The singleton
    is already built with the platform contents table; a request for a
    DIFFERENT table is logged rather than silently ignored, because it would
    mean a second knowledge base needs its own db instance and id — a real
    decision, not something to paper over.
    """
    global _PG_DB
    if _PG_DB is None:
        _PG_DB = PostgresDb(id=DB_ID, db_url=db_url, knowledge_table=_CONTENTS_TABLE)
    if contents_table is not None and contents_table != _CONTENTS_TABLE:
        from agno.utils.log import log_warning

        log_warning(
            f"get_postgres_db(contents_table={contents_table!r}) but the single "
            f"db instance is built with {_CONTENTS_TABLE!r}. Returning the "
            "singleton; a second knowledge base needs its own db id (see the "
            "2026-08-04 flatten note above)."
        )
    return _PG_DB


def get_agno_db() -> PostgresDb:
    """Agno operational store — sessions/memory/metrics/eval/traces/spans.

    Postgres since the 2026-08-04 flatten (ADR-0043 decision 3). Was SurrealDb,
    which is now off the critical path: its learning methods raise
    NotImplementedError (silently swallowed, the long-standing memory-lane
    no-op), and keeping a second backend registered bought nothing but the
    db_id gate. ``get_surrealdb_legacy()`` below still constructs the old
    handle for read-only reconciliation — it is not wired into AgentOS.
    """
    return get_postgres_db()


def get_surrealdb_legacy() -> SurrealDb:
    """The retired SurrealDb handle, kept for read-only reconciliation only.

    NOT registered with AgentOS. The 2026-08-04 export
    (_stale/surreal-export-20260804, sha256-manifested) is the durable copy;
    this exists so a future parity check can query the live container without
    resurrecting it as a dependency. Deleting SurrealDB is an owner decision.
    """
    return SurrealDb(
        client=None,
        db_url=SURREALDB_URL,
        db_creds={"username": SURREALDB_USER, "password": SURREALDB_PASS},
        db_ns=SURREALDB_NS,
        db_db=SURREALDB_DB,
        id="agentos-surreal-legacy",
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
        embedder = _embedder(EMBED_CODE_ID, EMBED_CODE_DIM, _EMBED_CODE_BASE_URL, _EMBED_CODE_API_KEY)
    else:
        embedder = _embedder(EMBED_TEXT_ID, EMBED_TEXT_DIM, _EMBED_TEXT_BASE_URL, _EMBED_TEXT_API_KEY)

    return Knowledge(
        name=name,
        # VerifiedWeaviate (not the raw agno Weaviate class): agno's Weaviate
        # silently skips documents whose embedding is None and still reports
        # the content row COMPLETED (see server/core/knowledge_vectordb.py's
        # docstring for the full trace) — VerifiedWeaviate raises instead when
        # an ENTIRE batch failed to embed, so a dead/misconfigured embedder
        # correctly surfaces as ContentStatus.FAILED.
        vector_db=VerifiedWeaviate(
            client=get_weaviate_client(),
            # agno has NO `async_client` constructor param, and its
            # get_async_client() falls back to use_async_with_local()
            # (localhost:8080). The INGEST path is fully async, so without this
            # every write failed against localhost while sync search worked —
            # the real cause of "knowledge never populates". See
            # VerifiedWeaviate.get_async_client().
            async_client_factory=get_weaviate_async_client,
            collection=table_name,
            search_type=SearchType.hybrid,
            embedder=embedder,
        ),
        contents_db=get_postgres_db(contents_table=f"{table_name}_contents"),
    )
