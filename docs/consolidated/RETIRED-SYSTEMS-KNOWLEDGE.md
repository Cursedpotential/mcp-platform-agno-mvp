# Retired-Systems Knowledge — the facts that must outlive their documents

> _Byline: Claude Code · Opus 5 · 2026-09-05_
> _(Session began 2026-09-05; assembled across the 09-05/09-06 boundary. Analyst pass —
> companion to `docs/reviews/2026-09-05-docs-consolidation-audit.md` and
> `docs/consolidated/OPEN-WORK-REGISTER-2026-09-05.md`.)_

**STATUS: ITERATING — NOT DONE. Done only when the owner says so.**

## What this document is, and what it is not

The owner's directive: *"Clean up anything stale; if it's a system we're no longer using but
still has relevant information, it needs to be recompiled into the new system."*

This is that recompilation. It carries forward every concrete fact, gotcha, measured number,
config detail, and owner decision about systems this repository has **retired or superseded**,
so those source documents can be archived without losing anything.

It is **not** authority. `docs/DECISION_LOG.md` and `docs/adr/` remain the authority;
`docs/registers/SETTLED.md` remains the lookup index. This file is a *salvage record*:
every entry cites its source by `path:line` or by ADR/D-number, and decisions are **quoted,
never paraphrased**.

### Rule for using this file

A fact here is true **about a retired system at the time it was recorded**. It is preserved
because it may bite again — the same class of failure, the same upstream defect, the same
vendor behaviour. Never cite this file as evidence that something is currently deployed.

### The one structural finding first

**The ADR tree is already an excellent retired-systems knowledge base.** Every retired ADR in
this repo carries a supersession banner, a "why it was reversed" paragraph, and the surviving
sub-decisions. ADR-0024 is the model:

> `docs/adr/0024-surrealdb-store-session-knowledge-memory.md:1-6` — "Status: ~~Accepted~~
> **Superseded** — vector/Knowledge role by ADR-0027 (2026-06-16, then ADR-0040 → Weaviate);
> store/session/memory role by **ADR-0043 decision 3** (accepted 2026-08-02, flatten executed
> 2026-08-04). SurrealDB is now parked read-only and off the critical path; the Agno
> operational store is PostgresDb. **Nothing of this ADR remains in force.** Kept in full for
> provenance — it was correct when decided."

Consequence for the consolidation: **no ADR is ever archived** (see the inversion list in the
audit). The recompilation burden is therefore *not* the ADRs — it is the operational gotchas
that live only in planning docs, handoffs, and the wiki, which is what the rest of this file
captures.

---

## 1 · Graphiti — retired 2026-08-25 (D-070)

### The ruling, verbatim

> `docs/DECISION_LOG.md` D-070 — "**Graphiti is retired for now.** Memory/graph lane =
> SurrealDB (ADR-0056 governed projection + walk memory) with n8n as the agent layer and
> Temporal as the durable spine (D-068); the graph engine is an OPEN choice between Cognee
> and Memgraph. ADR-0014/0031/0037/0038/0039 (Graphiti) are suspended, not deleted."
> Owner: *"Graphiti is dead, for the moment anyways — remember Surreal and n8n and Temporal,
> and either Cognee or Memgraph."* — owner-ruled 2026-08-25 03:12.

Note the exact words **"for now"** and **"suspended, not deleted."** The five Graphiti ADRs
stay in place. The graph-engine choice (Cognee vs Memgraph) is **still open** — see the
Open-Work Register.

### Facts that must survive

**Upstream defect — the Neo4j `database` field is silently dropped.** Still unfixed on
upstream `main` when checked.

> `docs/planning/graphiti-image-rebuild-plan.md` §2 — `mcp_server/src/services/factories.py`,
> `DatabaseDriverFactory.create_config`, neo4j branch returns only
> `{'uri', 'user', 'password'}` with the comment *"Note: database and use_parallel_runtime
> would need to be passed to the driver after initialization if supported"* —
> "…and `graphiti_mcp_server.py` then builds `Graphiti(uri=…, user=…, password=…)` with no
> database. The FalkorDB branch *does* pass `database` and constructs a driver explicitly."

This is **why two Graphiti stacks existed and were load-bearing**, which an earlier session
wrongly flagged as duplication:

