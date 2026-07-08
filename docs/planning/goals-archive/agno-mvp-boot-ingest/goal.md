# Goal: Agno MVP — Boot + Transcript Context Ingestion

## The Goal

Get the Agno MCP Platform (`Agno-MCP-Platform/`) to its first correctly-wired, running state, with AI transcript conversations about the evidence platform loaded as agent context — so an agent can answer grounded questions about the platform's own architecture and history using that context.

This is Goal 1 of 2. Goal 2 (use the context-loaded agents to drive the polyglot evidence processing platform build) follows from this.

## Scope

**In:**
- SQL migrations (extensions + dual-schema + audit tables with `run_id`)
- compose.yaml with n8n + R2 added; `--reload` removed
- `agents/providers.py` (Context Providers → `PlatformContext`)
- `app/main.py` rewrite (AgentOS `base_app` pattern, root router as entry point, no reload)
- LearningMachine wired with PROPOSE mode
- `knowledge/platform/conversations/` drop zone + working `agents.ingestion` script
- AgentOS built-in playground available at `http://localhost:8000/playground`
- Embedder resolved (NVIDIA NIM or OpenAI key requirement documented)
- `example.env` complete for all boot variables

**Out (next goal):**
- TS/Py MCP server vendoring (Phase 7 in EXECUTION_PLAN.md)
- Cloud cleanup (Drive/OneDrive) providers
- ChatMiner pipeline (Phase 10)
- Review Panel UI (Phase 13)
- Evals rewrite beyond import-clean

## Shared Understanding

→ See `goals/agno-mvp-boot-ingest/facts.md`

The facts make the critical distinction explicit: **transcript context goes into the Agno Knowledge base** (the pgvector RAG surface agents query). The `evidence` database is a separate, read-only protected store for case evidence — it exists in the schema but is NOT populated or used in this goal.

## Execution Plan

→ See `goals/agno-mvp-boot-ingest/plan.md`

Seven implementation steps in order:
1. SQL migrations
2. compose.yaml (n8n + R2 + remove --reload)
3. `agents/providers.py`
4. LearningMachine `build_learning()`
5. `app/main.py` rewrite
6. Knowledge drop zone + ingestion script
7. Grounded answer test (done condition)

Each step has a verification command. All verification runs inside the container (`docker exec`), never on the host.

## Key References

- `docs/planning/EXECUTION_PLAN.md` — compressed, agent-ready build guide with verified Agno imports and anti-patterns
- `docs/planning/VERIFIED_AGNO_API.md` — confirmed import paths (re-verify against pinned image)
- `agents/factory.py` — the reference implementation; do NOT rewrite it
- `agents/instructions.py` — the reference guardrails

## Done Condition

All 20 facts in `facts.md` pass. Specifically:

1. `docker compose up -d --build` starts all services (agno-app, agentos-db, n8n) cleanly.
2. AgentOS playground is accessible at `http://localhost:8000/playground`.
3. A Platform Ops prompt routes to the Platform Ops team; a Builder prompt routes to the Builder team.
4. `python -m agents.ingestion` indexes hand-selected transcript files with no errors.
5. The Dev Copilot agent answers a question about the evidence platform architecture citing specific content from the ingested transcripts.

---

Launch this goal with: `/goal goals/agno-mvp-boot-ingest/goal.md`
