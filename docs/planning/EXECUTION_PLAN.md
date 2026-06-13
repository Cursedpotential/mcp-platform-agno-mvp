# Agno MCP Platform — LLM Execution Plan

> **⚠️ STATUS (2026-06-11): MVP Goal 1 is DONE and the stack is live on the VPS.** This file
> is the historical Phase-1 build plan. For current state, vision, and the active round read
> [`../PROJECT_CANON.md`](../PROJECT_CANON.md) and the active plan
> [`../../plans/logical-herding-forest.md`](../../plans/logical-herding-forest.md). Decisions
> since: ADRs 0013–0021. This plan is retained for build history; do not treat it as current.
>
> **Version:** 1.0 · **Date:** 2026-06-07
> **Inputs read:** Handoff Guide v8.1 · FollowUp Guide · MIGRATION_PLAN_v8.md · BUILD_TODO.md · VERIFIED_AGNO_API.md · all source files
> **How to use this:** a fresh coding agent should read THIS file first, then the phase it is working, then the exact files listed. Do NOT re-read the full handoff guides unless a specific detail is missing — this plan is the compressed, executable form of them.
> **Container-first rule:** Agno runs ONLY inside the `agno-app` image (Python 3.11). Host is Python 3.14, no agno. Dev loop = `docker compose up -d --build`. Verify inside the container, not via a host venv.

---

## Current State Summary (as of 2026-06-07)

| Phase | Status | Notes |
|---|---|---|
| Phase 1 — Settings + deps | ✅ **Done** | `app/settings.py` provider-agnostic, `pyproject.toml` has core deps, `example.env` partial |
| Phase 2 — Database | ⚠️ **Partial** | Compose uses `agnohq/pgvector:18` (good: PG18 + pgvector built in), but **`sql/` dir does not exist** — no extension/schema migrations |
| Phase 3 — Compose | ⚠️ **Partial** | Has postgres + agno-app but **missing n8n + R2 rclone volume** |
| Phase 4 — Context Providers | ❌ **Not built** | `agents/providers.py` does not exist |
| Phase 5 — LearningMachine | ❌ **Not built** | No `build_learning()` function; not wired into factory or app |
| Phase 6 — app/main.py | ⚠️ **Broken** | Has AgentOS skeleton but imports old flat modules, uses `reload=True`, no `ctx` assembly, no router as entry point |
| Phase 7 — MCP servers | ❌ **Not built** | No `mcp-servers/` vendored; `MCPTools` not wired |
| Phase 8 — Approval flow | ❌ **Not built** | HITL tools are stubs; no `continue_run` wiring; no `run_id` in schema |
| Phase 9 — Knowledge + ingestion | ⚠️ **Partial** | `db/session.py` has `create_knowledge()` (correct hybrid pattern), no `agents/ingestion.py` or real `ingest_knowledge.py` |
| Phase 10 — ChatMiner | ⚠️ **Partial** | `agents/transcript_miner.py` exists, has known import bugs (3 listed in migration plan) |
| Phase 11 — Cloud cleanup | ❌ **Not built** | No providers, no MCP servers configured |
| Phase 12 — Evals | ⚠️ **Skeleton** | `evals/` harness exists; no real categories (accuracy/routing/governance) |
| Phase 13 — Review Panel | ❌ **Not built** | Post-MVP |

**Critical unblocking priority:** Phase 2 SQL → Phase 4 Providers → Phase 5 Memory → **Phase 6 main.py** (spine).

---

## Locked Architecture (do not re-litigate)

```
Root Router  (mode="route")           agents["router"]
├── Platform Ops Team (coordinate)
│   ├── Ingestion Orchestrator
│   ├── Analysis Orchestrator
│   └── Review Gatekeeper
├── Builder Team (coordinate)
│   ├── Dev Copilot (UserControlFlowTools)
│   ├── Project PAL
│   └── Forensic Data Agent (readonly_db_tools)
└── Cloud Drive Cleanup Agent (standalone, trash-only)
```

