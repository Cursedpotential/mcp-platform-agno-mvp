# Plan — Agno MVP: Boot + Transcript Context Ingestion

## Approach

Work the unblocking sequence bottom-up: DB → compose → providers → LearningMachine → main.py → ingestion. Each step is self-contained and verifiable before the next begins. All work is in `Agno-MCP-Platform/` (the active repo). All verification runs **inside the container** via `docker exec` — never on the host.

The critical execution docs are:
- `docs/planning/EXECUTION_PLAN.md` — verified Agno imports, anti-pattern table, phase patterns
- `docs/planning/VERIFIED_AGNO_API.md` — confirmed imports to re-verify against pinned image
- `agents/factory.py` — already the reference implementation; do NOT rewrite it

---

## Step 1 — SQL Migrations

**Files to create:** `sql/0001_init_extensions.sql`, `sql/0002_schema.sql`

**Files to modify:** `compose.yaml` (add init-SQL volume mounts to agentos-db)

### `sql/0001_init_extensions.sql`
```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS btree_gin;
CREATE EXTENSION IF NOT EXISTS btree_gist;
CREATE EXTENSION IF NOT EXISTS unaccent;
-- uuidv7() is native on PG18 — no extension needed.
-- pg_textsearch is in the image but NOT enabled here (add when BM25 needed).
```

### `sql/0002_schema.sql` — key decisions:
- PKs: `DEFAULT uuidv7()` — PG18 native, timestamp-ordered
- `CREATE SCHEMA IF NOT EXISTS evidence;` — read-only by agents
- `CREATE SCHEMA IF NOT EXISTS analysis;` — derived artifacts, approval-gated writes
- `agent_run` + `approval_request` tables: **add `run_id UUID` column** for native-confirm resume
- `evidence_hash`: `digest BYTEA NOT NULL, CHECK (algo <> 'sha256' OR octet_length(digest) = 32)`
- `transcript_insight`: stores ChatMiner mining output
- **NO `learned_knowledge` table** — LearningMachine owns this

### Mount in compose.yaml
```yaml
  agentos-db:
    image: agnohq/pgvector:18
    volumes:
      - pgdata:/var/lib/postgresql
      - ./sql/0001_init_extensions.sql:/docker-entrypoint-initdb.d/01_extensions.sql:ro
      - ./sql/0002_schema.sql:/docker-entrypoint-initdb.d/02_schema.sql:ro
```

**Verify:**
```bash
docker compose down -v && docker compose up -d agentos-db
docker exec agentos-db psql -U ai -d ai -c "\dx"        # extensions listed
docker exec agentos-db psql -U ai -d ai -c "\dt"        # agent_run, approval_request, evidence_hash, transcript_insight
docker exec agentos-db psql -U ai -d ai -c "SELECT uuidv7();"  # returns a UUID
docker exec agentos-db psql -U ai -d ai -c "SET default_transaction_read_only=on; INSERT INTO evidence.evidence_hash(source_ref,algo,digest) VALUES('test','sha256',decode('aa','hex'));"  # must FAIL
```

---

## Step 2 — compose.yaml: Add n8n + R2, Remove --reload

**File to modify:** `compose.yaml`

Three changes:
1. Remove `--reload` from `agentos-api` command (breaks MCP lifespan)
2. Add n8n service (shares postgres, isolated `n8n` database)
3. Add R2 mount into agno-app

```yaml
  agentos-api:
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000
    # removed: --reload --reload-dir ...

  n8n:
    image: n8nio/n8n:latest
    container_name: n8n
    restart: unless-stopped
    ports:
      - "5678:5678"
    environment:
      DB_TYPE: postgresdb
      DB_POSTGRESDB_HOST: agentos-db
      DB_POSTGRESDB_DATABASE: ${N8N_DB:-n8n}
      DB_POSTGRESDB_USER: ${DB_USER:-ai}
      DB_POSTGRESDB_PASSWORD: ${DB_PASS:-ai}
      N8N_ENCRYPTION_KEY: ${N8N_ENCRYPTION_KEY:-changeme-dev-key}
      GENERIC_TIMEZONE: ${TIMEZONE:-America/Detroit}
    volumes:
      - n8n_data:/home/node/.n8n
    depends_on:
      agentos-db:
        condition: service_healthy
    networks:
      - agentos

volumes:
  pgdata:
  n8n_data:
```