> `docs/URGENT-TODO.md` row 8 — "~~Parallel stacks: TWO Weaviates AND TWO Graphiti stacks
> violate the no-parallel rule.~~ **CORRECTED 2026-08-20 (archaeology):** the two **Graphiti**
> stacks are **intentional and load-bearing** — the upstream `zepai/knowledge-graph-mcp` image
> drops the Neo4j `database=` field, so one image can only bind one Neo4j DB; the
> `cursedpotential` fork exists to target the `memory` DB for the case lane. Not duplication."

**The image we were running was wrong and unpinned.**

> `docs/planning/graphiti-image-rebuild-plan.md` §1 — ours `zepai/knowledge-graph-mcp:**latest**`
> vs upstream compose's `:**standalone**`; digest built **2026-03-11**; `graphiti-core` ~March
> vintage vs **v0.29.3** (2026-07-27); MCP server **1.0.2**. "`:latest` is also **unpinned** —
> any redeploy can silently pull a different image. Same class of hazard as the Weaviate
> `:latest` we pinned earlier this session."

**The hotfix pile and what each sidecar was actually for** (all three are the reusable lesson,
not the container):

- `graphiti-hostfix` nginx — the image's FastMCP locks `allowed_hosts` to localhost, so a
  tailnet-IP request returns **421**.
- `graphiti-portkeyfix` nginx — `graphiti_core`'s OpenAI client has **no header hook**, so it
  cannot send `x-portkey-config`. Recorded as "keep for now (upstream client still has no
  header hook)".
- mounted `config.yaml` — **the image ignores `CONFIG_PATH`**.
  (all: `docs/planning/graphiti-image-rebuild-plan.md` §3 table)

**The rebuild that fixed it, as built** — kept because it is the template for owning any
upstream image:

> `docs/planning/graphiti-image-rebuild-plan.md:5` — "**BUILT, DEPLOYED AND VERIFIED
> 2026-07-31.** `ghcr.io/cursedpotential/graphiti-mcp:0.29.3` @ `sha256:fc64fd33…` is live on
> ovh-files, case lane writes the `memory` DB (proven), all three owner questions resolved."

Base `python:3.11-slim-bookworm`; `graphiti-core[neo4j,falkordb]==${GRAPHITI_CORE_VERSION}`
(default 0.29.1, pinned 0.29.3); the `providers` extra pulls `google-genai`, `anthropic`,
`groq`, `voyageai`, `sentence-transformers`.

**Extraction-model constraint (still generally true, still costly to relearn).** From the
global learnings and the Graphiti pipeline work: `glm-5.1` could not emit JSON-schema-conformant
structured output and Graphiti's extraction was silently empty for weeks; NIM `nemotron`
guided-JSON conformed. The transferable rule — *verify any model empirically before wiring it
to a structured-output consumer* — outlives Graphiti entirely.

**Moot on retirement, recorded so nobody re-opens it:** `graphiti-image-rebuild-plan.md:221` —
"`graphiti-hostfix` sidecar retained; not yet tested whether the new image makes it
[unnecessary]." Graphiti is retired; the question does not need answering.

**Recovered bytecode — the only surviving record of the GraphRAG comparison lane.**
`docs/recovered/GRAPHRAG-RECOVERED-FROM-BYTECODE.txt` plus five `.pyc` files are a decompiled
salvage of a retired Temporal workflow comparing Semantica extraction against a `sat_temporal`
extractor: `GraphRagLane`, `LaneReceiptV1`, `semantica_receipt_id` / `sat_temporal_receipt_id`,
referencing `server.analysis.graphrag_repository`, `server.analysis.semantica_comparison_adapter`,
`server.analysis.sat_temporal_extractor`, `server.analysis.graphrag_contracts`. **The source
`.py` files no longer exist.** This is forensically load-bearing for D-093's side-by-side lane
design and must not be archived into obscurity — it is the only evidence of that lane's exact
class and field names.

---

## 2 · LiteLLM — retired 2026-07-29 (ADR-0042)

### The ruling, verbatim

> `docs/adr/0015-litellm-gateway-ollama-primary.md:2-4` — "Status: Accepted — **SUPERSEDED by
> ADR-0042** (2026-07-29; Portkey = the model gateway; LiteLLM retired, teardown pending per
> `adr/README.md`). Kept for history; do not wire anything new to LiteLLM."

### Facts that must survive

**Why the gateway existed at all** — the reason is *not* retired, only the product is:

> `docs/adr/0015-...md` Context — "NVIDIA NIM rate-limited the owner for the first time during
> real use. The provider-agnostic factory (ADR-0008) already put a preference order in
> `app/settings.py`, but agents, n8n, and Graphiti each reached providers differently, and a
> single rate-limited provider could stall everything. We need one swap point and a primary
> that isn't NVIDIA."

And the measured payoff, which is the argument for keeping Portkey as *the* single swap point:

> same ADR, Consequences — "One place to add/swap providers; the NVIDIA→Ollama pivot took
> minutes, not a per-agent edit."

**Rejected alternative, preserved so it is not re-proposed:** "Per-agent provider config —
rejected: no single swap point; a rate-limit stalls the fleet."

**The teardown was never done.** This is a live discrepancy, not history:

> `docs/URGENT-TODO.md` row 16 — "**LiteLLM container was never actually torn down.** Every
> doc says 'retired' (ADR-0042, owner 2026-07-29) but DECISION_LOG D-030 clarifies only
> docs/refs were retired. Port 4000 is dead but the container persists."

> `docs/URGENT-TODO.md` row 12 — "**Dead port mapping:** `gateway` container on ovh-app
> publishes 4000 with nothing listening (retired LiteLLM). Only `opencode` on 4096 is live."

**Config paths that must not be moved blindly** (recorded during the repo repack, still a trap
for any Dockerfile edit):

> `docs/planning/repo-restructure-spec.md:138` — "…keep `docker/` config paths stable (gateway
> bakes `docker/gateway/litellm-config.yaml` — do NOT move those)". *(That path is now
> `deploy/docker/gateway/…` after the 2026-09-01 restructure — see §7.)*

**Where LiteLLM still appears in docs:** all remaining wiki mentions are correctly inside
`docs/wiki/archive/**` (e.g. `docs/wiki/archive/.planning/codebase/INTEGRATIONS_LEGACY.md:67-113`
describing a LiteLLM-Proxy + Provider-Hub architecture, and `:364`
`ghcr.io/berriai/litellm:main-latest (LLM proxy)`). No live-doc LiteLLM drift was found.
`docs/planning/2026-09-03-ingest-redesign-plan-and-sequential-guide.md:361` states it plainly:
"LiteLLM/Supabase/Qdrant appendices are dead (ADR-0042, D-042)."

---

## 3 · Windmill — retired 2026-06-23 (ADR-0029 supersedes ADR-0028)

### The ruling, verbatim

> `docs/adr/0028-windmill-casebible-orchestration-substrate.md:2` — "Status: **Superseded by
> ADR-0029 (2026-06-23)** — Windmill is dead; CaseBible no longer runs on it. The replacement
> substrate is now decided: a dedicated persistent CaseBible resource on the Agno stack
> (ADR-0029)."

### The sub-decisions that explicitly SURVIVED the substrate's death

This is the part that must not be lost when the ADR is skimmed. ADR-0028's own banner says so:

> `docs/adr/0028-...md` banner — "The sub-decisions below remain sound and carry into ADR-0029
> — **rclone** as the off-the-shelf mover/hasher, **DuckDB MD5 dedupe** (not raw R2 ETag), the
> **Postgres ledger**, the **non-destructive `_QUARANTINE_REVIEW`** safety rule, **rules-first +
> small-local-model** classification, and the **Agno-stays-the-brain** boundary. Only the
> Windmill *substrate* is retired."

### Facts that must survive

**The R2 ETag trap** — a correctness bug waiting for anyone who dedupes object storage:

> `docs/adr/0028-...md` Decision — "**Dedupe uses the reliable hash, not the raw R2 ETag.** R2
> multipart-upload ETags are not plain MD5, so large files would mis-/under-dedupe;
> rclone-sourced MD5 (in object metadata) is the dedupe key."

**Why rclone was retained** (four specific capabilities, each still true):

> same — "it exports Google Docs to real bytes (`--drive-export-formats`), reads true source
> hashes (OneDrive QuickXorHash, GDrive MD5) and writes real MD5 into R2 object metadata,
> supports OneDrive (not a native Windmill integration), and does server-side R2→R2 moves.
> Windmill orchestrates rclone; it does not replace it."

**The mount-less pipeline shape** — reusable design, engine-independent:
"`rclone lsjson` → DuckDB dedupe → `rclone moveto`, gated by … approval/suspend steps. FUSE
mounts become optional (human eyeballing via Kasm only)."

**Licensing note, recorded because usage scope may change:** "Usage is **strictly
personal/internal** (no resale/managed-service), so Windmill's AGPLv3 Community Edition is
unrestricted and free — no commercial license needed. All boxes are **CPU-only (no GPU)**."