- `agents/factory.py` is already the reference implementation — **do not rewrite it**.
- `agents/instructions.py` is already the reference — **do not rewrite it**.
- HITL = `@tool(requires_confirmation=True)` + `continue_run()`. Not a custom REST state machine.
- Memory = native `LearningMachine`. No `learned_knowledge` table.
- Read/write split = `DatabaseContextProvider(sql_engine=analysis, readonly_engine=evidence)`. Infrastructure-level, not prompt-level.

---

## Verified Agno Imports (confirmed against live docs — re-verify against pinned image)

```python
from agno.os import AgentOS
from agno.agent import Agent
from agno.team.team import Team                               # mode="route" / "coordinate"
from agno.tools import tool                                   # @tool(requires_confirmation=True)
from agno.tools.user_control_flow import UserControlFlowTools
from agno.tools.mcp import MCPTools                           # one per server; AgentOS manages lifecycle
from agno.tools.mcp_toolbox import MCPToolbox                 # DB fleet toolsets
from agno.context.mcp import MCPContextProvider               # read-only default
from agno.context.workspace import WorkspaceContextProvider   # NOTE: NOT "Workspace"
from agno.context.gdrive import GoogleDriveContextProvider
from agno.context.database import DatabaseContextProvider     # infra read/write split
from agno.knowledge.knowledge import Knowledge
from agno.vectordb.pgvector import PgVector, SearchType
from agno.db.postgres import PostgresDb
# LearningMachine: confirm `from agno.learn import LearningMachine, LearningMode, ...`
# (may be agno.learning — verify in the built image before wiring)
```

**Watch-outs:**
- `FilesystemContextProvider` (agno.context.fs) NOT confirmed in docs — use `WorkspaceContextProvider` instead for the codebase; use plain knowledge ingest for frozen docs/archives.
- Actual class name is `WorkspaceContextProvider`, not `Workspace`.
- `AgentOS(base_app=app)` + `get_app()`. NEVER `app.mount(...)`.
- `reload=True` BREAKS MCP lifespan. Never in production; only acceptable in dev when MCPTools are NOT attached.
- `MultiMCPTools` is NOT deprecated — it's a valid style choice. But one `MCPTools` per server is simpler default.

---

## Anti-Patterns (from v1 corrections — guaranteed to break things)

| ❌ Do NOT | ✅ Do instead |
|---|---|
| `app.mount("/path", agentos_app)` | `AgentOS(base_app=app)` → `agent_os.get_app()` |
| `reload=True` with MCPTools attached | `reload=False` always for this app |
| Manual `.connect()` / `.close()` inside AgentOS | AgentOS manages MCP lifecycle automatically |
| `knowledge.add_content_async(...)` | `knowledge.ainsert(name=, path=, metadata=)` |
| `learned_knowledge` custom table | LearningMachine `LearnedKnowledgeConfig` |
| `AgentMemory` / `TeamMemory` | removed in Agno v2; use `enable_user_memories=True` / `learning=` |
| Hard-coded `gpt-4o` or `claude-sonnet-*` default | Provider-agnostic factory in `app/settings.py` |
| `uuid_generate_v4()` | `uuidv7()` (PG18 native, no extension needed) |
| Store digests as hex TEXT | `BYTEA` with `CHECK octet_length` |
| `update_memory_on_run=True` AND `enable_agentic_memory=True` together | Mutually exclusive — pick one |

---

## Phase 2 — Database: SQL Migrations

**Files to create:** `sql/0001_init_extensions.sql`, `sql/0002_schema.sql`, `docker/postgres/Dockerfile` (optional custom image — current `agnohq/pgvector:18` may suffice)

> Note: `compose.yaml` currently uses `agnohq/pgvector:18` which already has pgvector. Verify if PostGIS, pg_trgm, pgcrypto, pg_textsearch are present before creating a custom Dockerfile. If they're already in that image, a custom Dockerfile is NOT needed — just add the SQL init files.

**Pattern (copy from handoff §8.1):**

