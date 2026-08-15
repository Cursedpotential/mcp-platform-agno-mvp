# Temporal Evidence and Agent Experience Platform

> _Byline: Claude Code · Sonnet 5 · 2026-08-09 (docs/registers true-up — plan-link fix;
> drift-fix 2026-08-12 Claude Code · Kimi K3: stack line LiteLLM→Portkey/Weaviate per ADR-0040/0042; deploy section marked pre-4-box)_
> _Current-entry-point repair: Codex · GPT-5 · 2026-08-15._

A pro se family-law evidence, analysis, and legal-strategy platform. The current backend
runs through an **Agno 2.8.7 / AgentOS adapter**; the accepted target is a
**framework-neutral platform API and custom Workbench**. Agno remains available during
the strangler migration and is not yet retired. AG2 is a bounded coordination candidate,
not the approved replacement.

> **Start here:** [`docs/PROJECT_CANON.md`](docs/PROJECT_CANON.md) — the durable source of
> truth (vision, decisions, roadmap, access, gotchas). Orientation for agents:
> [`AGENTS.md`](AGENTS.md). Current document map: [`docs/INDEX.md`](docs/INDEX.md).
> Decisions: [`docs/adr/`](docs/adr/). Active plan:
> [`docs/BUILD_PLAN.md`](docs/BUILD_PLAN.md). Debt register: [`docs/DEBT.md`](docs/DEBT.md).

## The three-part arc
1. **Evidence** — custody (sha256 + manifest) → parse → normalize → store → court-ready export,
   over a polyglot tool mesh (named workflows per evidence type + composable atomic tools).
2. **Analysis** — multi-pass psychological/abuse analysis over a **bitemporal** graph; the
   delta between the contemporaneous read and full-disclosure read is the abuse made legible.
3. **AI Legal Team** — agents (ported from the owner's Gemini Gems personas) that turn the
   processed evidence + knowledge base into strategy, motions, and filings.

## Current runtime and accepted target

| Concern | Current | Accepted target |
|---|---|---|
| Runtime | Agno/AgentOS adapter and existing agent teams | Framework-neutral contracts with adapter-by-adapter cutover |
| Product UI | Custom Next.js/FastAPI Workbench, expanding locally | Workbench is the primary product; no AgentOS clone |
| Knowledge | One canonical ingest plane, including locally built Knowledge browsing | Ingest everything once; apply horizon limits only when agents retrieve/replay |
| Semantics | Semantica wiring is configuration-only | Semantica VIP service; its findings may remain governed candidates |
| Memory | Existing Graphiti reads/writes are incomplete | PostgreSQL belief-event authority with per-run Graphiti projection |
| Models/workspace | Portkey plus existing OpenCode Copilot integration | Request-scoped provider routes plus persistent OpenCode control and isolated jobs |

Current infrastructure includes PostgreSQL 18 (pg_duckdb + pgvector + PostGIS, dual
evidence/analysis schema) · Neo4j + Graphiti (bitemporal temporal graph) · Portkey model
gateway (Ollama Cloud primary, NVIDIA embed/rerank/backup; LiteLLM RETIRED 2026-07-29,
ADR-0042) · Weaviate vectors (locked ADR-0040) · OpenCode · Cloudflare R2 (blob storage)
· isolated agent sandbox · Kasm desktop · n8n (separate server). See the canon for the
verified service map; working-tree features are not implied to be deployed.

## Develop

Python development is `uv`-managed on the workstation; do not use bare
`python`, `pip`, or `pytest`. The authoritative commands are in `AGENTS.md`:

```bash
uv run ruff check server tests
uv run ruff format --check server tests
uv run mypy server
uv run pytest -q
```

Go work under `vendored/sbv` requires the `fts5` build tag; use its Makefile
targets. Root `compose.yaml` is mirrored to the VPS and is production-facing,
not a disposable local-only stack. Deployment runs through the current Coolify
fleet and requires explicit owner review; do not infer a deploy from a local
build or documentation change.
