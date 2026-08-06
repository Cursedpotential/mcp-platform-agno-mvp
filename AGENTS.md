# AGENTS.md — Universal Entry Point

> **This is the first file any agent (Claude Code, Codex, Gemini CLI, opencode) reads.**
> Keep it short: universal context + navigation index. **Closest file wins** — nested
> `AGENTS.md` files below override this one for their subtree; read the nested map
> before editing inside that directory.

## Project

Pro se family-law evidence + analysis + legal-strategy platform on Agno AgentOS.
Evidence custody → parse → normalize → store → export. Analysis over a
bitemporal graph. AI Legal Team (to build).

## WHY THIS EXISTS — the knowledge-horizon mechanism

**Read this before proposing anything about storage, retrieval, memory, agents, or
schema. It is the point of the project, and it is counter-intuitive enough that
designs which ignore it come out subtly wrong.** Full text:
`docs/PROJECT_CANON.md` §1. Owner, 2026-08-01: *"this is the single most important
aspect of this whole project."*

The platform reconstructs **how a person realizes they were abused**, by running the
same evidence past agents with **different knowledge horizons** and diffing them.

- **The ignorant agent** starts knowing nothing and walks forward, living events as
  they were actually discovered. Its horizon **advances at each step** — this is a
  walk over N horizons, not one query. Gaslighting works here, and only here.
- **The hindsight agent** sees everything at once, including facts acquired years later.
- **The delta between what those two agents experience IS the deceit, the manipulation,
  and the gaslighting** — "what you were led to believe vs what was true vs when you
  found out." That delta is the deliverable. Not a timeline; the delta.

**A "pass" is a knowledge horizon — a retrieval filter bound to an agent, NOT a table,
lane, or destination.** Owner, 2026-08-01: *"ultimately it's just a permissions thing,
and which agents have hindsight."* How many passes exist is a workflow decision.

Consequences that are easy to get wrong:

- **One store, filtered per agent.** Do NOT design parallel as-lived / hindsight
  stores. Everything is written once carrying `occurred_at` (valid time),
  `knowledge_time`, and `disclosure_tier` — live enum `ai.disclosure_horizon`
  (`contemporaneous` / `hindsight` / `discovered`) on `working.normalized_record`
  (~~`analysis.normalized_record`~~ until the 2026-08-02 schema split, sql/0014).
- **Extraction is not analysis.** Semantica may read everything; it forms no beliefs.
  The horizon discipline belongs at the AGENT layer, never the extraction layer.
- **Enforce the horizon as a PRE-filter in every store** — Postgres, Weaviate,
  Graphiti, Neo4j. Vector search is the main leak: embeddings have no sense of time,
  so a future document scores exactly as similar as a contemporaneous one. Filtering
  after top-k silently shrinks k, sometimes to zero, with no error.
  ⚠ **Weaviate-specific landmine (verified in agno 2.8.0 source, 2026-08-02):**
  agno's Weaviate adapter SILENTLY DROPS `agno.filters` FilterExpr lists
  (`log_warning` + `filters = None`) — only **dict filters**
  (`{"domain": ..., "disclosure_tier": ...}`) are applied. A horizon filter
  written as a FilterExpr passes tests on other vectordbs and applies ZERO
  filters in prod. Dict filters only, always, on Weaviate.
- **Contamination is silent.** One leaked future fact makes the ignorant agent merely
  *smarter*; nothing fails and the delta is quietly worthless.
- **Graphiti holds the ignorant agent's own accumulating belief state** as it walks —
  it is not a filtered copy of the evidence.

## Stack

Agno 2.8.0 · PostgreSQL 18 (pg_duckdb + pgvector + PostGIS) — **also the Agno
operational store** since the 2026-08-04 flatten (ADR-0043 decision 3) ·
Neo4j + Graphiti · Portkey gateway (Ollama Cloud primary; LiteLLM retired,
ADR-0042) · Weaviate vectors (locked ADR-0040, cutover pending — Milvus
sidelined) · ~~SurrealDB operational store~~ **SurrealDB parked read-only,
off the critical path** (ADR-0043; container still up on ovh-data, export at
`_stale/surreal-export-20260804` — only the owner deletes) · FastAPI
base_app pattern.