**Windmill was known dead in design docs before the ADR formalised it:**
`docs/planning/transcript-mining-pipeline-spec.md:103` — "Backend durability — Zep deprecated,
Windmill dead; this design avoids both." (2026-06-19.)

---

## 4 · SurrealDB — the LEGACY OPERATIONAL ADAPTER ONLY is retired

### ⚠ Read this before touching anything Surreal-shaped

There are **two different Surreal things** and conflating them has already produced doc drift
in this repo. The current, governed role is **not** retired:

> `docs/DECISION_LOG.md` D-073 — "**SurrealDB is the final temporal-graph aggregation, walk,
> and analysis engine.** Evidence modalities remain in their proper authoritative/specialist
> homes; governed, established facts and typed provenance references are projected into
> Surreal, where the complete cross-source temporal graph is assembled and the final
> as-lived/hindsight walks and delta analysis execute." — owner-ruled 2026-08-25.
> "Refines D-070 and supersedes ADR-0056's description of Surreal as merely experimental."

> `docs/DECISION_LOG.md` D-080 — "…Weaviate serves search, Neo4j serves the
> Semantica-originated semantic graph, and Surreal serves the final reconciled cross-domain
> temporal graph and walks." — owner-ruled 2026-08-25.

**Retired:** the legacy Agno *operational* Surreal adapter and the old `data-surreal` instance.
**Not retired:** SurrealDB as the analysis/walk engine.

### Why the operational adapter was reversed — the single most expensive gotcha in this repo

> `docs/adr/0024-surrealdb-store-session-knowledge-memory.md` — "**Why it was reversed**
> (short version; full reasoning in ADR-0043 and
> `docs/reference/agno-memory-and-storage/07-platform-mapping.md`): agno's SurrealDb backend
> raises `NotImplementedError` on every LearningMachine method, and LearningMachine swallows
> the exception — so `user_profile` / `user_memory` / `session_context` / `entity_memory` were
> **silent no-ops in production for months**. Separately, registering a second `db.id` armed
> agno's multi-db gate, making every route that omitted `db_id` return 400. The consolidation
> this ADR sought was real, but it landed on Postgres, not SurrealDB."

Two transferable rules fall out of that paragraph and both are already canon elsewhere:
*config accepted ≠ feature working*, and *a swallowed exception is a silent data-loss bug*.

### Facts that must survive

**What SurrealDB was chosen FOR** — the requirement did not go away, it moved to PG + Surreal-as-projection:

> `docs/adr/0024-...md` Context — "SurrealDB is multi-model (document + relational + vector +
> graph + live queries) with **native bitemporal versioning** (valid time + transaction time,
> time-travel via SurrealKV)".

**The altitude distinction, still the right frame** even though the actors changed:

> same, Decision — "SurrealDB = bitemporal *storage*; Graphiti = bitemporal *knowledge-graph
> cognition* (auto fact-invalidation on contradiction, episodic ingestion, entity resolution,
> hybrid retrieval, point-in-time graph state — the Pass-1→final delta)."

**The pgwire path is closed** — do not re-open the spike:

> `docs/planning/architecture-directives/architecture-validation-2026-06-14.md:1-4` —
> "Supersedes the 'drop Postgres via SurrealDB-pgwire' path. Read this before reopening the
> pgwire spike."

**The Surreal integration directive is design-only, never deployed:**
`docs/planning/architecture-directives/surrealdb-integration.md:1-5` — "SurrealDB Integration —
Design Artifact (DRAFT, do not deploy) … Status: design draft. No live source or infra touched."

**Parked artefacts and their location.** The export is at `../_stale/surreal-export-20260804`
(a *sibling* of this repository; only the owner deletes). The parked deployment
`data-surreal-phase1-t0-r1` and the 5.1 GB disk on the powered-off `ovh-data` VPS are recorded
in `docs/URGENT-TODO.md` rows 9 and 14. **`docs/URGENT-TODO.md` row 14 is now stale** — it says
"SurrealDB is formally RETIRED (ADR-0043, owner ruling 2026-08-06)" as a whole-product claim,
which D-073/D-080 corrected on 2026-08-25. Flagged in the Open-Work Register; not edited here.

---

## 5 · AgentOS as the API host — retired (D-101 / D-107)

### Current state, verbatim

