@.claude/recall-context.md

# AGENTS.md — orientation for any agent (Claude Code, Codex, others)

> Source of truth for working in this repo. `CLAUDE.md` symlinks here.
> **Read [`docs/PROJECT_CANON.md`](docs/PROJECT_CANON.md) first** — it holds the full
> vision, decisions, roadmap, access, and gotchas and survives compaction.
>
> **Document Contract (one authoritative file per concern — CANON §0):** before any task,
> read the canon + the relevant doc:
> [`EVIDENCE_MERGE_MAP.md`](docs/EVIDENCE_MERGE_MAP.md) = what code exists / where (inventory) ·
> [`BUILD_PLAN.md`](docs/BUILD_PLAN.md) = what to build next (plan) ·
> [`REPO_STRUCTURE.md`](docs/REPO_STRUCTURE.md) = where files go (structure) ·
> [`CONVENTIONS.md`](docs/CONVENTIONS.md) = how to write code (style).
> If docs conflict, CANON §5 Locked Decisions wins; update the others in the same change.

## What this is
A pro se family-law (custody) **evidence + analysis + legal-strategy platform** on
Agno AgentOS. Three-part arc: **Part 1 Evidence** (custody→parse→normalize→store→export),
**Part 2 Analysis** (multi-pass psychological/abuse analysis over a bitemporal graph),
**Part 3 AI Legal Team** (ported from the owner's Gemini Gems → strategy, motions, filings).
It bootstraps itself: the Builder agents help stand up the rest of the platform.

## Architecture (current)
Root **Router** (`mode=route`) → three coordinate families:
- **Platform Ops** — Ingestion / Analysis Orchestrators + Review Gatekeeper (evidence pipeline)
- **Builder** — Dev Copilot / Project PAL / Forensic Data (builds the platform)
- **AI Legal Team** — *to build* (Part 3)

Plus standalone Document Digest (Gemini long-context). Stack (8 services on the OVH VPS,
profiles default/`tools`/`graph`/`desktop`): `agentos-db` (PG18 + pg_duckdb + pgvector +
PostGIS), `agentos-api` (AgentOS base_app), `platform-tools` (SBV + tools-facade),
`agent-sandbox` (isolated exec), `gateway` (LiteLLM + OpenCode), `neo4j` + `graphiti-mcp`
(bitemporal graph), `desktop` (Kasm). n8n is on a separate Tailscale-linked server.
Full detail + access in `docs/PROJECT_CANON.md`.

## Key files
| File | Purpose |
|---|---|
| `app/main.py` | AgentOS entrypoint (base_app pattern, router, HITL + knowledge routes, lifespan) |
| `app/settings.py` | provider-agnostic model factory (Ollama-first) |
| `agents/factory.py` | `build_agent_team(ctx)` — teams, agents, HITL tools |
| `agents/providers.py` | Context Providers → `PlatformContext`; `build_learning()`; Graphiti MCP |
| `db/session.py` | `get_postgres_db`, `create_knowledge`, `ensure_duckdb_r2_secret` |
| `db/embedder.py` | `NimEmbedder` (asymmetric query/passage) · `db/reranker.py` `NvidiaReranker` |
| `evidence/` | *(building)* the polyglot evidence spine (custody/registry/workflows/normalize/store/export) |
| `compose.yaml` | the whole stack |

## Conventions
**Full style guide → [`docs/CONVENTIONS.md`](docs/CONVENTIONS.md).** Highlights:
- **Byline on EVERY artifact** (doc + code): `tool/platform · model · date` (e.g. `Claude Code · Opus 4.8 · 2026-06-13`). Markdown → line under the title; code → top comment. Multi-tool workflow needs per-artifact provenance.
- **No stubs** unless unavoidable → mark `# STUB:` + register in `docs/DEBT.md` (ADR-0021).
- **Harness-first tests**: `pytest` + `python -m evals` must run green.
- **HITL is first-class**: every write pauses for recorded approval (ADR-0002/0019).
- **Atomic-tool contract**: one capability per module in `evidence/tools/`, self-registering; everything normalizes to `NormalizedRecord`. New capabilities = atomic tool or MCP service behind Agno, **never a forked architecture** (see `REPO_STRUCTURE.md`).
- **Decisions get ADRs** (`docs/adr/`, supersede don't edit) **and** update `PROJECT_CANON.md` §5 same change. Active plan: `plans/`; forward sequencing: `docs/BUILD_PLAN.md`.
- **agno 2.6.13 gotchas** and stack quirks: see `docs/PROJECT_CANON.md` §8.
- **Never ingest** `Secrets/` or case-data dirs into Knowledge. Secrets live in gitignored `.env`.

## Dev loop (containerized — never a host venv)
```bash
# on the VPS (ssh -i ~/.ssh/ovh debian@40.160.5.19), in ~/agno-mvp:
docker compose --profile graph --profile tools up -d --build
docker compose logs -f agentos-api
```
Code is volume-mounted (`.:/app`) → deploy = sync files + `docker compose ... up -d`/`restart`.
Format/validate on a host venv: `./scripts/format.sh`, `./scripts/validate.sh`.

## Where to look
- Vision/decisions/roadmap/access/gotchas → `docs/PROJECT_CANON.md`
- **Inventory** (what code exists across the 3 corpora, best version, tool catalog) → `docs/EVIDENCE_MERGE_MAP.md`
- **Forward plan** (phases A–E) → `docs/BUILD_PLAN.md` · **structure** → `docs/REPO_STRUCTURE.md` · **style** → `docs/CONVENTIONS.md`
- Decision records → `docs/adr/` (index in `docs/adr/README.md`) · Live stub/debt → `docs/DEBT.md`
- Build **history** (superseded for forward work) → `docs/planning/` ; active working plan → `plans/`
- Mined reusable code → `../extracted-code/` (MANIFEST.md); **read-only donor archives** → `../dev-resources/Archives/` (dial-stack, chatminer)