`sql/0001_init_extensions.sql`:
```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS btree_gin;
CREATE EXTENSION IF NOT EXISTS btree_gist;
CREATE EXTENSION IF NOT EXISTS unaccent;
-- UUIDv7 is native on PG18: uuidv7() — NO extension needed.
-- pg_textsearch: baked in image but NOT enabled here (enable when BM25 needed).
```

`sql/0002_schema.sql` (key design decisions):
- PKs: `DEFAULT uuidv7()` (PG18 native, timestamp-ordered)
- Two schemas: `evidence` (read-only, never written by agents) + `analysis` (derived artifacts)
- `agent_run` and `approval_request` tables: **add `run_id` column** (the native-confirm resume key — maps paused Agno run to the approval row)
- `evidence_hash` table with `digest BYTEA` + `CHECK (algo <> 'sha256' OR octet_length(digest) = 32)`
- Keep `transcript_insight` (ChatMiner output)
- **NO `learned_knowledge` table** (→ LearningMachine owns this)

**Mounting init SQL:** Copy to `docker-entrypoint-initdb.d/` in compose or Dockerfile. Only runs on first boot.

**How to mount in compose.yaml (if using agnohq/pgvector:18 stock image):**
```yaml
  agentos-db:
    image: agnohq/pgvector:18
    volumes:
      - pgdata:/var/lib/postgresql
      - ./sql/0001_init_extensions.sql:/docker-entrypoint-initdb.d/01_extensions.sql:ro
      - ./sql/0002_schema.sql:/docker-entrypoint-initdb.d/02_schema.sql:ro
```

**Verify:** Extensions apply on first boot. A connection with `default_transaction_read_only=on` rejects writes to `evidence` schema.

---

## Phase 3 — Compose: Add n8n + R2

**File to modify:** `compose.yaml`

**Add two services** (owner-confirmed: both in scope):

```yaml
  n8n:
    image: n8nio/n8n
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
      N8N_ENCRYPTION_KEY: ${N8N_ENCRYPTION_KEY}
    depends_on:
      agentos-db:
        condition: service_healthy
    networks:
      - agentos
    volumes:
      - n8n_data:/home/node/.n8n
```

R2 is mounted via an `rclone` volume or bind-mount into `agno-app` at `/r2` — acts as the §17 blob landing zone. Exact approach depends on whether rclone or a FUSE mount is used.

**Also fix in compose.yaml:**
- Remove `--reload` from `agentos-api` command (breaks MCP). Replace with `uvicorn app.main:app --host 0.0.0.0 --port 8000` (no reload).
- Add `healthcheck` to `agentos-db`.

**Verify:** `docker compose up -d --build` → all healthy; `/health` 200; n8n accessible at :5678.

---

## Phase 4 — Context Providers (`agents/providers.py`)

**File to create:** `agents/providers.py`

This file builds the `ctx` object (a simple dataclass or named tuple) that `build_agent_team(ctx)` in `factory.py` expects. The factory accesses: `ctx.model`, `ctx.db`, `ctx.knowledge`, `ctx.learning`, `ctx.source_tools`, `ctx.code_tools`, `ctx.readonly_db_tools`, `ctx.drive_read_tools`, `ctx.drive_write_tools`.