> `docs/INDEX.md` "Current truth in one paragraph" — "AgentOS is retired from the production
> API target; the plain FastAPI host and direct-caller cutover are implemented locally and held
> for live Coolify proof. Agno 2.8.7 remains only as a disabled, bounded atomic-agent library
> dependency while Temporal task contracts are built."

### Facts that must survive

**The mount pattern was wrong and the reason is durable:**

> `docs/planning/EXECUTION_PLAN.md:85` — "`AgentOS(base_app=app)` + `get_app()`. NEVER
> `app.mount(...)`."
> `:95` (table) — `app.mount("/path", agentos_app)` → `AgentOS(base_app=app) →
> agent_os.get_app()`.

**`--reload` breaks MCP** — this bites any ASGI app that serves MCP, not just AgentOS:

> `docs/planning/EXECUTION_PLAN.md:185,378` — "Remove `--reload` from agentos-api command
> (breaks MCP). Replace with `uvicorn app.main:app --host 0.0.0.0 --port 8000` (no reload)."

**Auth behaviour that outlived the host** (from the repository learnings, still true of the
successor API): `authorization=False` in `main.py` only disables JWT — the `OS_SECURITY_KEY`
bearer still gates every route including `/knowledge/*`. Internal callers must send
`Authorization: Bearer $OS_SECURITY_KEY`.

**A registered agent module needs a container restart** — uvicorn hot-reload does not pick up a
new agent module. Recorded in `docs/create-new-agent.md` Step 6 and still true of any
registry-at-import-time design.

**Template residue — the five `docs/*-agent.md` prompt files.** `create-new-agent.md`,
`extend-agent.md`, `improve-agent.md`, `eval-and-improve.md`, and `review-and-improve.md` came
in with the upstream AgentOS skeleton (ADR-0001, "fresh build from skeleton"). They instruct the
reader to edit `agents/<slug>.py` and reference `../app/config.yaml`, `../compose.yaml`, and
`../railway.json` — **none of which exist** (`app/` was repacked to `server/` by ADR-0033; the
compose file lives at `deploy/compose.yaml`; `railway.json` never existed here). The one durable
fact inside them is the eval harness contract, preserved next.

**The eval contract (the only living part of those five files):** cases live in `evals/cases.py`,
the runner in `evals/__main__.py`; each case uses agno's built-in `AgentAsJudgeEval` (LLM judge
against a `criteria` rubric, binary pass/fail) and/or `ReliabilityEval` (asserts which tools
fired) — **no custom DSL**. `evals/cases.py` is still `CASES: tuple[Case, ...] = ()` — tracked as
open in `docs/DEBT.md` ("Evals populated (was `CASES=()`) | planned … `evals/cases.py`").

---

## 6 · Milvus as the *platform's* vector store — retired (ADR-0040 / D-042)

### ⚠ The distinction that must never be collapsed again

> `docs/registers/SETTLED.md` — "The Milvus service (`100.91.190.107:19530`, collection
> `agent_session_memory_nemotron3`) is UP and IS memsearch's backend — memsearch is a live,
> working source. Only the Agno platform's `data-vector` role is deliberately down (Weaviate is
> the platform search projection, D-042). NEVER say 'Milvus is down' and NEVER treat a memsearch
> failure as expected." — 2026-09-03 owner correction.

Three documents still carry the retired framing and are listed for correction in the
Open-Work Register: `docs/blueprint/architecture.md:99` (`MV[("Milvus — DOWN, deliberate")]`),
`docs/research/integration-audit-2026-08-24/stage-2-discovery-candidates.md:119`, and
`docs/reports/mcp-platform-agno-review.md:32`.

### Facts that must survive

**The boot-crash root cause** — this is the kind of thing that costs a night to rediscover:
Milvus standalone's embedded etcd defaults (100 ms heartbeat / 1 s election) on a slow VPS disk
produce an `etcdserver: leader changed` panic loop (exit 134). Fixed via
`milvus-coolify/embedEtcd.yaml` `heartbeat-interval 1000` / `election-timeout 10000`
(host copy ro-mounted; edit the host file and the next restart picks it up).
Observed operationally in `docs/planning/operator-console-requirements.md:155` — "bounced
Milvus → etcd leader-change boot-race crash loop". The `data-vector` app went down deliberately
on 2026-08-10 after the **sixth** embedded-etcd corruption (`docs/COORDINATION.md`).