For R2: if rclone is the approach, add an environment block to agentos-api:
```yaml
    environment:
      R2_BUCKET_NAME: ${R2_BUCKET_NAME:-}
      R2_ACCESS_KEY_ID: ${R2_ACCESS_KEY_ID:-}
      R2_SECRET_ACCESS_KEY: ${R2_SECRET_ACCESS_KEY:-}
      R2_ENDPOINT_URL: ${R2_ENDPOINT_URL:-}
```
and mount `/r2` once credentials are set (can be a bind mount or rclone FUSE mount — document the method in a comment).

Also add a `healthcheck` to `agentos-db` so n8n's `depends_on` works:
```yaml
  agentos-db:
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER:-ai}"]
      interval: 5s
      timeout: 5s
      retries: 10
```

**Verify:**
```bash
docker compose up -d --build
docker compose ps                           # all services Up/healthy
curl -s http://localhost:8000/health        # 200 (or agno-app startup log shows no errors)
curl -s http://localhost:5678               # n8n UI responds
docker compose logs agentos-api | grep -i reload  # should NOT appear
```

---

## Step 3 — `agents/providers.py` (Context Providers → ctx)

**File to create:** `agents/providers.py`

This file produces the `PlatformContext` dataclass that `build_agent_team(ctx)` in `factory.py` consumes.

```python
from __future__ import annotations
import os
from dataclasses import dataclass, field
from typing import Any

from agno.context.workspace import WorkspaceContextProvider
from agno.context.database import DatabaseContextProvider
# from agno.context.gdrive import GoogleDriveContextProvider  # deferred: cloud cleanup goal
# from agno.context.mcp import MCPContextProvider             # deferred: MCP servers goal

@dataclass
class PlatformContext:
    model: Any
    db: Any
    knowledge: Any
    learning: Any
    source_tools: list[Any] = field(default_factory=list)
    code_tools: list[Any] = field(default_factory=list)
    readonly_db_tools: list[Any] = field(default_factory=list)
    drive_read_tools: list[Any] = field(default_factory=list)
    drive_write_tools: list[Any] = field(default_factory=list)


def build_context(model, db, knowledge, learning, analysis_url: str, evidence_url: str) -> PlatformContext:
    # Live codebase — read-only navigation
    workspace = WorkspaceContextProvider(id="workspace")
    code_tools = workspace.get_tools()

    # Evidence (read-only) vs analysis (write, approval-gated)
    db_provider = DatabaseContextProvider(
        sql_engine=_make_engine(analysis_url),
        readonly_engine=_make_engine(evidence_url, readonly=True),
    )
    readonly_db_tools = db_provider.get_read_tools()  # physically cannot write

    # Drive tools deferred until cloud cleanup goal
    drive_read_tools: list[Any] = []
    drive_write_tools: list[Any] = []

    # Source tools = workspace + db read (MCP servers added at Phase 7)
    source_tools = [*code_tools, *readonly_db_tools]

    return PlatformContext(
        model=model, db=db, knowledge=knowledge, learning=learning,
        source_tools=source_tools, code_tools=code_tools,
        readonly_db_tools=readonly_db_tools,
        drive_read_tools=drive_read_tools, drive_write_tools=drive_write_tools,
    )


def _make_engine(url: str, readonly: bool = False):
    """SQLAlchemy async engine from a URL."""
    from sqlalchemy.ext.asyncio import create_async_engine
    connect_args = {"options": "-c default_transaction_read_only=on"} if readonly else {}
    return create_async_engine(url, connect_args=connect_args)
```

**Re-verify imports inside the image before finalizing:**
```bash
docker exec agentos-api python -c "from agno.context.workspace import WorkspaceContextProvider; print('ok')"
docker exec agentos-api python -c "from agno.context.database import DatabaseContextProvider; print('ok')"
```

**Verify:**
```bash
docker exec agentos-api python -c "from agents.providers import build_context; print('import ok')"
```

---

## Step 4 — LearningMachine (`build_learning`)

**File to modify:** `agents/providers.py` (add `build_learning` function)

