# SurrealDB Integration — Design Artifact (DRAFT, do not deploy)

> _Byline: Claude Code · Opus 4.8 · 2026-06-14_

**Status:** design draft. No live source or infra touched. This file is the single
source for the change; apply by hand after review.

## Role split (locked — not re-litigated here)

| Store | Owns |
|-------|------|
| **SurrealDB** (new) | Agno **operational** layer: sessions, memory, metrics, eval runs, knowledge *content rows*, culture, traces, spans. |
| **Milvus** (unchanged) | ALL vectors / ANN. |
| **Postgres / pg_duckdb** (unchanged) | Normalized records, evidence, DuckDB analytics. Also keeps the `*_contents` Knowledge document rows (see "open questions"). |

## Verified facts from the installed source

- `agno==2.6.13` ships `agno.db.surrealdb.SurrealDb` natively. Declares the optional
  dep `surrealdb>=1.0.4` (extra `surrealdb`). The `surrealdb` package is **NOT yet
  installed** in `.venv` — it must be added.
- Constructor (`.venv/Lib/site-packages/agno/db/surrealdb/surrealdb.py`): `client`,
  `db_url`, `db_creds`, `db_ns`, `db_db`, then optional `*_table` names + `id`.
  Passing `client=None` lazily builds the connection on first use via
  `build_client(db_url, db_creds, db_ns, db_db)`.
- `build_client` (`.venv/.../agno/db/surrealdb/utils.py`):
  ```python
  client = Surreal(url=url)          # url scheme decides WS vs HTTP transport
  client.signin(creds)               # creds = {"username": .., "password": ..}
  client.use(namespace=ns, database=db)
  ```
  So: **WebSocket** transport via `ws://<host>:8000/rpc` (the `/rpc` path + `ws://`
  scheme select `BlockingWsSurrealConnection`). `db_creds` is the **root signin dict**
  `{"username": <user>, "password": <pass>}`.

---

## a) `db/session.py` change (env-driven)

Minimal, surgical: add a `get_agno_db()` factory that returns a `SurrealDb` for the
operational layer, and point the operational consumers at it. **Postgres stays** for
Knowledge document-content rows (`create_knowledge` keeps `get_postgres_db(...)` as
`contents_db`) and for the pg_duckdb / evidence work. Milvus is untouched.

### BEFORE (current top-of-file imports + factory)

```python
from os import getenv

from agno.db.postgres import PostgresDb
from agno.knowledge import Knowledge
from agno.knowledge.embedder.openai import OpenAIEmbedder
from agno.vectordb.milvus import Milvus, SearchType

from db.url import db_url

DB_ID = "agentos-db"
```

…and the consumers in `agents/*.py`, `app/main.py`, `evals/cases.py` call
`get_postgres_db()` for operational persistence.

### AFTER (add SurrealDb factory; leave Postgres + Milvus intact)

Add the import and config block near the top:

```python
from agno.db.surrealdb import SurrealDb

# --- SurrealDB: the Agno OPERATIONAL store (sessions/memory/metrics/eval/
# knowledge-content/culture/traces/spans). Reached over the salem private link
# (exec tier on OVH-1 -> data tier on OVH-3). WS transport, /rpc path. ----------
SURREALDB_URL = getenv("SURREALDB_URL", "ws://10.1.2.101:8000/rpc")
SURREALDB_USER = getenv("SURREALDB_USER", "root")
SURREALDB_PASS = getenv("SURREALDB_PASS", "root")
SURREALDB_NS = getenv("SURREALDB_NS", "agno")
SURREALDB_DB = getenv("SURREALDB_DB", "platform")
```

Add the factory (alongside `get_postgres_db`):

```python
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
```

Then update the operational consumers to call `get_agno_db()` instead of
`get_postgres_db()`:

- `app/main.py:79`            `db = get_agno_db()`
- `agents/dev_copilot.py:13`  `db=get_agno_db(),`
- `agents/analysis_orchestrator.py:13`
- `agents/forensic_data_agent.py:13`
- `agents/transcript_miner.py:13`
- `agents/ingestion_orchestrator.py:13`
- `agents/review_gatekeeper.py:13`
- `agents/project_pal.py:13`
- `evals/cases.py:26`         `eval_db = get_agno_db()`