## Repository Layout

> Backend repacked under one `server/` boundary (ADR-0033); `server/tools/` is
> capability-sub-namespaced (ADR-0035). Progressive disclosure: this table
> tells you WHICH nested `AGENTS.md` to read before editing a subtree.

| Directory | What lives there | Nested map |
|---|---|---|
| `server/` | The whole backend (`server.*` imports), dependency direction | `server/AGENTS.md` |
| `server/contracts/` | Import-light `NormalizedRecord`/`RecordType` contract | `server/contracts/AGENTS.md` |
| `server/evidence/` | The evidence spine: custody, store, workflows, cli | `server/evidence/AGENTS.md` |
| `server/tools/` | Cross-domain parser/extractor/gateway registry | `server/tools/AGENTS.md` |
| `server/agents/` | Agent/team constructors, providers, `@tool` wrappers | `server/agents/AGENTS.md` |
| `server/api/`, `server/core/`, `server/analysis/` | Entrypoint/config, DB session/model factory, behavioral analysis | see `server/AGENTS.md` |
| `server/vendored/` | Third-party Python projects (chatminer, semantica) — not ours to lint | — |
| `vendored/` | Third-party **non-Python** projects we do actively develop — currently `vendored/sbv` (Go). Distinct from `server/vendored/`; both are real. | `vendored/sbv/DEVELOPMENT.md` |
| `workbench/` | Operator Workbench — `workbench/api` (FastAPI) + `workbench/web` (Next.js) | — |
| `sql/` | Numbered PostgreSQL migrations (`NNNN_name.sql`, never edit an applied one) | — |
| `docker/` | One folder per service image (`tools/`, `gateway/`, `postgres/`, ...) | — |
| `docs/` | Canon, ADRs, decision log, plans, wiki | `docs/PROJECT_CANON.md` |
| `tests/` | The pytest suite | — |
| `scripts/` | format/validate/ingest/entrypoint | — |

## Commands

| Task | Command |
|---|---|
| Lint | `uv run ruff check server tests` |
| Format check | `uv run ruff format --check server tests` |
| Typecheck | `uv run mypy server` |
| Test (default, unit) | `uv run pytest -q` |
| Test (one file) | `uv run pytest -q tests/test_<name>.py` |
| Integration tests (opt-in, live services) | `uv run pytest -m integration` |
| Go build/test (`vendored/sbv`) | `go build -tags fts5 ./...` / `go test -tags fts5 ./...` |

⚠ The `fts5` build tag is **mandatory** for `vendored/sbv`. A plain `go test ./...`
fails every DB-backed test with `no such module: fts5` — that is a missing build
tag, not a code defect. Use the `Makefile` targets, which set it for you.

All Python is `uv`-managed — never invoke a bare `python`/`pip`/`pytest`.

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

See `server/agents/AGENTS.md` for the roster and build conventions.

## Model Provider Chain

Ollama (glm-5.1) → NVIDIA → Kimi → OpenRouter → Anthropic → OpenAI → Google → Groq.
First provider with valid credentials wins. Override via `DEFAULT_MODEL_PROVIDER`
or `<PROVIDER>_MODEL_ID`. See `server/core/settings.py` for resolution rules.

## Further Reading

Before a non-trivial task, identify which of these are relevant and read them first:

- `docs/PROJECT_CANON.md` — vision, locked decisions, roadmap, gotchas
- `docs/REPO_STRUCTURE.md` — where every kind of file goes
- `docs/CONVENTIONS.md` — coding style, tool contract, docstring standards
- `docs/COORDINATION.md` — multi-chat lane ownership + live TODO ledger
- `docs/DECISION_LOG.md` — running append-only decision log (complements ADRs)
- `docs/adr/` — Architecture Decision Records (`docs/adr/README.md` = index)
- `docs/DEBT.md` — active stubs and known debt

Tool-specific setup (hooks, slash-commands) lives in that tool's own config, never here.

