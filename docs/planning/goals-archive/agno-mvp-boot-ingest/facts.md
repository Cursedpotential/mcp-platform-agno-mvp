# Facts — Agno MVP: Boot + Transcript Context Ingestion

> **Critical distinction:** The chat transcripts feed the **Agno Knowledge base** (pgvector RAG — what agents query for context). They do NOT go into the `evidence` database. The `evidence` schema is a read-only protected store for case evidence; it is created by the SQL migrations but not populated or used in this goal. Evidence processing is a follow-on goal.

---

## Compose / Boot

1. `docker compose up -d --build` starts all services cleanly with no errors. [auto]
2. The agno-app service is reachable at http://localhost:8000 and `/docs` returns HTTP 200. [auto]
3. n8n is in compose.yaml and accessible at http://localhost:5678 after boot. [auto]
4. Cloudflare R2 is mounted into agno-app at `/r2` via rclone volume (the §17 blob landing zone).
5. The agno-app container does NOT use `--reload` (it breaks the MCP lifespan). [auto]

## AgentOS Wiring

6. `app/main.py` uses `AgentOS(base_app=fastapi_app)` + `get_app()` — no subpath mount. [auto]
7. All API requests enter through `agents["router"]` (mode="route"); a Platform Ops prompt routes to the Platform Ops team, not the Builder team. [auto]

## Database

8. SQL migrations (`sql/0001_init_extensions.sql`, `sql/0002_schema.sql`) apply on first `docker compose up`; `agent_run`, `approval_request`, `evidence_hash`, and `transcript_insight` tables exist with `uuidv7()` PKs. [auto]
9. A database connection with `default_transaction_read_only=on` pointed at the `evidence` schema rejects INSERT/UPDATE/DELETE. [auto]
10. When a native-confirm tool pauses a run, the resulting `approval_request` row has a non-null `run_id` that maps back to the Agno run. [auto]

## Context Providers

11. `agents/providers.py` builds a `PlatformContext` object with `source_tools`, `code_tools`, `readonly_db_tools`, `drive_read_tools`, and `drive_write_tools` populated (cloud lists may be empty if Drive/OneDrive MCP servers are not running). [auto]
12. The `DatabaseContextProvider` read sub-agent (readonly_engine → evidence) cannot invoke write tools at the infrastructure level. [auto]

## Memory

13. LearningMachine is wired with PROPOSE mode for Entity Memory and Learned Knowledge; a proposed learning surfaces a human-confirm step rather than writing automatically.

## Knowledge / Ingestion

14. `knowledge/platform/conversations/` directory exists and is the documented drop zone for hand-selected transcript files. [auto]
   - Note: this feeds the agent Knowledge base (RAG context), not the evidence database.
15. `scripts/ingest_knowledge.py` calls `knowledge.ainsert(name=, path=, metadata=)` for each accepted file — not a print stub. [auto]
16. Embeddings use NVIDIA NIM (`nv-embedqa-e5-v5`, 1024-d) — no `OPENAI_API_KEY` required. Reranking uses NVIDIA NIM (`nv-rerankqa-mistral-4b-v3`). Both are configured in `db/session.py` via `NVIDIA_API_KEY` only.
17. `docker exec -it agentos-api python -m agents.ingestion` completes without import errors and reports the number of documents indexed. [auto]

## Acceptance / Done Condition

18. An agent (routed through the Builder team → Dev Copilot) answers a question about the evidence platform architecture using content from the ingested transcripts — the answer references specific context from those files, not just generic knowledge.
19. The platform boots and agents respond when `NVIDIA_API_KEY` is set (NVIDIA NIM); it also works when `OLLAMA_API_KEY` or `OLLAMA_HOST` is set (Ollama Cloud/local) — no hardcoded model default.
20. `example.env` documents all variables needed to boot: NVIDIA/Ollama keys, DB vars, HITL vars, n8n vars, R2 vars — and notes the embeddings key requirement.