**Client-side caching gotcha:** after dropping a Milvus collection externally, the API must be
restarted — agno's client caches the numeric collection ID and 500s with
`code=100 collection-not-found` on the next insert.

**Eager-connect at startup:** `docs/planning/operator-console-requirements.md:149` — startup
fails "when Milvus is unreachable (`create_knowledge` eager-connects)". Any vector backend wired
at import time inherits this failure mode.

**Dimension changes are re-embeds, not config changes:**
`docs/planning/operator-console-requirements.md:160` — "Milvus `platform_knowledge` recreate
(1024-d→4096-d) — owner-gated". `docs/DEBT.md` records the same rule generally: changing the
embedder means re-embedding the store; mixed dimensions hard-error.

**A freshly created collection reports `row_count 0` until flushed**, and a search against it
returns `[]` with no error — flush once after the first index.

**The lineage, so the next vector-store proposal starts from the right place:**
pgvector (ADR-0010) → Milvus platform-wide (ADR-0026/0027) → **Weaviate LOCKED** (ADR-0040,
2026-07-27), cutover verified 2026-08-09 (D-042; `pymilvus` dropped from the Dockerfile).
`docs/planning/forensic-db-extension-and-reconciliation-addendum.md:12,16,18` preserves the
mid-lineage state, including a BM25 placement conflict (pg_textsearch-in-PG vs Milvus
hybrid dense+sparse) and an explicit **"Stale / do NOT inherit"** list: Multicorn2 live-FDW hub
(`neo4j_fdw`, `duckdb_fdw`) plus a March `shared_preload_libraries='timescaledb,pg_search,pg_cron,…'`
line — dropped by ADR-0032; pgvectorscale; Apache AGE (Semantica backend option only, never
deployed).

### The Weaviate landmine that replaced it — still live, re-verified twice

Not a retired-system fact, repeated here because it is the direct successor risk and every
horizon design depends on it: agno's Weaviate adapter **silently drops** `agno.filters`
FilterExpr lists (`log_warning` + `filters = None`); only **dict filters** are applied.
Verified in agno 2.8.0 source 2026-08-02, re-verified 2.8.7 on 2026-08-14 at
`weaviate.py:414-416`, `:441-443`, `:883-884`. A horizon filter written as a FilterExpr passes
tests on other vectordbs and applies **zero** filters in production.

---

## 7 · The pre-2026-09-01 directory layout

Retired by the owner's 2026-09-01 restructure. Recorded because **every old doc, Dockerfile
`COPY`, and compose build-context in the archive uses the old paths**, and a reader who does not
know the mapping will chase ghosts.

| Old path (in archived docs) | Current path | Authority |
|---|---|---|
| `app/` | `server/` | ADR-0033 (server package repack) |
| root `engine/` | `modules/engine/` | 2026-09-01 owner restructure (`AGENTS.md`) |
| root `docker/` | `deploy/docker/` | same — compose files in `deploy/` now resolve `./docker/...` build contexts correctly |
| root `workbench/` | `modules/workbench/` | same |
| root `vendored/` → `modules/vendored/` | **dissolved 2026-09-01**; third-party Python is `server/vendored/`; SBV is `modules/forks/sbv` | same |
| root `contracts/` | **removed** (never-populated placeholder); recreate as `modules/contracts/` only when H-02 lands real schema files | owner ruling 2026-09-01 (`AGENTS.md`) |
| root `timesketch-fork/`, `llm_probe/`, `llm_probe_ui/` | workspace sibling / `modules/custom/` | 2026-09-01 restructure (`AGENT_MEMORY.md` retired rows) |
| `compose.yaml` (root) | `deploy/compose.yaml` | 2026-09-01 restructure |

Contemporaneous evidence of the old shape, for anyone verifying an archived doc:

- `docs/planning/operator-console-requirements.md:6` — "…workbench app (`workbench/`, Coolify
  :8020) is rebuilt in place."
- `docs/planning/repo-restructure-spec.md:138` — "every `COPY app/ …` / `COPY evidence/ …` →
  `COPY server/ …`; keep `docker/` config paths stable".
- `docs/planning/repo-restructure-spec.md:165` — "…`tools/` into `evidence/tools/`, move
  `chatminer/` under `vendored/`. No `server/` parent".

**The root `contracts/` placeholder** is not documented anywhere in the planning corpus — its
only record is the current `AGENTS.md` row. That row is therefore the sole surviving evidence and
must not be trimmed as boilerplate.

---

