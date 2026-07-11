# DECISION LOG — Agno-MCP-Platform

> _Byline: Claude Code · Fable 5 · started 2026-07-09 (2026-07-10 entries: Claude Opus 4.8)_
> **Running, append-only design/decision log.** Every load-bearing decision lands here with
> date, lane, rationale, and status — a fast scan of "why is it this way?" without digging
> through chat. Complements (does not replace) the formal `docs/adr/` ADRs: when a decision is
> big/contested enough to need alternatives-considered and supersession, promote it to an ADR
> and link it here. **Append; strike (~~…~~) when reversed, don't delete.** Newest on top.

Lanes: **A** = restructure · **B** = ingestion/table redesign · **C** = infra/gateway. See
`docs/COORDINATION.md` for lane ownership and the live-status ledger.

---

## 2026-07-10

| # | Decision | Lane | Status | Rationale / notes |
|---|---|---|---|---|
| D-029 | **AGENTS.md progressive-disclosure reconfiguration** — root `AGENTS.md` rewritten as a concise map of the real `server/*` layout + 5 nested `AGENTS.md` drill-downs (`server/`, `server/tools/`, `server/evidence/`, `server/agents/`, `server/contracts/`) | — | done | Root `AGENTS.md` still described the pre-ADR-0033 flat-package layout (`agents/`, `app/`, `db/`, `evidence/`) and promised per-directory `README.md` files that never existed — the progressive disclosure it advertised didn't exist. Closest-file-wins nesting now backs that promise for real. Doc-only, gates re-verified green. |
| D-028 | **Facade-collapse premise DISPROVEN — the facade STAYS; Batches B/C are MOOT** | A/C | corrected | `docs/planning/facade-collapse-plan.md`'s core premise — that `agno`'s `enable_mcp_server` re-exports granular `@tool` functions over `agentos-mcp`, letting ContextForge repoint there and the facade be removed — is false: verified from agno source (`agno/os/app.py:588-595`), AgentOS's MCP surface exposes only ~19 AgentOS *operations*, never the parser/SBV `@tool`s. Batch A (G4 gateway + SBV toolkit as agno `@tool`s) shipped anyway (useful on its own); Batches B/C do not proceed. All 14 facade tools instead registered directly in ContextForge as REST tools (5th virtual server `platform_tools`, alongside `agno`/`coolify`/`graphiti`/`exa`). rel: `docs/planning/facade-collapse-plan.md` (superseded banner), `docs/COORDINATION.md` FACADE COLLAPSE entry. |
| D-027 | **ADR-0035 Option A — record contract's home is `server/contracts/records.py`, not `server/core/`** | A | done | Owner initially picked "promote to `server/core/records.py`" (the literal reading of "promote out of evidence"), but `server/core/__init__.py` eagerly imports `server.core.session` (sqlalchemy/agno/duckdb) — routing the record contract through it would FATAL-loop the dep-light `docker/tools` facade the moment any parser imports it (the same failure class as the 2-day ADR-0033-era outage). `server/contracts/` is a new, deliberately import-light package created to be facade-safe by construction; `server/contracts/__init__.py` stays dependency-free. `server/evidence/normalize.py` kept as a deprecated re-export shim (nothing deleted). Also executed same-ADR: `server/evidence/tool_finder/` → `server/tools/gateway/`; `server/tools/` sub-namespaced into `parsers/{messaging,ai_chat,generic}/` + `extractors/`; registry discovery switched `pkgutil.iter_modules` → `pkgutil.walk_packages` (recursive). Merged `main` (`8240205`), deployed, verified (facade `/health` 23 tools). Gates green: ruff/mypy/pytest 208. rel: ADR-0035 (supersedes/relates ADR-0033). |

## 2026-07-09