**Pattern:**
```python
from dataclasses import dataclass
from typing import Any
from agno.context.workspace import WorkspaceContextProvider
from agno.context.database import DatabaseContextProvider
from agno.context.gdrive import GoogleDriveContextProvider
from agno.context.mcp import MCPContextProvider

@dataclass
class PlatformContext:
    model: Any
    db: Any
    knowledge: Any
    learning: Any
    source_tools: list[Any]    # TS/Py MCP + Workspace + DB fleet MCPToolbox
    code_tools: list[Any]      # WorkspaceContextProvider → query_workspace
    readonly_db_tools: list[Any]  # DatabaseContextProvider read sub-agent → evidence schema
    drive_read_tools: list[Any]   # GoogleDriveContextProvider per account
    drive_write_tools: list[Any]  # MCPContextProvider trash-only over piotr-agier MCP server

def build_context(model, db, knowledge, learning) -> PlatformContext:
    # Workspace (live codebase, read-only)
    workspace = WorkspaceContextProvider(id="workspace")
    code_tools = workspace.get_tools()

    # Database — evidence (read-only) vs analysis (write, approval-gated)
    # readonly_engine → evidence schema; sql_engine → analysis schema
    db_provider = DatabaseContextProvider(
        sql_engine=analysis_engine,
        readonly_engine=evidence_engine,
    )
    readonly_db_tools = db_provider.get_read_tools()  # verify exact method name in image

    # Google Drive read providers — one per account (corpora="user")
    # (build only if GOOGLE_SA_FILE_* env vars are set)
    drive_read_tools = []
    for acct_id in _configured_drive_accounts():
        p = GoogleDriveContextProvider(id=f"gdrive_{acct_id}", corpora="user")
        drive_read_tools.extend(p.get_tools())

    # Cloud cleanup write tools (trash-only)
    drive_write_tools = []
    if cleanup_url := os.getenv("DRIVE_CLEANUP_MCP_URL"):
        cleanup_provider = MCPContextProvider(
            id="drive_cleanup",
            url=cleanup_url,
            include_tools=["search", "list", "get_metadata",
                           "create_folder", "move", "rename", "trash"],
        )
        drive_write_tools = cleanup_provider.get_tools()

    # Source tools = TS/Py MCP tools + DB fleet + Workspace
    # (MCPTools added in Phase 7; for now use [] placeholder)
    source_tools = [*code_tools]

    return PlatformContext(
        model=model, db=db, knowledge=knowledge, learning=learning,
        source_tools=source_tools, code_tools=code_tools,
        readonly_db_tools=readonly_db_tools,
        drive_read_tools=drive_read_tools, drive_write_tools=drive_write_tools,
    )
```

**Verify (inside container):** `from agents.providers import build_context` imports cleanly; read sub-agents cannot write; no tool-name collisions (`query_workspace`, `query_database`, `query_gdrive_*` are all distinct).

---

## Phase 5 — LearningMachine

**File to modify:** `agents/providers.py` — add `build_learning(db, model, knowledge)`.

**Exact import to confirm in the built image:**
```python
from agno.learn import (
    LearningMachine, LearningMode,
    UserProfileConfig, UserMemoryConfig,
    SessionContextConfig, EntityMemoryConfig, LearnedKnowledgeConfig,
)
# If agno.learn fails, try: from agno.learning import ...
```

**Pattern (from handoff §7.1b):**
```python
def build_learning(db, model, knowledge) -> LearningMachine:
    return LearningMachine(
        user_profile=UserProfileConfig(mode=LearningMode.ALWAYS),
        user_memory=UserMemoryConfig(mode=LearningMode.AGENTIC),
        session_context=SessionContextConfig(mode=LearningMode.ALWAYS, enable_planning=True),
        entity_memory=EntityMemoryConfig(mode=LearningMode.PROPOSE),
        learned_knowledge=LearnedKnowledgeConfig(
            mode=LearningMode.PROPOSE,
            knowledge=knowledge, namespace="platform",
            agent_can_save=True, agent_can_search=True,
        ),
        # Consider also: DecisionLogConfig for the HITL approval audit trail
    )
    # IMPORTANT: enable_clear_memories=False (no bulk delete)
```

**Modes rationale:**
- `ALWAYS` / `AGENTIC` for profile/session (low-stakes, frequent)
- `PROPOSE` for entity + learned knowledge (high-stakes, durable — human confirms before writing)

**Verify (inside container):** stores persist to Postgres; a PROPOSE capture surfaces a human-confirm step in the API response.

---

## Phase 6 — `app/main.py` Rewrite (THE SPINE)

**File to rewrite:** `app/main.py`

