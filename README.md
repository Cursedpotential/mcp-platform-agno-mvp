# Agno MCP Platform — Evidence, Analysis & Legal-Strategy

> _Byline: Claude Code · Sonnet 5 · 2026-08-09 (docs/registers true-up — plan-link fix)_

A pro se family-law (custody) **evidence-processing, analysis, and legal-strategy
platform** built on **Agno AgentOS** (FastAPI + PostgreSQL). Everything runs on the
owner's infrastructure, behind HITL approval, with evidence held under chain-of-custody.

> **Start here:** [`docs/PROJECT_CANON.md`](docs/PROJECT_CANON.md) — the durable source of
> truth (vision, decisions, roadmap, access, gotchas). Orientation for agents:
> [`AGENTS.md`](AGENTS.md). Decisions: [`docs/adr/`](docs/adr/). Active plan:
> [`docs/BUILD_PLAN.md`](docs/BUILD_PLAN.md). Debt register: [`docs/DEBT.md`](docs/DEBT.md).

## The three-part arc
1. **Evidence** — custody (sha256 + manifest) → parse → normalize → store → court-ready export,
   over a polyglot tool mesh (named workflows per evidence type + composable atomic tools).
2. **Analysis** — multi-pass psychological/abuse analysis over a **bitemporal** graph; the
   delta between the contemporaneous read and full-disclosure read is the abuse made legible.
3. **AI Legal Team** — agents (ported from the owner's Gemini Gems personas) that turn the
   processed evidence + knowledge base into strategy, motions, and filings.

## Stack
AgentOS (router + 3 agent families) · PostgreSQL 18 (pg_duckdb + pgvector + PostGIS, dual
evidence/analysis schema) · Neo4j + Graphiti (bitemporal temporal graph) · LiteLLM gateway
(Ollama Cloud primary, NVIDIA embed/rerank/backup) · OpenCode · Cloudflare R2 (blob storage)
· isolated agent sandbox · Kasm desktop · n8n (separate server). Deployed on an OVH VPS;
linked by Tailscale. See the canon for the full service map and access.

## Develop
Containerized — never a host venv. On the VPS (`ssh -i ~/.ssh/ovh debian@40.160.5.19`,
`~/agno-mvp`):
```bash
docker compose --profile graph --profile tools up -d --build
```
Code is volume-mounted, so deploy = sync files + `docker compose ... up -d`/`restart`.
Tests: `pytest` and `python -m evals` (harness-first; must run green). Format/validate:
`./scripts/format.sh`, `./scripts/validate.sh`.