## Commit Attribution

AI commits carry: `Co-Authored-By: <agent name and model> <noreply@anthropic.com>`

## Claude-Reflect Learnings

<!-- Auto-generated by claude-reflect. Do not edit this section manually. -->

### Environment Setup
- Tailnet PG from the desktop needs `DB_HOST=100.91.190.107` (~~`100.119.96.29`~~ — PG moved to ovh-files 2026-08-02, wave 1 of the ovh-data retirement; app `data-pg-files`). The default host `agentos-db` still only resolves inside the compose network.
- VPS services bind `${BIND_IP}` (the box's tailnet IP), NOT loopback — on-box probes and SSH tunnels must target `100.72.169.40:<port>`, never `localhost:<port>` (a tunnel to VPS-localhost gets connection-refused).

### API Auth
- agentos-api: `authorization=False` in main.py only disables JWT — the `OS_SECURITY_KEY` bearer still gates every route (incl. `/knowledge/*`). Internal callers send `Authorization: Bearer $OS_SECURITY_KEY` (value in `~/.secrets/infra-access.md`).

### Deploy & Data-Tier Gotchas
- Coolify apps WITHOUT watch_paths redeploy on EVERY push to their branch — the whole data tier (pg/neo4j/graphiti/surreal/vector) bounced on every main merge until watch paths were scoped per-app (2026-07-21/22). New app = set watch_paths at creation, always.
- Milvus standalone boot: embedded etcd defaults (100ms heartbeat/1s election) + slow VPS disk = "etcdserver: leader changed" panic loop (exit 134). Fixed via milvus-coolify/embedEtcd.yaml heartbeat-interval 1000 / election-timeout 10000 (host copy: ovh-data /data/agno/config/milvus/embedEtcd.yaml, ro-mounted — edit host file and the next restart picks it up).
- After dropping a Milvus collection externally, RESTART agentos-api — agno's client caches the numeric collection ID and 500s with code=100 collection-not-found on the next insert.
- agno `Step.on_error` REALLY defaults to skip (docstring claims fail) — always set on_error="fail" explicitly or failed stages report run-completed.
- H3 custody chain: TWO constructions coexist and are BOTH correct (owner-verified 2026-08-01; the 2026-07-22 "correction" declaring the first WRONG was itself wrong). (a) **SBV Go chain** (vendored/sbv/CUSTODY.md + custody.go, test-proven): chain_0 = "" and chain_i = sha256(chain_{i-1} + "<LF>" + H2_i) — H1 never enters the fold. (b) **Case Bible chain** (live-verified, 1,918 links): genesis = H1, chain_i = sha256(prev_hex + h2_hex). Both currently share tag `h3-chain-v1`, which does NOT disambiguate — give them distinct tags before further chain writes.

### Control Surfaces
- os.agno.com free tier accepts the remote instance via localhost trickery: the browser does the connecting, so `ssh -i ~/.ssh/ovh -N -L 7777:100.72.169.40:8000 root@100.72.169.40` makes the platform "http://localhost:7777" — CORS already allows the os.agno.com origin. One-click launcher: `C:\Users\matts\bin\agentos-control.cmd` (Desktop shortcut "AgentOS Control Plane").

<!-- End claude-reflect section -->

### Session Learnings 2026-08-02
- Test data must never become canonical: design-phase ingests are disposable and re-runnable from originals; only reference.* and hand-labeled gold are precious. Wipe + re-ingest once the design settles (owner ruling; executed 2026-08-02).
- Config accepted ≠ feature working: agno accepted `EntityMemoryConfig(mode=PROPOSE)` for months and silently did nothing. Verify features via docs + an observed write, never via config acceptance.
- Custody canon tags name the exact construction: new H3 rows carry `h3-chain-sbv-genesisempty-v1`; legacy `h3-chain-v1` rows are read-only and disambiguated by writer (see docs/DECISION_LOG.md 2026-08-02).
- Remove a worktree when its branch merges — 13 stale ones hid an unmerged security fix. Quarantine untracked remnants before `--force` removal.