This is the most critical file. The current version is broken: it imports old flat agent modules, uses `reload=True`, and doesn't wire the router.

**What it must do:**
1. Build Context Providers → assemble `ctx` via `agents/providers.py`
2. Call `build_agent_team(ctx)` from `agents/factory.py`
3. Register `agents["router"]` as the AgentOS primary entry point
4. Register custom routes: `/v1/approval-requests`, `/v1/knowledge/reindex`, `/v1/transcripts/mine`
5. On a native-confirm pause: persist `approval_request` row **with `run_id`** + paused-tool refs
6. **NEVER** use subpath mount; **NEVER** `reload=True` with MCPTools attached

**Pattern (from handoff §8.2):**
```python
from fastapi import FastAPI
from agno.os import AgentOS
from agents.factory import build_agent_team
from agents.providers import build_context, build_learning
from app.settings import build_model
from db import get_postgres_db, create_knowledge

async def build_app():
    model = build_model()
    db = get_postgres_db()
    knowledge = create_knowledge("platform", "platform_knowledge")
    learning = build_learning(db, model, knowledge)
    ctx = build_context(model, db, knowledge, learning)
    agents = build_agent_team(ctx)

    app = FastAPI(title="MCP Platform Assistant")
    register_approval_routes(app, agents)      # see routes below
    register_knowledge_routes(app, knowledge)
    register_transcript_routes(app, agents)

    agent_os = AgentOS(
        agents=list(agents.values()),
        base_app=app,
        on_route_conflict="preserve_base_app",
        scheduler=True,
        tracing=True,
        db=db,
    )
    return agent_os.get_app()

app = asyncio.run(build_app())  # or use lifespan

if __name__ == "__main__":
    import uvicorn
    # NO reload=True — breaks MCP lifespan
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)
```

**Approval route pattern** (captures `run_id` for native resume):
```python
@app.post("/v1/approval-requests/{id}/decision")
async def decide_approval(id: str, body: DecisionBody):
    row = await db.get_approval_request(id)
    # Resume or reject the native-confirm pause:
    if body.decision == "approved":
        for tool_call in row.paused_tools:
            tool_call.confirmed = True
        await agents[row.agent_key].acontinue_run(run_id=row.run_id, updated_tools=row.paused_tools)
    else:
        for tool_call in row.paused_tools:
            tool_call.confirmed = False
            tool_call.confirmation_note = body.decision_notes
        await agents[row.agent_key].acontinue_run(run_id=row.run_id, updated_tools=row.paused_tools)
    await db.update_approval_status(id, body.decision, body.decided_by, body.decision_notes)
```

**Also update compose.yaml**: remove `--reload` from the `agentos-api` command.

**Verify (inside container):** service boots; a request to `/docs` works; a request routed to Builder lands in the Builder team (check `show_members_responses` output); a write action creates a `pending` approval_request row with a non-null `run_id`.

---

## Tool Porting Source (Evidence Platform — Goal 2)

> **Owner note (2026-06-07):** The vast majority of tools for the evidence processing platform come from `dev-resources/`. The canonical source order is:
>
> 1. **`dev-resources/Archives/MCP_PLATFORM/mcp-servers/`** — the modular TS/Py/JS servers; vendor these into `mcp-servers/` at Phase 7.
> 2. **`dev-resources/Archives/MCP_Tool_Platform-REF-READ-ONLY/server/mcp/`** — the alpha monolith; the largest pool of capabilities still to port (tool by tool, via Dev Copilot).
> 3. **`dev-resources/Archives/TheBigOne/`** — TraceIQ, Evidence, Voice; mine for domain logic.
> 4. **`Agno-MCP-Platform-agno - alpha/`** — ChatMiner parsers, instructions, lib/chunking (Phase 10).
>
> Strategy: Dev Copilot (context-loaded with transcript history) identifies what to port next; Forensic Data Agent queries the existing tool inventory; Dev Copilot proposes the port; human approves. This is Goal 2.

---

## Phase 7 — MCP Connectivity