| # | Decision | Lane | Status | Rationale / notes |
|---|---|---|---|---|
| D-026 | **tools + registry moved out of evidence to `server/tools/` (cross-domain capability layer)** | A | done | Tools are cross-domain: evidence/analysis/agents/workflows/CLI all consume them, so they don't belong nested under the evidence spine. `git mv server/evidence/tools server/tools`; `git mv server/evidence/registry.py server/tools/registry.py`; ~150 import-statement + string-path substitutions across `.py`/tests/facade; the two near-identical auto-discovery loops in `registry.py` collapsed into one, made package-name-agnostic (`__package__`, not hardcoded); intra-package imports (`registry`, `_common`, `_chatminer_adapter`, sibling parsers) converted to relative imports. Also fixed a live mount regression: `compose.yaml`/`compose.exec.yaml` mounted `./evidence:/opt/tools/evidence:ro` (a dir that no longer exists post-ADR-0033, so the tools facade served zero parsers) → now mounts the WHOLE `server/` tree (`./server:/opt/tools/server:ro`, not just `server/tools/`, because `server.tools.*` has real transitive deps on `server.evidence.normalize` + `server.vendored.chatminer`, both lightweight); `docker/tools/tools/facade.py` imports plain `server.tools.registry`/`server.tools._sbv_client`, same path as the main app. Verified (outside the repo's own venv, which has `server` editable-installed and would mask this) with an isolated-Python simulation of the container's actual import graph — `load_builtin_tools()` returns all 23 tools. Gates GREEN: ruff clean, mypy clean, **pytest 186**. rel: ADR-0033. |
| D-025 | **Repo repack = Option A** (full `server/{api,core,agents,evidence,analysis,vendored/chatminer}` + `ui/` + `shared/`) | A | **EXECUTED on branch, gated** | Mirror the prior iteration's one-backend-boundary discipline; current 8 flat sibling packages are historical drift. Alternative B rejected. **ADR-0033 authored.** Done 2026-07-09 via `scripts/repack_to_server_layout.py` (152 files, 240 import rewrites, path-depth + string-module + config-split fixes); gates GREEN: ruff clean, mypy 106 files, **pytest 186**. `podman build` proof + merge DEFERRED (owner to config podman later; merge auto-deploys exec tier). `REPO_STRUCTURE.md` updated. |
| D-024 | **Repack runs as a one-window RUNBOOK, not a branch/drive-by** | A | standing | Merging `main` auto-deploys the exec tier (D-011); repack moves ~200 import sites + the uvicorn entrypoint + Dockerfile COPY paths, so it needs a keyboard-present window with a local `docker build` proof and Lane C watching the redeploy. A long-lived branch would rot against B's `.py` + C's `docker/` edits. |
| D-023 | **UI / G1 DEFERRED; decoupled from the repack** | A | decided | Don't race the CopilotKit shell. Repack proceeds on its own coordinated schedule; G1 is no longer sequenced "before/after" it. |
| D-022 | **`shared/` deferred** — create only when `ui/` needs shared types | A | decided | Consistent with deferring UI; avoid a speculative empty package. |
| D-021 | **`visualizations/` → `docs/visualizations/`** | A | **done** | Q1. Not a product surface; belongs with docs. |
| D-020 | **`configs/` → `docker/milvus/`, `deploy/n8n/` → `docker/n8n/`** | A | **done** | Q3. DEPLOY-NEUTRAL: compose mounts Milvus configs from absolute VPS host paths (`/data/agno/config/milvus/…`); repo copy is only the scp source (comment repointed). ⚠ Lane C to confirm n8n isn't deployed from the old path. rel: ADR-0007 (n8n+R2), ADR-0026/0027 (Milvus). |
| D-019 | **Process rule:** an open question leaves the annotate list the moment it's acted on | A | standing | Fix for the `.planning/build` / venv ghost-question confusion (owner: "you asked me to review a folder you already moved"). Spec split into 4a DONE / 4b genuinely-open. |
| D-018 | **`.planning/build/` = LIVE architecture directives** → `docs/planning/architecture-directives/` (+ INDEX.md) | A | done | Owner: "most of that was good directives." ContextForge/SurrealDB/DNS/Traefik/topology; reconcile against live infra, do NOT `_stale`. |
| D-017 | **Multi-chat war room** = `docs/COORDINATION.md` (Lane A/B/C, append-only ledger) | A | standing | Three chats work the repo concurrently; shared ledger prevents collisions. |

## 2026-07-08

