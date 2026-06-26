# AGENTS.md — Universal Entry Point

> **This is the first file any agent (Claude Code, Codem, Hermes) reads.**
> Keep it short: universal context + navigation index. Details live one level
> deeper in each directory's `README.md`.

## Project

Pro se family-law evidence + analysis + legal-strategy platform on Agno AgentOS.
Evidence custody → parse → normalize → store → export. Analysis over a
bitemporal graph. AI Legal Team (to build).

## Stack

Agno 2.6.13 · PostgreSQL 18 (pg_duckdb + pgvector + PostGIS) · Neo4j + Graphiti
· LiteLLM gateway (Ollama Cloud primary) · Milvus vectors · SurrealDB operational
store · FastAPI base_app pattern.

## Repository Layout

> **Read each directory's `README.md` when you need details about that area.**

| Directory | What lives there | When to read its README |
|---|---|---|
| `agents/` | All agent + team constructors, context providers, instructions | Adding/changing an agent or team |
| `app/` | Server entrypoint, model factory, config | Starting the server, changing providers |
| `db/` | DB connections, knowledge engine, embeddings | DB/schema work, knowledge ingestion |
| `evidence/` | The evidence spine: custody, registry, normalize, store, parsers | Evidence pipeline work |
| `sql/` | Numbered PostgreSQL migrations | Schema changes |
| `docker/` | Dockerfiles for each service image | Container builds |
| `docs/` | Canon, ADRs, plans, wiki | Vision, decisions, roadmap |
| `evals/` | Agno eval cases (harness-first) | Testing agent behavior |
| `scripts/` | Format, validate, ingest, entrypoint | Dev workflow |
| `knowledge/` | Curated knowledge inputs (NEVER secrets) | Knowledge ingestion |

## Agent Topology

```
Root Router (mode=route)
+-- Platform Ops (mode=coordinate)
|   +-- ingestion_orchestrator
|   +-- analysis_orchestrator
|   +-- review_gatekeeper
+-- Builder (mode=coordinate)
|   +-- dev_copilot
|   +-- project_pal
|   +-- forensic_data_agent
+-- document_digest (conditional, GOOGLE_API_KEY)
```

See `agents/README.md` for the full agent roster, build instructions, and conventions.

## Model Provider Chain

Ollama (glm-5.1) → NVIDIA → Kimi → OpenRouter → Anthropic → OpenAI → Google → Groq.
First provider with valid credentials wins. Override via `DEFAULT_MODEL_PROVIDER`
or `<PROVIDER>_MODEL_ID`. See `app/settings.py` for full resolution rules.

## Development

Format/validation: `./scripts/format.sh` `./scripts/validate.sh` (host venv).
Tests: `pytest` + `python -m evals` (must run green — harness-first).
Containerized on VPS; never a host venv.

```bash
# VPS (ssh -i ~/.ssh/ovh debian@40.160.5.19), in ~/agno-mvp:
docker compose --profile graph --profile tools up -d --build
docker compose logs -f agentos-api
```

Code is volume-mounted (`.:/app`) → deploy = sync files + restart.

## Deploy Docs

For service topology, VPS access, and infrastructure see `docs/PROJECT_CANON.md`
(§8 Deployment) and `compose.yaml`.

## Further Reading

**IMPORTANT:** Before starting any task, identify which docs below are relevant
and read them first. Load the full context before making changes.

- `docs/PROJECT_CANON.md` — vision, locked decisions, roadmap, gotchas
- `docs/EVIDENCE_MERGE_MAP.md` — code inventory across all three corpora
- `docs/BUILD_PLAN.md` — forward plan (phases A–E)
- `docs/REPO_STRUCTURE.md` — where every kind of file goes
- `docs/CONVENTIONS.md` — coding style, tool contract, docstring standards
- `docs/HANDOFFS.md` — agent-executable task units
- `docs/DEBT.md` — active stubs and known debt
- `docs/adr/` — 28 Architecture Decision Records

Tool-specific setup (hooks, slash-commands) lives in that tool's own config,
never in these authoritative docs.