**Files to create:** `mcp-servers/` (vendored from `dev-resources/Archives/MCP_PLATFORM/mcp-servers/`)

MCP servers location (confirmed in MIGRATION_PLAN §7 open decisions):
- `dev-resources/Archives/MCP_PLATFORM/mcp-servers/ts-mcp-server/`
- `dev-resources/Archives/MCP_PLATFORM/mcp-servers/py-mcp-server/`
- `dev-resources/Archives/MCP_PLATFORM/mcp-servers/js-mcp-server/`

**Decision (owner: vendor):** Copy these into `agno-mvp/mcp-servers/` so the container is self-contained.

**Pattern (from handoff §7.2):**
```python
from agno.tools.mcp import MCPTools

ts_mcp = MCPTools(
    command=os.getenv("TS_MCP_COMMAND"),   # e.g. "node mcp-servers/ts-mcp-server/dist/index.js"
    tool_name_prefix="ts",
    refresh_connection=True,
)
py_mcp = MCPTools(
    command=os.getenv("PY_MCP_COMMAND"),
    tool_name_prefix="py",
    refresh_connection=True,
)
# AgentOS manages the MCP lifespan — do NOT manually .connect() / .close() inside AgentOS.
# Manual `async with MCPTools(...)` is ONLY for standalone scripts.
```

Wire `ts_mcp` and `py_mcp` into `ctx.source_tools` in `agents/providers.py`.

**Verify (inside container):** tool discovery lists TS tools (hash, parse, normalize, etc.) and Py tools (document_intelligence, embeddings, etc.).

---

## Phase 8 — Approval Flow End-to-End

**Files to modify:** `agents/factory.py` (wire HITL tools), `app/main.py` (approval routes).

The `apply_db_modification` and `trash_cloud_file` tools in `factory.py` currently `raise NotImplementedError`. Wire them to the real execution paths after confirmation:

```python
@tool(requires_confirmation=True)
def apply_db_modification(statement: str, target_schema: str) -> str:
    """After confirmation, this executes via the DatabaseContextProvider write path."""
    # Real implementation: call the analysis engine write path
    # Only called after Agno's native confirm pause is approved
    return db_provider.execute_write(statement, target_schema)
```

**Verify:**
1. A platform agent attempting a write → run pauses → `approval_request` row created with `run_id` set
2. Call `POST /v1/approval-requests/{id}/decision` with `{"decision": "approved"}` → run resumes via `continue_run` → write completes
3. Reject → reason lands in `confirmation_note` → agent receives it in next turn
4. DB read/write split holds: `evidence` reads succeed; `evidence` write attempt fails at connection level

---

## Phase 9 — Knowledge + Ingestion

**Files to create/modify:**
- `agents/ingestion.py` (module entrypoint: `python -m agents.ingestion`)
- `scripts/ingest_knowledge.py` (scan/normalize/manifest → `knowledge.ainsert()`)
- `knowledge/platform/{conversations,docs,notes}/` directories

**Ingestion strategy (embed vs navigate):**
- **Frozen archives** → embed into Knowledge (`knowledge.ainsert(name=, path=, metadata=)`)
- **Live codebase** → navigate via `WorkspaceContextProvider` (never embed stale snapshots)
- **Never ingest** `dev-resources/Archives/OTHER_RESOURCES_TO_SORT/Secrets/` or `*.xxh3` files

**Pattern (from handoff §9.1 + §7.1):**
```python
# scripts/ingest_knowledge.py
async def ingest_all(knowledge: Knowledge, base_path: Path) -> int:
    ALLOWED_EXT = {".md", ".txt", ".json", ".csv", ".pdf", ".docx"}
    count = 0
    for path in base_path.rglob("*"):
        if path.suffix not in ALLOWED_EXT:
            continue
        if path.stat().st_size > 50 * 1024 * 1024:  # 50MB
            print(f"SKIP (too large): {path}")
            continue
        category = path.parent.name  # conversations / docs / notes
        name = path.stem.lower().replace("_", "-").replace(" ", "-")
        await knowledge.ainsert(
            name=name,
            path=str(path),
            metadata={"category": category, "source_path": str(path)},
        )
        count += 1
    return count
```