```python
def build_learning(db, model, knowledge):
    """Native operational memory on existing Postgres. PROPOSE = human confirms."""
    # First: verify the import path inside the container
    try:
        from agno.learn import (
            LearningMachine, LearningMode,
            UserProfileConfig, UserMemoryConfig,
            SessionContextConfig, EntityMemoryConfig, LearnedKnowledgeConfig,
        )
    except ImportError:
        from agno.learning import (  # fallback if module name differs
            LearningMachine, LearningMode,
            UserProfileConfig, UserMemoryConfig,
            SessionContextConfig, EntityMemoryConfig, LearnedKnowledgeConfig,
        )

    return LearningMachine(
        user_profile=UserProfileConfig(mode=LearningMode.ALWAYS),
        user_memory=UserMemoryConfig(mode=LearningMode.AGENTIC),
        session_context=SessionContextConfig(mode=LearningMode.ALWAYS, enable_planning=True),
        entity_memory=EntityMemoryConfig(mode=LearningMode.PROPOSE),
        learned_knowledge=LearnedKnowledgeConfig(
            mode=LearningMode.PROPOSE,
            knowledge=knowledge,
            namespace="platform",
            agent_can_save=True,
            agent_can_search=True,
        ),
        enable_clear_memories=False,  # no bulk deletion
    )
```

**Verify import path:**
```bash
docker exec agentos-api python -c "from agno.learn import LearningMachine; print('agno.learn ok')"
# if that fails:
docker exec agentos-api python -c "from agno.learning import LearningMachine; print('agno.learning ok')"
```

---

## Step 5 — `app/main.py` Rewrite (THE SPINE)

**File to rewrite:** `app/main.py`

This is the most critical file. The current version imports old flat agent modules and doesn't wire the router. Replace it entirely.

Key constraints (from anti-pattern table in EXECUTION_PLAN.md):
- `AgentOS(base_app=app)` + `get_app()` — NEVER `app.mount(...)`
- NO `reload=True` — breaks MCP lifespan
- Register `agents["router"]` as the entry point
- On pause: persist `approval_request` row WITH `run_id`

```python
"""
AgentOS Entrypoint — v8.1
=========================
"""
from contextlib import asynccontextmanager
from os import getenv
from fastapi import FastAPI
from agno.os import AgentOS
from agno.utils.log import log_info

from agents.factory import build_agent_team
from agents.providers import build_context, build_learning
from app.settings import build_model
from db import get_postgres_db, create_knowledge
from db.url import db_url

runtime_env = getenv("RUNTIME_ENV", "dev")
scheduler_base_url = getenv("AGENTOS_URL", "http://127.0.0.1:8000")


@asynccontextmanager
async def lifespan(app):
    log_info("AgentOS lifespan: startup")
    try:
        yield
    finally:
        log_info("AgentOS lifespan: shutdown")


def _build_app():
    model = build_model()
    db = get_postgres_db()
    knowledge = create_knowledge("platform", "platform_knowledge")
    learning = build_learning(db, model, knowledge)

    # analysis engine (writes OK) and evidence engine (read-only)
    analysis_url = db_url.replace("+psycopg", "+asyncpg")   # async engines
    evidence_url = analysis_url  # same DB, different schema; readonly_engine uses read-only connection

    ctx = build_context(model, db, knowledge, learning, analysis_url, evidence_url)
    agents = build_agent_team(ctx)

    app = FastAPI(title="MCP Platform Assistant — AgentOS")
    _register_approval_routes(app, agents, db)
    _register_knowledge_routes(app, knowledge)

    agent_os = AgentOS(
        agents=list(agents.values()),
        base_app=app,
        on_route_conflict="preserve_base_app",
        scheduler=True,
        tracing=True,
        db=db,
        lifespan=lifespan,
    )
    return agent_os.get_app()


def _register_approval_routes(app, agents, db):
    from fastapi import Body
    from pydantic import BaseModel

    class DecisionBody(BaseModel):
        decision: str   # "approved" | "rejected"
        decided_by: str = "owner"
        decision_notes: str = ""

    @app.get("/v1/approval-requests")
    async def list_pending():
        # Query approval_request WHERE approval_status='pending'
        return {"pending": []}  # implement with db query

    @app.post("/v1/approval-requests/{approval_id}/decision")
    async def decide(approval_id: str, body: DecisionBody = Body(...)):
        # 1. fetch approval_request row (run_id, agent_key, paused_tools)
        # 2. resume via agents[agent_key].acontinue_run(run_id=..., updated_tools=...)
        # 3. update row status + decision fields
        return {"id": approval_id, "approvalStatus": body.decision}


def _register_knowledge_routes(app, knowledge):
    @app.post("/v1/knowledge/reindex")
    async def reindex():
        # trigger agents/ingestion.py logic
        return {"status": "queued"}


app = _build_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)
```