## 8 · Verify-in-place promotion — rejected 2026-09-03

### The rejection, verbatim

> `docs/planning/2026-09-03-ingest-simplification-plan.md:23` (§ context) — "An earlier
> verify-in-place variant was rejected because the D-128 immutability guards attach to
> `evidence.*` tables, so a flagged working row would be unguarded evidence."

**The shipped design instead promotes by writing new linked rows into `evidence.*`.** The
rejected alternative was to mark a `working.*` row verified in place and treat it as evidence.
The reason is structural, not stylistic: the guard triggers are bound to the `evidence.*`
tables, so anything asserted as evidence outside those tables carries **no** immutability
guarantee.

Related, and the reason the guards are currently mostly off:

> `docs/GUARD-TRIGGER-DISPOSITION.md` — "**Total guard triggers defined across sql/0001-0055:
> 131 on 84 tables.** … Governed by D-110: nothing is immutable until evidence is promoted,
> behind a dev flag. This file exists so that flipping that flag does NOT mean replaying all 131
> triggers blindly." Bucket A (replay when the flag flips, guarding `evidence.*`) currently
> contains **0 triggers**; bucket B (leave off — `context.*` intake and `working.*` derived, under
> active construction) contains **120**; bucket C ("wrong place" — append-only guards on lookup
> registries, which would make a mistaken format definition permanently uncorrectable) contains
> **3**; bucket D (moot — the finished `ai`→`platform` consolidation) contains **8**.

That file is a **living** register, not history — it is the thing that makes the eventual flag
flip safe. It is not archived.

---

## 9 · Traefik forward-auth Authentik — rejected 2026-09-02 (D-133)

### The ruling, verbatim

> `docs/DECISION_LOG.md` D-133 — "**Authentik integrates as an OIDC provider, NOT as a Traefik
> forward-auth proxy. Traefik is only for genuinely external-facing surfaces; everything else
> just gets Tailscale addresses.**" Owner, 2026-09-02: *"Traefik is only for external-facing
> surfaces, unless you need to use it for the auth process,"* then *"OIDC is the way to go…
> otherwise it just gets tailscale addresses."*

### Facts that must survive

**What exactly was built on the rejected architecture** — so it is reworked, not deployed:

> D-133 — "`deploy/authentik.yaml` (committed 2026-08-29, `0f53e3a` 'feat(auth): gate Workbench
> through Authentik and Traefik') encodes the rejected architecture end to end and must be
> reworked, not deployed as written - it requires `AUTHENTIK_LISTEN__TRUSTED_PROXY_CIDRS` with an
> exact Traefik CIDR (hard-fails without Traefik), carries Traefik router labels for
> `auth.int.mitechconsult.com` with a letsencrypt cert resolver, and defines an outpost router on
> `workbench.int.mitechconsult.com` + `/outpost.goauthentik.io/`, which is specifically the
> single-application forward-auth pattern."

**The ruled shape:** "Authentik runs on the tailnet … each service is an OIDC client that
validates JWTs in-process against Authentik's JWKS endpoint; browser surfaces (the Workbench)
run a standard authorization-code flow. No reverse proxy, no outpost, no letsencrypt, and no
public hostnames are required for internal services."

**The consequence nobody may report otherwise:**

> D-133 — "Because the authorization system is NOT up, **D-125's removal condition for
> `PLATFORM_DEV_AUTH_BYPASS` is nowhere near met** - the flag remains load-bearing and every
> service still depends on tailnet-IP checks plus bearer tokens. Nobody is to report the dev
> bypass as nearly retired until OIDC issuance and in-process validation are live and proven."

**The pattern it belongs to** — written-but-never-deployed work: "the same failure pattern as the
Evidence.dev lane (D-129) and the DuckDB ELT lane." Authentik has never been deployed; no Coolify
application exists for it (33 apps, none named authentik/keycloak/traefik).

---

## 10 · `unified-operator-surface` — NOT retired (correction)

This was listed as a probable retirement candidate when this audit was commissioned. **It is
not.** ADR-0061 is **Accepted** and `docs/INDEX.md` names it as the production composition:

> `docs/INDEX.md` — "Accepted ADR-0061 defines the production composition: Workbench is the
> unified shell and the storage-free SBV client is its bounded `/evidence/preview` pipeline
> surface."