**Verify:** `docker exec -it agentos-api python -m agents.ingestion` completes without error; an agent can answer a grounded question from the imported docs.

---

## Phase 10 — ChatMiner Integration

**Files to fix:** `chatminer/__init__.py`, `chatminer/core/artifacts.py`

**Three known bugs to fix (from MIGRATION_PLAN §6):**
1. `chatminer/__init__.py` imports non-existent `chatminer.core.pipeline` → add `chatminer/core/pipeline.py` with `parse_file`, `parse_multiple`, `parse_directory`, OR trim exports.
2. Root `parsers/__init__.py` imports non-existent `parsers.detector`/`.pipeline`/`.normalizer` → **delete** root `parsers/` entirely (superseded by `chatminer/parsers/`).
3. `chatminer/core/artifacts.py`: `ArtifactType.EVIDENCE_REFERENCE` not in enum → add the enum member.

**Routes to register** (in `app/main.py`):
- `POST /v1/transcripts/mine` → invokes `agents["transcript_miner"]` (re-add to factory)
- `GET /v1/transcripts/insights` → queries `transcript_insight` table

**transcript_miner agent** (re-add to `agents/factory.py`):
```python
def build_transcript_miner(model, db, knowledge, learning, chatminer_tools) -> Agent:
    return Agent(
        id="transcript-miner",
        name="Transcript Miner",
        role="Parse, segment, and extract insights from exported AI conversation transcripts.",
        model=model, db=db, knowledge=knowledge, learning=learning,
        tools=chatminer_tools,
        add_history_to_context=True, num_history_runs=10,
        instructions=[
            "Use chatminer tools to parse transcripts. Persist insights to transcript_insight.",
            "Never ingest raw transcripts into the evidence schema.",
        ],
        markdown=True,
    )
```

Add to `build_agent_team()` return dict: `"transcript_miner": transcript_miner`.

**Verify:** `import chatminer` cleans (no ImportError); `POST /v1/transcripts/mine` persists rows to `transcript_insight`.

---

## Phase 11 — Cloud Cleanup Agent

**Deferred until owner confirms:** number of Google + Microsoft accounts, service-account vs OAuth, exact MCP server versions.

**Reference:** `build_cloud_drive_cleanup_agent` in `agents/factory.py` is already written. This phase is just:
1. Stand up third-party MCP servers per account (Drive: `piotr-agier/google-drive-mcp`, OneDrive: `MrFixit96/onedrive-mcp-server`)
2. Configure `MCPContextProvider(include_tools=["search","list","get_metadata","create_folder","move","rename","trash"])` — NEVER `delete_permanently` / `empty_trash`
3. Pass `drive_read_tools` and `drive_write_tools` via `ctx` to the factory (already has the constructor)
4. Verify: dry-run plan phase reads only; `trash` is recoverable before touching real data

---

## Phase 12 — Evals

**Files to modify:** `evals/cases.py`, `evals/__main__.py`

The evals skeleton exists. Add these categories (from handoff §13 + dash pattern):

| Category | Type | What it checks |
|---|---|---|
| accuracy | `AccuracyEval` (1–10) | Grounded, correct answers from Knowledge |
| routing | `ReliabilityEval` | Router dispatches to correct family per prompt |
| governance | `AgentAsJudgeEval` (binary) | Refuses DDL/DML on `evidence` |
| boundaries | `AgentAsJudgeEval` (binary) | Schema-access and read-only boundaries respected |
| safety | `AgentAsJudgeEval` (binary) | No credential/secret leakage in outputs |

**Governance + boundaries MUST pass before any write path is trusted.**

Routing eval: build a fixed set of prompts, each labeled with expected family (Platform Ops / Builder / Cloud Cleanup). Assert router dispatches correctly ≥95% of labeled prompts.

---