**Also fix `evals/cases.py`** — remove the two broken imports (`agents.code_search`, `agents.web_search`) so the evals module at least imports cleanly. Replace with stubs or remove the cases:
```python
# from agents.code_search import code_search   # REMOVED: agent doesn't exist in v8.1
# from agents.web_search import web_search      # REMOVED: agent doesn't exist in v8.1
CASES: tuple = ()  # evals to be rewritten for v8.1 agents
```

**Verify:**
```bash
docker compose up -d --build
docker exec agentos-api python -c "import app.main; print('main imports ok')"
curl http://localhost:8000/docs              # Swagger UI loads
curl http://localhost:8000/v1/approval-requests  # returns JSON
# Test routing: send a builder-style prompt and check logs show Builder team response
```

---

## Step 6 — Knowledge Drop Zone + Ingestion

**Files to create/modify:**
- `knowledge/platform/conversations/` (create directory + `.gitkeep`)
- `knowledge/platform/docs/` (create directory + `.gitkeep`)
- `knowledge/platform/notes/` (create directory + `.gitkeep`)
- `scripts/ingest_knowledge.py` (rewrite — currently a stub)
- `agents/ingestion.py` (create — the `python -m agents.ingestion` entrypoint)

**Embedder + Reranker: NVIDIA NIM only — no OpenAI key required.**

`db/session.py` has already been updated to use:
- **Embedder:** `nvidia/nv-embedqa-e5-v5` (1024-d, text/transcripts/docs) via `OpenAIEmbedder` with NIM base_url
- **Code embedder:** `nvidia/nv-embedcode-7b-v1` (4096-d) for code artifact collections
- **Reranker:** `nvidia/nv-rerankqa-mistral-4b-v3` via `CohereReranker` (NIM rerank endpoint is Cohere-API-compatible)

**CRITICAL — verify dims before first boot:**
```bash
# Confirm nv-embedqa-e5-v5 output dimension (must match EMBED_TEXT_DIM=1024)
curl -s https://integrate.api.nvidia.com/v1/embeddings \
  -H "Authorization: Bearer $NVIDIA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"nvidia/nv-embedqa-e5-v5","input":"test"}' \
  | python -c "import sys,json; d=json.load(sys.stdin); print(len(d['data'][0]['embedding']))"
# Expected: 1024
```

If dim is wrong, set `NVIDIA_EMBED_TEXT_DIM=<actual>` in `.env` BEFORE `docker compose up`. Wrong dim = must drop + re-create the vector table.

**Verify reranker import in the image:**
```bash
docker exec agentos-api python -c "from agno.reranker.cohere import CohereReranker; print('reranker ok')"
# If ImportError, check: docker exec agentos-api python -c "import agno.reranker; print(dir(agno.reranker))"
# db/session.py falls back gracefully if reranker import fails — Knowledge still boots
```

**`scripts/ingest_knowledge.py`** (replace print stub):
```python
"""
Knowledge ingestion: scan knowledge/platform/, normalize, call knowledge.ainsert().
Run via: docker exec -it agentos-api python -m agents.ingestion
"""
import asyncio
from pathlib import Path
from agno.knowledge.knowledge import Knowledge
from db import create_knowledge

ALLOWED_EXT = {".md", ".txt", ".json", ".csv", ".pdf", ".docx"}
MAX_SIZE = 50 * 1024 * 1024  # 50 MB
BASE_PATH = Path("/app/knowledge/platform")


async def ingest_all(knowledge: Knowledge) -> int:
    count = 0
    for path in BASE_PATH.rglob("*"):
        if path.suffix not in ALLOWED_EXT:
            continue
        if not path.is_file():
            continue
        if path.stat().st_size > MAX_SIZE:
            print(f"SKIP (>50MB): {path}")
            continue
        category = path.parent.name  # conversations / docs / notes
        name = path.stem.lower().replace(" ", "-").replace("_", "-")[:127]
        print(f"  inserting [{category}] {name}")
        await knowledge.ainsert(
            name=name,
            path=str(path),
            metadata={"category": category, "source_path": str(path)},
        )
        count += 1
    return count


async def main():
    knowledge = create_knowledge("platform", "platform_knowledge")
    print(f"Ingesting from {BASE_PATH}...")
    n = await ingest_all(knowledge)
    print(f"Done. {n} document(s) indexed.")


if __name__ == "__main__":
    asyncio.run(main())
```