…and export it in `db/__init__.py`:

```python
from db.session import create_knowledge, ensure_duckdb_r2_secret, get_agno_db, get_postgres_db
from db.url import db_url

__all__ = ["create_knowledge", "db_url", "ensure_duckdb_r2_secret", "get_agno_db", "get_postgres_db"]
```

**Do NOT change `create_knowledge`** — it keeps `contents_db=get_postgres_db(...)`
(Knowledge content rows stay on Postgres) and `vector_db=Milvus(...)` (vectors on
Milvus). Both are deliberately untouched.

> One-line essence: introduce `get_agno_db()` returning `SurrealDb(client=None, db_url=ws://…/rpc, db_creds={username,password}, db_ns, db_db)` and repoint the 9 operational call-sites off `get_postgres_db()`; Postgres-for-Knowledge-contents and Milvus stay as-is.

---

## b) `surrealdb` service block for `compose.data.yaml`

> The data tier in the locked decision is **OVH-3** (tailnet `100.119.96.29`, salem
> private `10.1.2.101`). The file header currently names OVH-2 — reconcile that
> comment when applying (open question below). `BIND_IP` should be set to the data
> box's tailnet/salem IP in the Coolify app env.

### Host-prep line (run on the data box BEFORE first deploy)

```bash
# SurrealDB official image runs as ROOT (uid 0) by default — chown to 0:0.
sudo mkdir -p /data/agno/volumes/surrealdb
sudo chown -R 0:0 /data/agno/volumes/surrealdb
```

### Service block (add under `services:` in compose.data.yaml)

```yaml
  # ---------------------------------------------------------------------------
  # SurrealDB — the Agno OPERATIONAL store (sessions/memory/metrics/eval/
  # knowledge-content/culture/traces/spans). Persistent rocksdb on an absolute
  # host bind. Reached by agentos-api on OVH-1 over the salem/tailnet link.
  # WS transport on /rpc; raw TCP, tailnet-only — NEVER proxied, NEVER 0.0.0.0.
  # ---------------------------------------------------------------------------
  surrealdb:
    image: surrealdb/surrealdb:v3.1.4
    platform: linux/amd64
    container_name: surrealdb
    restart: unless-stopped
    user: "0:0"                      # official image is root; matches volume chown
    command:
      - start
      - --bind=0.0.0.0:8000          # in-container bind; host exposure gated by ports below
      - --user=${SURREALDB_USER:-root}
      - --pass=${SURREALDB_PASS:-root}
      - rocksdb:/data/surreal.db     # persistent file engine inside the bind mount
    ports:
      # raw TCP, tailnet-only (reached by agentos-api on OVH-1 over salem); never proxied
      - "${BIND_IP:-127.0.0.1}:8000:8000"
    volumes:
      - /data/agno/volumes/surrealdb:/data
    healthcheck:
      # /health returns 200 when the server is up (no auth required)
      test: ["CMD-SHELL", "curl -sf http://localhost:8000/health || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 12
    # DOMAIN PHASE — SurrealDB has NO admin UI worth exposing; keep tailnet-only.
    # Deliberately NO Traefik labels (raw TCP / internal service, like neo4j bolt).
    networks:
      - agentos
```

Notes:
- `--bind=0.0.0.0:8000` is the **in-container** listen address; host exposure is
  still gated to `${BIND_IP}` by the `ports:` mapping (same pattern as agentos-db).
- `rocksdb:/data/surreal.db` => embedded RocksDB file engine, persisted on the bind
  mount. (`surrealkv://data/...` is the alternative engine; rocksdb is the proven
  default for single-node.) `surreal.db` is created as a directory by the engine.
- No named volumes — absolute host bind, per project convention.

---

## c) requirements.txt / pyproject line

Pin to the agno-declared floor; latest 1.x is compatible with `surrealdb>=1.0.4`.

