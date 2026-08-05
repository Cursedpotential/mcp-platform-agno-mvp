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

## 2026-08-02

| # | Decision | Lane | Status | Rationale / notes |
|---|---|---|---|---|
| D-032 | **Studio's model picker is fed by the AgentOS `Registry`, NOT `GET /models`** | C | done | Owner-visible bug: the os.agno.com Studio picker offered one model. Root cause read from agno source (`agno/os/router.py::get_models`, byte-identical in 2.8.0 and 2.8.6): `/models` returns the DISTINCT models already **attached** to registered agents/teams — a usage report, not a catalog. All 6 agents + 3 teams share the one object `build_model()` returns, so the set collapses to 1. There is no config path into it, and growing it would mean attaching decoy agents to the roster the user sees. Docs give the supported path instead: Studio's agent builder shows "Model: select from registered models" (`/agent-os/studio/agents`) and the `Registry` is documented as the home for "model provider instances … that Studio depends on" (`/agent-os/studio/registry`), served at `GET /registry?resource_type=model`. So `AgentOS(registry=Registry(models=…))` is now built from the SAME verified list `AgentOSConfig.available_models` publishes (`server/api/config.yaml`, 37 probe-verified ids from `scripts/update_available_models.py`) — one source of truth, no roster pollution. New `server/core/model_registry.py`; `build_model()`/`_try_provider()`/`_model_id()` gained an optional exact-`model_id` argument (selection behaviour unchanged when omitted). **`/models` still returns 1 by design** — that is agno's documented semantics for that endpoint, not a residual bug. rel: `server/core/model_registry.py`, `server/api/main.py`, `tests/test_model_registry.py`. |

## 2026-07-29

| # | Decision | Lane | Status | Rationale / notes |
|---|---|---|---|---|
| D-031 | **ADRs 0036–0039 ACCEPTED** (DozerDB multi-DB isolation · Graphiti-MCP-via-ContextForge write-enabled · agents use graphiti-core natively · hosted structured-output extraction LLM) | C | done (acceptance; execution items open) | Owner "let's do it" 2026-07-29. Reality-checked before flipping: 0037's Streamable-HTTP blocker cleared by lived evidence (graphiti virtual server serving in ContextForge since ≤07-10, see D-028); 0039 already implemented in practice (nemotron guided-JSON 07-04, lane now Portkey per ADR-0042); 0038 consistent with ADR-0041's Agno-native orchestration ruling. Open execution items: DozerDB named-DB write verification + per-DB backups (0036), verify write surface + retire `:8071` no-auth door (0037). rel: ADR-0036..0039, canon §5 updated same change. |
| D-030 | **LiteLLM RETIRED — Portkey = THE model gateway** | C | done (docs; teardown pending) | Owner ruling 2026-07-29 (doc-patch pass). Portkey has carried Graphiti + exec-tier since 07-19 (11-provider failover, `docker/gateway/portkey/`); dual-gateway split-brain ends. Teardown of the LiteLLM container + OpenCode model-config remap = separate owner-gated task. → author ADR-0042 (created same change). Same pass also synced canon §5 to ADR-0040 (Weaviate locked, Milvus sidelined) + ADR-0041 (Memgraph additive), fixed agno 2.6.13→2.8.0 current-state refs (AGENTS.md, CONVENTIONS.md, canon §8), and backfilled ADR index rows 0036–0041. rel: ADR-0042, ADR-0040, ADR-0041. |

## 2026-07-11 (merged 2026-08-05 from `docs/agno-memory-expertise`)

> Renumbered on merge: this branch minted its own **D-030..D-035** while `main`
> independently used those numbers for different decisions, so every entry below
> shifted **+3** (D-030->D-033 ... D-035->D-038). Content is otherwise unchanged.
> Where a decision has since been overtaken it is struck in place, not removed.