**`agents/ingestion.py`** (module entrypoint):
```python
"""python -m agents.ingestion"""
from scripts.ingest_knowledge import main
import asyncio
asyncio.run(main())
```

**Verify:**
```bash
# Place one .md file in knowledge/platform/conversations/
docker exec agentos-api python -m agents.ingestion
# Expected output: "Done. 1 document(s) indexed."
docker exec agentos-db psql -U ai -d ai -c "SELECT count(*) FROM platform_knowledge;"  # > 0
```

---

## Step 7 — Grounded Answer Test (Done Condition)

After ingesting at least one transcript about the evidence platform:

```bash
curl -X POST http://localhost:8000/v1/runs \
  -H "Content-Type: application/json" \
  -d '{"message": "Based on my previous conversations, what was the planned architecture for the evidence MCP platform?", "stream": false}'
```

Expected: the Dev Copilot (routed via Builder team) returns an answer that cites specific content from the ingested transcript file, not generic knowledge.

---

## Verification Checklist (all 20 facts)

| Fact ID | How to verify | Pass condition |
|---|---|---|
| boot-compose | `docker compose up -d --build` | Exit 0, all services Up |
| boot-health | `curl http://localhost:8000/docs` | HTTP 200 |
| n8n-health | `curl http://localhost:5678` | HTTP 200 |
| r2-mount | Check compose.yaml + env vars set | Volume defined in compose |
| no-reload | `docker compose logs agentos-api \| grep reload` | No match |
| base-app-pattern | Read `app/main.py` | `AgentOS(base_app=app)`, no `app.mount` |
| router-entry | Send a Platform Ops prompt; check logs | Routes to Platform Ops team |
| sql-migrations | `\dt` in psql | All 4 tables present |
| evidence-readonly | Run INSERT with `default_transaction_read_only=on` | ERROR: cannot execute INSERT |
| run-id-capture | Trigger a write tool; check `approval_request` | `run_id` column non-null |
| providers-ctx | `python -c "from agents.providers import build_context"` | No import error |
| readonly-enforced | Check DatabaseContextProvider write tool absence | write tools not in readonly list |
| learning-machine | Trigger a PROPOSE learning; check API response | Human-confirm step in response |
| embedder-resolved | `python -m agents.ingestion` with no OpenAI key set | Either succeeds OR clear error message pointing to specific env var |
| knowledge-dropzone | `ls /app/knowledge/platform/conversations/` in container | Directory exists |
| real-ingest | Read `scripts/ingest_knowledge.py` | Contains `knowledge.ainsert(` not `print(` |
| ingest-runs | `python -m agents.ingestion` | Prints doc count, no errors |
| grounded-answer | POST /v1/runs with architecture question | Answer cites specific content from transcript |
| model-factory | Boot with only `NVIDIA_API_KEY` set | Agent responds |
| example-env-complete | Read `example.env` | All vars present + embeddings note |

---

## Risks & Open Questions

1. **`DatabaseContextProvider` API** — the method names `get_tools()` vs `get_read_tools()` are not confirmed. Re-verify against the built image before writing `providers.py`.
2. **`LearningMachine` import path** — confirm `agno.learn` vs `agno.learning` in the container before wiring.
3. **`WorkspaceContextProvider.get_tools()`** — method may be `get_tools()` or a different accessor. Check in image.
4. **n8n database** — n8n connects to postgres but creates its own tables. Confirm it doesn't interfere with `evidence`/`analysis` schemas (it uses `public` by default; consider setting `DB_POSTGRESDB_SCHEMA=n8n`).
5. **NVIDIA NIM embedder dimensions** — `nv-embedqa-e5-v5` output dim must be verified against NVIDIA docs before setting `VECTOR(n)` in the knowledge table. Wrong dim breaks the pgvector column.
6. **R2 mount method** — rclone FUSE mount in Docker requires `--privileged` or `--cap-add SYS_ADMIN`. Simpler alternative: S3-compatible boto3 reads from the agno app. Decide and document.
7. **`app/main.py` DB URL for async engines** — the current `db_url` uses `postgresql+psycopg` (sync driver). Async engines need `postgresql+asyncpg`. May need both drivers in `pyproject.toml`.
