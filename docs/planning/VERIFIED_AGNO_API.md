# Verified Agno API (vs live docs) — re-confirm against the pinned image

> The handoff is a snapshot. These were checked against the **live Agno docs MCP** on 2026-06-01.
> Agno is **not** installed on the host (containerized; python:3.11 image). **Re-verify each import
> inside the built `agno-app` image** once a version is pinned in `pyproject.toml`.

## Confirmed imports (exact)
```python
from agno.os import AgentOS                                   # AgentOS(base_app=app, on_route_conflict="preserve_base_app"); .get_app()
from agno.agent import Agent
from agno.team.team import Team                               # mode="route" (top) / "coordinate" (families)
from agno.tools import tool                                   # @tool(requires_confirmation=True) -> pause; resume continue_run()
from agno.tools.user_control_flow import UserControlFlowTools # structured-question intake
from agno.tools.mcp import MCPTools                           # one per server; AgentOS manages lifecycle; no reload
from agno.tools.mcp_toolbox import MCPToolbox                 # DB-fleet, toolset/tool filtering (v2.0.9)

# Context Providers (query_<id> / update_<id>; sub-agent per source)
from agno.context.mcp import MCPContextProvider               # read-only default -> query_mcp_<name>
from agno.context.workspace import WorkspaceContextProvider   # NOTE: NOT "Workspace" — full class name
from agno.context.gdrive import GoogleDriveContextProvider    # read-only query_gdrive; per Google account
from agno.context.database import DatabaseContextProvider     # sql_engine=analysis, readonly_engine=evidence (infra read/write split)
from agno.context.web import WebContextProvider               # (optional)

# Knowledge / DB
from agno.knowledge.knowledge import Knowledge                # Knowledge(vector_db=, contents_db=)  [confirm path in image]
from agno.vectordb.pgvector import PgVector, SearchType       # PgVector(..., search_type=SearchType.hybrid)
from agno.db.postgres import PostgresDb                       # contents_db / get_postgres_db
```

## Confirmed but pin in-image
- **LearningMachine** — real (`Learning Machines` + `Learning Stores`). Import path **NOT yet pinned**
  (handoff says `agno.learn`; docs page is `/learning/`). Confirm `from agno.learn import LearningMachine, LearningMode, ...`
  vs `agno.learning` in the image before wiring memory.
- **Learning stores = SIX, not five:** User Profile, User Memory, Session Context, Entity Memory,
  Learned Knowledge, **Decision Log** (decisions + reasoning, per-agent, auditing). Decision Log is a
  strong fit for the HITL/approval audit trail — consider enabling it.
- **Learning modes:** `Always`, `Agentic`, `Propose` — confirmed.

## Confirmed patterns
- AgentOS: "Bring Your Own FastAPI App" → `base_app=` + `on_route_conflict="preserve_base_app"`; `get_app()`.
- MCPTools within AgentOS: lifecycle auto-managed; **do not** use `reload=True` when MCPTools attached.
- Skeleton uses `from agno.os import AgentOS` + `agent_os.get_app()` (matches).

## Watch-outs
- Handoff loosely says "Workspace provider" → actual class is `WorkspaceContextProvider`.
- `FilesystemContextProvider` (handoff `agno.context.fs`) not yet confirmed in docs listing (saw slack/gdrive/
  database/web/workspace/mcp). Verify or use `WorkspaceContextProvider` for the codebase + a plain knowledge
  ingest for frozen docs.
- Skeleton default model = NVIDIA NIM/OpenRouter; handoff wants provider-agnostic + pinned Anthropic. Reconcile in Phase 1.