| # | Decision | Lane | Status | Rationale / notes |
|---|---|---|---|---|
| D-038 | **Key/provider rotation = Portkey (already deployed :8787 behind ContextForge); the two candidate Nexus repos are NOT adopted for production** | C | decided (owner) | Owner (2026-07-11): "I think Portkey will do that." Portkey is already live on :8787 behind the ContextForge gateway (per infra ledger) and provides the wanted behavior: rotate KEYS/PROVIDERS behind a FIXED embedding model (can't rotate embedders — mixed dims hard-error; CAN rotate keys/providers for the same model). Research (`nexus-gateway-notes.md`) found both owner-named repos too young/untrusted to hold production keys: `Ranatoasted571/nexus-proxy` does NOT proxy `/v1/embeddings` at all (chat/completions only — disqualifying); `AlphaBitCore/nexus-gateway` CLAIMS an `/v1/embeddings` route but is unverified, ships a TLS-intercepting compliance proxy + desktop agent + seeded default admin creds — not worth the trust exposure when Portkey already solves it. LiteLLM remains the live fallback (carries the Graphiti `embed-text` nv-embed-v1 4096-d lane). Nexus thread CLOSED. rel: D-010 (embed-text dim-lock), portkey-gateway-later memory (deferral now resolved — Portkey is the answer). |
| D-037 | **Ingest sequencing + two-tier normalization: (a) hash→land needs NO embeddings and NO chunking; (b) full-text search is the FIRST retrieval layer; (c) chunking follows LATER on the same per-domain split; (d) DuckDB is embedded IN Postgres (pg_duckdb) — AI-chat + KB content land there WITHOUT the heavy forensic normalization that evidence/messages require** | B | decided (owner) | Owner (2026-07-11): "we don't necessarily need the embedding functioning right off the bat… it's going to be saved in DuckDB… even the chunking isn't right away, we're doing full-text search to begin with while we tweak the chunking, which will follow the same kind of domain split"; + "DuckDB is embedded in PG. AI chats and knowledge for the knowledge base don't necessarily need to be normalized the same way that text messages and different things need to be in PG — they can just live in DuckDB." **KEY DISTINCTION — DuckDB is NOT a separate store**: it's the `pg_duckdb` engine inside the same Postgres 18 instance (verified in stack). So "land in DuckDB" and "land in PG" are the same DB — the difference is table format + normalization rigor. **Two data classes:** (1) EVIDENCE / text messages / forensic records → fully normalized into PG relational `source.*` tables with custody hashes (H1/H2/H3), bitemporal columns, HITL identity resolution (RESTART-0001/0002 — the court-defensible path); (2) AI-CHAT TRANSCRIPTS + KB content → land in DuckDB columnar (can read the R2 parquet lake), light touch, NOT force-fit into the normalized forensic schema. **Sequencing (both classes):** ingest = parse → custody hash → land (no vectors, no chunks) → full-text search available immediately (PG tsvector / DuckDB FTS — engine TBD at build) → chunking (hybrid semantic+fixed, `docs/planning/agno-chunking-strategy.md`) tuned afterward, applying the SAME legal/timeline/code/general split as the D-036 KB collections → embed per-domain last. This DECOUPLES parser-tables/RESTART-0001 from the still-open embedder bench + KB-substrate sparse build (D-034) + gateway work — ingest is now on its own track. Still gated: owner sign-off on the RESTART-0001 schema + HITL identity prompt before touching live PG. rel: D-034 (real-sparse rides KB ingest, AFTER this), D-035 (Surreal story-layer reopens once this produces hashed rows), D-036 (per-domain split reused for chunking). |
| D-036 | **Topic 4 — per-domain KBs: collection per domain (kb_legal / kb_timeline / kb_code / kb_general) with SPECIALIZED embedders; case_id partition keys from day one; 'symmetric-only' DEMOTED from rule to conditional** | B | decided (owner) | Domains + embedder directions (owner-specified): legal → a legal-TRAINED embedder (candidate search required; asymmetric models now IN PLAY — see correction); timeline/history → MULTIMODAL embedder (Gemini or Nemo/nemotron candidates — timeline carries photos/media); code → codestral-embed + tree-sitter chunking; general → likely bge-m3. Collection-per-domain (agno-validated pattern; per-domain dims possible); partition keys wired into kb_legal + kb_timeline schemas AT CREATION (cheap now, painful retrofit) — OWNER CORRECTION: NOT case_id (there is exactly ONE case — this is a personal single-case platform, usage-scope personal); the partition dimension will be something useful WITHIN the one case (source-type / party / time-period — chosen at KB-build design with owner). OWNER CORRECTION recorded: "symmetric-only" was never a rule — it was the workaround for one client (NIM embedqa) that couldn't pass `input_type` per call; with a proper integration path asymmetric embedders are fine. OPEN SUB-TASK (gates collection creation — dims lock): short embedder-candidate bench for the legal + multimodal lanes. Chunking per domain already decided (docs/planning/agno-chunking-strategy.md). rel: D-034 (real-sparse rides bge-m3 lanes). |
| D-035 | **Topic 3 (Surreal consolidation/story space) — design TEMPORARILY DEFERRED by owner** | B | deferred, on the board | Owner (2026-07-11): "not worried about it yet — once we get it normalized, into the databases, hashed, and run against Semantica + entity extraction + sentiment, THEN we'll figure it out." Write-path pattern (sole gated writer vs HITL tools vs batch job) explicitly undecided ("idk yet"). PRECONDITIONS before this topic reopens: RESTART-0001 ingest live → custody hashing on rows → Semantica/entity/sentiment analysis producing real outputs. Surreal's consolidation-space ROLE remains owner-affirmed (see research log) — only the schema/design work is deferred. Reopen as its own ADR with real data in hand. |
| D-034 | ~~**KB substrate = Milvus CONFIRMED (ADR-0027 holds); sparse lane gets the REAL fix (in-repo)**~~ **SUPERSEDED by ADR-0040 (2026-07-27): Weaviate is the locked vector substrate; Milvus is sidelined.** Recorded here unchanged for provenance -- it was true when decided (2026-07-11) and the reasoning about agno's hashed-TF-IDF fake-sparse lane is still the reason a real sparse lane matters on whatever substrate wins. | B | ~~decided~~ superseded (Topic 2, owner-decided 2026-07-11; overtaken 2026-07-27) | SurrealDB does NOT take the KB role — it keeps operational store + the Topic-3 consolidation/story space. The Surreal-retriever challenger is closed (not piloted). Sparse: agno's Milvus client fakes the sparse half with hashed TF-IDF; Milvus 3.0 supports REAL sparse (`SPARSE_FLOAT_VECTOR` GA, BM25 server-side function, or true BGE-M3 sparse — our text embedder already emits both lanes). Decision: build an in-repo custom insert/search path for genuine dense+sparse hybrid (no upstream PR for now). **Sequencing: build lands with the KB-ingest work AFTER Topic 4** (per-domain collection/partition design) to avoid schema rework — tracked in COORDINATION TODO so it cannot slip. Evidence: `topic-2-kb-substrate-brief.md`, files 02/05, owner-supplied milvus.io/docs/sparse_vector.md. |
| D-033 | **LearningMachine persists to PostgresDb (not SurrealDb); entity_memory fix TEMPORARILY DEFERRED to Topics 5/6; decision_log enabled (ALWAYS)** | B | done (Topic 1 of the memory/storage decision agenda, owner-decided) | agno 2.6.13's SurrealDb backend stubs all four learning methods (`NotImplementedError`, `agno/db/surrealdb/surrealdb.py:1990-2034`) — `user_profile`/`user_memory`/`session_context`/`entity_memory` were silent no-ops in production; only `learned_knowledge` worked (bypasses db via Knowledge/Milvus). Fix: `build_learning()` now uses `get_postgres_db()` (restores the documented ADR-0004 intent; smallest diff, no agno patch ownership); sessions/chat-history STAY on SurrealDb (those roles work there); Surreal's consolidation-space role untouched. `entity_memory`: the fix is **temporarily deferred, NOT dropped** — agno silently degrades PROPOSE→ALWAYS (no genuine HITL) and entities get their real home via Semantica + Graphiti custom entity types; it returns in Topics 5/6 with a genuine gate. `decision_log` store enabled in ALWAYS mode (its only active mode) as the durable agent-decision audit lane. Owner also set a wording rule: never label deferred work "disabled" — that's how things get forgotten; say "temporarily deferred". Evidence: `docs/reference/agno-memory-and-storage/07-platform-mapping.md` §A.3/§D-Topic-1, `01-memory-and-learning.md`. |

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

## 2026-08-02 — H3 chain tags disambiguated (hashing audit finding 2)
Two valid H3 constructions shared the tag `h3-chain-v1`: the SBV Go fold
(genesis `""`, `sha256(prev + "\n" + h2)`) and the Case Bible chain (genesis
`H1`, `sha256(prev_hex + h2_hex)`, 1,918 links live-verified). New rows
written by `server/evidence/custody.py` now carry
`h3-chain-sbv-genesisempty-v1`; the Case Bible writer (out-of-repo, case-bible
vault tooling) should adopt `h3-chain-h1genesis-v1`. **Crosswalk:** rows
tagged `h3-chain-v1` predate this decision and are disambiguated by WRITER
(SBV import batches → SBV construction; Case Bible vault → H1-genesis), never
by relabelling — recorded custody rows are append-only. _Byline: Claude Code ·
Fable 5 · 2026-08-02._

## 2026-08-02 — SBV demoted from forensic-primary to shadow (gap-review P0)
The parser-gap review (docs/HANDOFF-2026-08-02-sbv-chatminer-parser-gap-review.md)
found the SBV adapter reads `GET /api/activity` after upload — the service
account's ENTIRE persistent corpus, not the new import — so a second upload can
attribute earlier records to the new artifact's custody event (false
provenance). `accept()` now also requires `SBV_PRIMARY_ENABLED` (default
unset); `messages.sms-xml` (pure-Python) is the effective primary and prod
flips to it on next exec-tier deploy (intended). SBV stays callable by id for
shadow/diagnostic runs. Its mapper was fixed in the same commit (bodyless
retention + outbound role types 2/4/5/6) so shadow output is comparison-grade.
**Restore conditions** = the review's acceptance criteria: upload returns an
immutable import_id, activity reads scoped to it, primary/fallback equivalence
on a golden corpus, mandatory custody binding. _Byline: Claude Code · Fable 5 ·
2026-08-02._

## 2026-08-02 — PG moved to ovh-files (wave 1 of the ovh-data retirement)
Platform PostgreSQL now runs on ovh-files as Coolify app `data-pg-files`
(PG 18.1, pg_duckdb+postgis+pgvector, BIND_IP 100.91.190.107:5432). All four
databases transferred (pg_dumpall) and count-verified; exec-tier repointed via
the new `PG_HOST` env (`DB_HOST: ${PG_HOST:-${OVH3_HOST}}`); live API verified
connected to the new host with zero clients left on the old; old `data-pg` app
STOPPED, never deleted (datadir intact at /data/agno/volumes/pgdata).
Remaining on ovh-data for waves 2-4: SurrealDB, Weaviate, Neo4j-dev + graphiti
trio. _Byline: Claude Code · Fable 5 · 2026-08-02._