| # | Decision | Lane | Status | Rationale / notes |
|---|---|---|---|---|
| D-016 | **Seed reconciliation RESOLVED — no action** | A | closed | Live ontology (164 cat / 527 pat) == exact `0007` prefix of the committed chain `0006+0007+0008`; `evidence/patterns.py` OntologyChain validator OK; P2.1 corpus fully homed (0 missing). Earlier "drift 153→164" read used the wrong baseline (0006 alone) — withdrawn. |
| D-015 | **Ontology = a migration CHAIN validated by `evidence/patterns.py`**; P2.1 parallel-tables approach superseded | A/B | standing | Invariant: "live == a prefix of the committed chain" detects both data loss and uncaptured drift. 4 `contradiction_rules` remain unhomed pending a table decision (B). rel: ADR-0018 (bitemporal evidence), ADR-0031 (entity layer). |
| D-014 | **Live PG data + ingestion/detection LOGIC FROZEN** until the Lane-B brainstorm lands | B | frozen | Structure work moves code only; behavior identical. |
| D-013 | **Sealed-lexicon rule:** committed seeds keep `[REDACTED:*]` placeholders only; real values load out-of-band, never git | A/B | standing | Court-safety (0006 rule). Read-only dumps → gitignored `live-dumps/`. rel: ADR-0018 (disclosure tier). |
| D-012 | **Tier 0/1 hygiene** — delete dead venvs (~577 MB, regenerable so never-delete N/A); recall fragments → `../_stale/`; `goals/`+`.planning/`+`plans/` → `docs/planning/` | A | done | — |
| D-011 | **exec-tier Coolify app deploys from `main`** (repointed from `hotfix/agent-ui-lockfile`) | C | standing | ⚠ Any merge to `main` auto-redeploys exec tier (+ webhooked coolify-mcp/portkey/data-* apps). Keep `docker/` config paths stable. rel: ADR-0009 (deploy on OVH), ADR-0016 (tool containers). |
| D-010 | **`embed-text` MUST stay `nvidia/nv-embed-v1` (4096-d symmetric)** | C | standing | Graphiti Neo4j graph is embedded at 4096-d; any dim change breaks vector search (bit us twice). Do not swap in asymmetric embedqa models. rel: ADR-0011 (NIM embedder dimension contract), ADR-0010 (two-collection embedding), ADR-0014 (Neo4j+Graphiti). |
| D-009 | **Repointing a Coolify app hotfix→main surfaces every hotfix-only file main lacked** (audit first) | C | lesson | Seven hotfix-only pieces (agent-ui Dockerfile, `app/mcp_main.py`, agentos-mcp compose svc, `fastmcp` install, …) caused staged crashloops; also the FastMCP host-header 421 bug (same as graphiti). |

## Carried context (decided in prior sessions / other lanes)

| # | Decision | Lane | Notes |
|---|---|---|---|
| D-008 | **DB schema RESTART**; hash placement = **Option A** (h1/h2/h3 custody hashes as COLUMNS per row) | B | Initial ingestion schema dead; 6 per-source RAW tables + `file_custody` anchor; ingest lands raw, no transform. DRAFT until owner approves live. rel: ADR-0018 (bitemporal/custody), ADR-0029 (dedicated ingestion). |
| D-007 | **Prior GitHub iterations are the design SoT** — honor, don't re-invent | B | Iterations index → `D:/casebible/iterations_index.duckdb` (~2080 artifacts). |
| D-006 | **ContextForge = the MCP tool gateway; LiteLLM/Portkey = the model gateway** (distinct layers) | C | CF v1.0.4 live; 4 virtual servers (agno/coolify/graphiti/exa); coolify-write is a separate write cluster from the hosted read-only bundle. rel: ADR-0025 (gateway topology), ADR-0023 (universal API+MCP), ADR-0015 (LiteLLM). |
| D-005 | **Swarm network REJECTED** by owner | C | (was floated during the CF upgrade chat.) |
| D-004 | **Auto-memory canonical store = the PARENT workspace dir**; teleport/subdir sessions sync up first | — | `memory-parent-dir-canonical`. Subdir `MEMORY.md` is a redirect pointer. |
| D-003 | **TheBigOne = donor dump** (prior iterations + un-integrated tools/schemas) — mine, never build there | — | — |
| D-002 | **Never trim memory lossily** to hit a size target — merge preserving all facts/refs | — | Owner rule. |
| D-001 | **Rotate the Cloudflare GLOBAL API key** (leaked in old repos, redacted 2026-07-04) | owner | ⏳ OPEN — only the owner can rotate. |

---

**ADR convention (owner rule — always note when applicable):** every entry is checked against
`docs/adr/`. Use `rel: ADR-NNNN` for an existing ADR that governs/relates to the decision;
use `→ author ADR-NNNN` when the decision is architecturally significant and needs its own ADR
(then create it and keep the ref). A decision with no applicable ADR is fine — but the check
is mandatory, not optional.
