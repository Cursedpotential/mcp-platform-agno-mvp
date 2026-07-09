# DECISION LOG — Agno-MCP-Platform

> _Byline: Claude Code · Fable 5 · started 2026-07-09_
> **Running, append-only design/decision log.** Every load-bearing decision lands here with
> date, lane, rationale, and status — a fast scan of "why is it this way?" without digging
> through chat. Complements (does not replace) the formal `docs/adr/` ADRs: when a decision is
> big/contested enough to need alternatives-considered and supersession, promote it to an ADR
> and link it here. **Append; strike (~~…~~) when reversed, don't delete.** Newest on top.

Lanes: **A** = restructure · **B** = ingestion/table redesign · **C** = infra/gateway. See
`docs/COORDINATION.md` for lane ownership and the live-status ledger.

---

## 2026-07-09

| # | Decision | Lane | Status | Rationale / notes |
|---|---|---|---|---|
| D-025 | **Repo repack = Option A** (full `server/{api,core,agents,evidence,analysis,vendored/chatminer}` + `ui/` + `shared/`) | A | **locked** | Mirror the prior iteration's one-backend-boundary discipline; current 8 flat sibling packages are historical drift. Alternative B (8→5, no `server/`) rejected: captures domain separation but not the one-boundary win. |
| D-024 | **Repack runs as a one-window RUNBOOK, not a branch/drive-by** | A | standing | Merging `main` auto-deploys the exec tier (D-011); repack moves ~200 import sites + the uvicorn entrypoint + Dockerfile COPY paths, so it needs a keyboard-present window with a local `docker build` proof and Lane C watching the redeploy. A long-lived branch would rot against B's `.py` + C's `docker/` edits. |
| D-023 | **UI / G1 DEFERRED; decoupled from the repack** | A | decided | Don't race the CopilotKit shell. Repack proceeds on its own coordinated schedule; G1 is no longer sequenced "before/after" it. |
| D-022 | **`shared/` deferred** — create only when `ui/` needs shared types | A | decided | Consistent with deferring UI; avoid a speculative empty package. |
| D-021 | **`visualizations/` → `docs/visualizations/`** | A | **done** | Q1. Not a product surface; belongs with docs. |
| D-020 | **`configs/` → `docker/milvus/`, `deploy/n8n/` → `docker/n8n/`** | A | **done** | Q3. DEPLOY-NEUTRAL: compose mounts Milvus configs from absolute VPS host paths (`/data/agno/config/milvus/…`); repo copy is only the scp source (comment repointed). ⚠ Lane C to confirm n8n isn't deployed from the old path. |
| D-019 | **Process rule:** an open question leaves the annotate list the moment it's acted on | A | standing | Fix for the `.planning/build` / venv ghost-question confusion (owner: "you asked me to review a folder you already moved"). Spec split into 4a DONE / 4b genuinely-open. |
| D-018 | **`.planning/build/` = LIVE architecture directives** → `docs/planning/architecture-directives/` (+ INDEX.md) | A | done | Owner: "most of that was good directives." ContextForge/SurrealDB/DNS/Traefik/topology; reconcile against live infra, do NOT `_stale`. |
| D-017 | **Multi-chat war room** = `docs/COORDINATION.md` (Lane A/B/C, append-only ledger) | A | standing | Three chats work the repo concurrently; shared ledger prevents collisions. |

## 2026-07-08

| # | Decision | Lane | Status | Rationale / notes |
|---|---|---|---|---|
| D-016 | **Seed reconciliation RESOLVED — no action** | A | closed | Live ontology (164 cat / 527 pat) == exact `0007` prefix of the committed chain `0006+0007+0008`; `evidence/patterns.py` OntologyChain validator OK; P2.1 corpus fully homed (0 missing). Earlier "drift 153→164" read used the wrong baseline (0006 alone) — withdrawn. |
| D-015 | **Ontology = a migration CHAIN validated by `evidence/patterns.py`**; P2.1 parallel-tables approach superseded | A/B | standing | Invariant: "live == a prefix of the committed chain" detects both data loss and uncaptured drift. 4 `contradiction_rules` remain unhomed pending a table decision (B). |
| D-014 | **Live PG data + ingestion/detection LOGIC FROZEN** until the Lane-B brainstorm lands | B | frozen | Structure work moves code only; behavior identical. |
| D-013 | **Sealed-lexicon rule:** committed seeds keep `[REDACTED:*]` placeholders only; real values load out-of-band, never git | A/B | standing | Court-safety (0006 rule). Read-only dumps → gitignored `live-dumps/`. |
| D-012 | **Tier 0/1 hygiene** — delete dead venvs (~577 MB, regenerable so never-delete N/A); recall fragments → `../_stale/`; `goals/`+`.planning/`+`plans/` → `docs/planning/` | A | done | — |
| D-011 | **exec-tier Coolify app deploys from `main`** (repointed from `hotfix/agent-ui-lockfile`) | C | standing | ⚠ Any merge to `main` auto-redeploys exec tier (+ webhooked coolify-mcp/portkey/data-* apps). Keep `docker/` config paths stable. |
| D-010 | **`embed-text` MUST stay `nvidia/nv-embed-v1` (4096-d symmetric)** | C | standing | Graphiti Neo4j graph is embedded at 4096-d; any dim change breaks vector search (bit us twice). Do not swap in asymmetric embedqa models. |
| D-009 | **Repointing a Coolify app hotfix→main surfaces every hotfix-only file main lacked** (audit first) | C | lesson | Seven hotfix-only pieces (agent-ui Dockerfile, `app/mcp_main.py`, agentos-mcp compose svc, `fastmcp` install, …) caused staged crashloops; also the FastMCP host-header 421 bug (same as graphiti). |

## Carried context (decided in prior sessions / other lanes)

| # | Decision | Lane | Notes |
|---|---|---|---|
| D-008 | **DB schema RESTART**; hash placement = **Option A** (h1/h2/h3 custody hashes as COLUMNS per row) | B | Initial ingestion schema dead; 6 per-source RAW tables + `file_custody` anchor; ingest lands raw, no transform. DRAFT until owner approves live. |
| D-007 | **Prior GitHub iterations are the design SoT** — honor, don't re-invent | B | Iterations index → `D:/casebible/iterations_index.duckdb` (~2080 artifacts). |
| D-006 | **ContextForge = the MCP tool gateway; LiteLLM/Portkey = the model gateway** (distinct layers) | C | CF v1.0.4 live; 4 virtual servers (agno/coolify/graphiti/exa); coolify-write is a separate write cluster from the hosted read-only bundle. |
| D-005 | **Swarm network REJECTED** by owner | C | (was floated during the CF upgrade chat.) |
| D-004 | **Auto-memory canonical store = the PARENT workspace dir**; teleport/subdir sessions sync up first | — | `memory-parent-dir-canonical`. Subdir `MEMORY.md` is a redirect pointer. |
| D-003 | **TheBigOne = donor dump** (prior iterations + un-integrated tools/schemas) — mine, never build there | — | — |
| D-002 | **Never trim memory lossily** to hit a size target — merge preserving all facts/refs | — | Owner rule. |
| D-001 | **Rotate the Cloudflare GLOBAL API key** (leaked in old repos, redacted 2026-07-04) | owner | ⏳ OPEN — only the owner can rotate. |

---

_When promoting an entry to a formal ADR, add `→ ADR-NNNN` in its row and keep the row._