## Phase 13 — Review Panel (Post-MVP)

**Files to create:** `ui/review_panel/` (static HTML/JS or React), two FastAPI routes

**Critical constraint:** The decision endpoint MUST resume the same native paused run via `continue_run(run_id, updated_tools=...)`. It is NOT a second approval path. The `run_id` is stored on the `approval_request` row (added in Phase 2 SQL).

**Routes:**
- `GET /v1/approval-requests?status=pending` → list pending rows
- `POST /v1/approval-requests/{id}/decision` → approve/reject → call `acontinue_run`

Bind to the `ApprovalRequestViewModel` in `ui/review_schema.ts` (already correct).

**Verify:** A paused action appears within seconds; Approve → run resumes; Reject + reason → `confirmation_note` set; state survives server restart (Postgres, not browser storage).

---

## Open Decisions (owner must decide before relevant phase)

| # | Decision | Proposed | Phase |
|---|---|---|---|
| D1 | Settings home: `app/settings.py` vs `config/settings.py` | Keep `app/settings.py` (skeleton layout) | 1 |
| D2 | `transcript_miner` placement: standalone vs team member | Standalone (recommended) | 6/10 |
| D3 | MCP servers: vendor vs external path | Vendor into `mcp-servers/` | 7 |
| D4 | PG18 vs PG17 fallback | PG18 target; PG17+pg_uuidv7 if builds missing | 2 |
| D5 | Cloud accounts: count + auth method per account | **Needed at Phase 11** | 11 |
| D6 | n8n role: driver, consumer, or both → `enable_mcp_server=True`? | TBD | 3 |
| D7 | Model provider for MVP runtime | Anthropic (ANTHROPIC_API_KEY) primary | 1 |

---

## Definition of Done (per phase)

A phase is NOT done until ALL hold:
1. Code committed to `Agno-MCP-Platform/` (the active repo).
2. Builds containerized — verified **inside** `docker compose build / up`, never via host venv.
3. Phase verify passes (boot, route, read-only reject, ingest answer, etc.).
4. Relevant eval/test green — governance + boundaries + routing must pass before any write path.
5. New architecture decisions have an ADR in `docs/adr/`.
6. `AGENTS.md` (root) updated to reflect new state.

---

## Quick Reference: File Dispositions

| File | Status | Next action |
|---|---|---|
| `agents/factory.py` | ✅ Reference ported | Add `transcript_miner` (Phase 10) |
| `agents/instructions.py` | ✅ Reference ported | Add transcript_miner text (Phase 10) |
| `agents/providers.py` | ❌ Missing | Create (Phase 4) |
| `app/main.py` | ⚠️ Broken | Rewrite (Phase 6) |
| `app/settings.py` | ✅ Done | Minor: confirm Anthropic model IDs current |
| `db/__init__.py`, `db/session.py`, `db/url.py` | ✅ Done | Keep |
| `compose.yaml` | ⚠️ Partial | Add n8n + R2 + remove --reload (Phase 3) |
| `sql/0001_init_extensions.sql` | ❌ Missing | Create (Phase 2) |
| `sql/0002_schema.sql` | ❌ Missing | Create (Phase 2) |
| `docker/postgres/Dockerfile` | ❌ Missing (optional) | Create only if agnohq/pgvector:18 lacks PostGIS/pg_trgm |
| `scripts/ingest_knowledge.py` | ❌ Missing | Create (Phase 9) |
| `agents/ingestion.py` | ❌ Missing | Create (Phase 9) |
| `chatminer/__init__.py` | ⚠️ Broken (3 bugs) | Fix (Phase 10) |
| `parsers/` (root) | ⚠️ Broken | Delete (Phase 10) |
| `evals/` | ⚠️ Skeleton | Add categories (Phase 12) |
| `ui/review_schema.ts` | ✅ Keep | — |
| `ui/review_panel/` | ❌ Missing | Create (Phase 13, post-MVP) |
| `memory/README.md` | ❌ Missing | Create (Phase 5) |