`requirements.txt` (add near the `agno==2.6.13` line):

```
surrealdb>=1.0.4,<2
```

Equivalent for `pyproject.toml` `[project] dependencies` (or just enable agno's extra):

```toml
"surrealdb>=1.0.4,<2",
# or, instead of the explicit pin, pull agno's optional extra:
# "agno[surrealdb]==2.6.13",
```

> Verified version currently installed: **none** (package absent from `.venv`). Agno
> 2.6.13 metadata requires `surrealdb>=1.0.4`. Pin `>=1.0.4,<2` to stay on the
> tested major. Re-pin to the exact resolved version after `pip install`.

---

## d) env vars for agentos-api (exec tier, OVH-1) to reach SurrealDB over salem

Add to the exec-tier Coolify app env (consumed by `db/session.py`):

```bash
SURREALDB_URL=ws://10.1.2.101:8000/rpc   # data box salem private IP, /rpc, WS
SURREALDB_USER=root
SURREALDB_PASS=<root-pass>                # MUST equal data-tier SURREALDB_PASS
SURREALDB_NS=agno
SURREALDB_DB=platform
```

And on the **data tier** (compose.data.yaml app env), the matching root creds + bind:

```bash
SURREALDB_USER=root
SURREALDB_PASS=<root-pass>
BIND_IP=100.119.96.29                     # OVH-3 tailnet IP (or 10.1.2.101 salem)
```

> Transport note: use `ws://` (WebSocket on `/rpc`) — agno's `build_client` selects
> the WS connection class from this URL. If you ever front SurrealDB with TLS, switch
> to `wss://`. Do NOT use `http://...` unless you intend the blocking-HTTP transport.

---

## e) Gotchas / open questions

1. **Data-box identity mismatch.** Locked context says SurrealDB lives on **OVH-3**
   (`100.119.96.29` / salem `10.1.2.101`), but `compose.data.yaml`'s header comments
   describe **OVH-2** (`100.91.190.107`). Confirm which box, and fix `BIND_IP` /
   header before deploy. The `SURREALDB_URL` above assumes the salem IP `10.1.2.101`.
2. **`surrealdb` pip pin.** Not yet installed. Install, then re-pin to the exact
   resolved version. Confirm the installed client speaks the v3.1.4 server RPC
   (1.x clients target SurrealDB 2.x/3.x RPC — verify handshake on first connect).
3. **Server major version.** v3.1.4 is the latest stable (released 2026-06-10). If a
   client/server RPC incompatibility shows up, fall back to the latest 2.x server tag.
4. **WS vs HTTP transport.** `build_client` keys off the URL scheme only. `ws://…/rpc`
   => `BlockingWsSurrealConnection`. Long-lived WS connections can drop; agno rebuilds
   lazily via the `client` property, but confirm reconnect behavior under idle.
5. **Root auth scope.** `--user/--pass` create a **root** user. `db_creds` signs in as
   root, then `use(ns=agno, db=platform)`. Fine for a single-tenant internal service;
   tighten to a namespace/DB-scoped user later if multi-tenant.
6. **Knowledge content rows stay on Postgres.** `create_knowledge` deliberately keeps
   `contents_db=get_postgres_db(...)`. If the intent is to move ALL Agno operational
   data (incl. knowledge-content) onto SurrealDB, switch that to `get_agno_db()` too —
   but that's a larger change and is intentionally OUT of this minimal swap.
7. **Migration / data continuity.** Existing sessions/memory currently live in
   Postgres (agno tables). This swap starts SurrealDB **empty** — no migration is
   included. Decide whether historical operational data must be carried over.
8. **`rocksdb:` path form.** Using `rocksdb:/data/surreal.db` (engine creates a dir).
   Double-check the exact CLI arg form for v3.x (`rocksdb:` vs `rocksdb://`) against
   the v3.1.4 docs before deploy; the engine prefix syntax has shifted across majors.
9. **Healthcheck tool.** `curl` must exist in the image; if the surrealdb image is
   distroless, swap the healthcheck to the bundled `surreal isready` CLI or a TCP probe.
```