`docs/adr/0061-unified-operator-surface.md` (`status: accepted`) and its companion
`docs/design/0061-unified-operator-surface/spec.md` are **KEEP-CANON**. What *is* slated for
retirement is only the **compose file name** — `docs/DECISION_LOG.md` D-138 lists, as still open
from the naming thread, "retirement of `graphiti*`, `phase1-surreal*`, `unified-operator-surface`
compose files." A compose filename is not the architecture. Recorded here so the fence is not
torn down twice.

---

## 11 · Other retired things captured in passing

**Zep** — `docs/planning/transcript-mining-pipeline-spec.md:103`: "Zep deprecated, Windmill
dead; this design avoids both." (2026-06-19.)

**FileFlows** — replaced entirely by the ADR-0028 decision before Windmill itself died; the
Phase-2 classification/routing role moved to the pipeline shape in §3.

**SBV as a *fork*** — reclassified, not retired:
> `docs/registers/SETTLED.md` — "D-131 | SBV is a DONOR (lowcarbdev, MIT), not a fork; absorbing
> into `modules/engine/decode/`; name donor-derived code for what it does now".
An earlier revision of `AGENTS.md` credited "danzek", which was wrong. `docs/planning/sbv-fork-plan.md`
(2026-07-09, "DRAFT for owner sign-off") and its five open questions are superseded wholesale by
D-131. **Its `fts5` build-tag rule survives:** a plain `go test ./...` fails every DB-backed test
with `no such module: fts5` — that is a missing build tag, not a code defect.

**The `agno` docker network is a LOCAL bridge, not a cross-host overlay** — cross-host is
tailnet-only, never by service name. And `coolify-proxy` owns host port 8080 on *every* node, so a
Coolify app listening on 8080 gets its published host port bumped (Weaviate:
`100.91.190.107:8081->8080`). Probe at the app's **configured** host:port, never a shell-default
guess. These belong to the current stack but are recorded here because the archived topology docs
contradict them.

**Two H3 custody chain constructions coexist and are BOTH correct** — a 2026-07-22 "correction"
declaring the first WRONG was itself wrong. (a) SBV Go chain: `chain_0 = ""`,
`chain_i = sha256(chain_{i-1} + "<LF>" + H2_i)`; H1 never enters the fold. (b) Case Bible chain:
genesis = H1, `chain_i = sha256(prev_hex + h2_hex)` (live-verified, 1,918 links). New rows carry
`h3-chain-sbv-genesisempty-v1`; legacy `h3-chain-v1` rows are read-only and disambiguated by
writer. Current authority: `docs/reference/HASH-TAXONOMY-2026-08-29.md` and D-124/D-077/D-136.

---

## 12 · Source documents this file makes safe to archive

Archiving any of these is conditional on this file surviving alongside them, and on their open
items appearing in `docs/consolidated/OPEN-WORK-REGISTER-2026-09-05.md`.

| Source document | Section here | Class |
|---|---|---|
| `docs/planning/graphiti-image-rebuild-plan.md` | §1 | ARCHIVE-CLEAN |
| `docs/planning/gui-integration-spec.md` (LiteLLM/AgentOS-UI half) | §2, §5 | UNCLEAR — open questions unresolved |
| `docs/planning/sbv-fork-plan.md` | §11 | ARCHIVE-CLEAN |
| `docs/planning/sbv-mcp-integration-plan.md` | §11 | ARCHIVE-CLEAN |
| `docs/planning/forensic-db-extension-and-reconciliation-addendum.md` | §6 | ARCHIVE-CLEAN |
| `docs/planning/repo-restructure-spec.md` | §7 | ARCHIVE-CLEAN |
| `docs/planning/EXECUTION_PLAN.md`, `MIGRATION_PLAN_v8.md`, `VERIFIED_AGNO_API.md`, `BUILD_TODO.md` | §5, §7 | ARCHIVE-CLEAN |
| `docs/create-new-agent.md`, `extend-agent.md`, `improve-agent.md`, `eval-and-improve.md`, `review-and-improve.md` | §5 | ARCHIVE-CLEAN |
| `docs/wiki/archive/.planning/codebase/INTEGRATIONS_LEGACY.md` | §2 | ARCHIVE-CLEAN *(⚠ credential redaction required first — see the audit's P0)* |

**Never archived, referenced throughout:** every ADR, `docs/DECISION_LOG.md`,
`docs/registers/SETTLED.md`, `docs/GUARD-TRIGGER-DISPOSITION.md`, `docs/URGENT-TODO.md`,
`docs/DEBT.md`, `docs/recovered/`.
