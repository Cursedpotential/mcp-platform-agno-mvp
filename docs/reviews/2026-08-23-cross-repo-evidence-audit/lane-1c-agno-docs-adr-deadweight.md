# Lane 1c — Agno docs, ADRs, and dead-weight audit

> _Byline: Claude Code · Opus 5 · 2026-08-23_ · source: subagent ad17edcca5dc30dee

Read-only. Docs treated as aspirational unless corroborated against other docs, ledger entries, or
actual file contents.

## 1. `docs/URGENT-TODO.md`

Byline: Claude Code · Opus 5 · 2026-08-20. Every "known broken / deferred" row was seeded 2026-08-20
from an infra/networking fleet audit. **None of the 13 open items relate to document ingest, evidence,
search/retrieval, or bundling/exhibits.** They are entirely Docker/Tailscale/Traefik/OVH topology:

1. Docker subnet collision with owner's home LAN (OPEN)
2. ovh-files/ovh-app identical docker subnets (OPEN)
3. Fix: distinct `default-address-pools` per host (OPEN)
4. Traefik binds `0.0.0.0` on all 4 hosts, not tailnet IP (OPEN — public exposure)
5. Port 8080 published to `0.0.0.0` with nothing behind it (OPEN)
6. `Secrets/PLATFORM_REFERENCE.md` badly stale — subdomains 503, Milvus/LiteLLM dead refs (OPEN)
7. Coolify `*.sslip.io` domains not wired to Traefik, 404 (OPEN)
8. Two Weaviate + two Graphiti "parallel stacks" — Graphiti duplication ruled intentional; Weaviate
   duplication still unexplained (PARTLY RESOLVED)
9. ovh-data VPS needs OVH termination (OWNER, billing)
10. Old "confirm before changes" vs SPRINT MODE contradiction — RESOLVED
11. OVH private network never came up — wrong NIC configured (OPEN)
12. Dead port mapping for retired LiteLLM gateway container (OPEN)
13. Historical subnet-blackhole hazard note (NOTE)
14. **SurrealDB formally RETIRED (ADR-0043) yet `data-surreal-phase1-t0-r1` ordered promoted
    2026-08-20 — contradiction needs owner ruling (OWNER — BLOCKING)**
15. Two unexplained Weaviate instances on ovh-files (OWNER)
16. LiteLLM container never torn down despite "retired" docs (OPEN)

**Meaningful negative finding:** this file is a pure infra punch list. Evidence/ingest debt lives in
`DEBT.md`, not here.

## 2. ADRs relevant to document handling / evidence / retrieval

Read `docs/adr/README.md` (index) + full text of ADR-0012, 0017, 0018, 0044, 0057, 0058.

- **ADR-0012** (Phase 0 decisions locked, 2026-06-09) — settings home, transcript_miner topology, MCP
  vendoring, PG18 target, n8n role, model-provider default. Foundational plumbing, not document
  handling.
- **ADR-0017** (Evidence = polyglot orchestration mesh, Accepted 2026-06-11) — custody gate
  (sha256 → `evidence.evidence_hash` + R2 blob) → named workflows per evidence type → atomic tools
  registry → agent re-composition on tool failure. The architectural spine for ingest; still cited as
  current in canon §5.
- **ADR-0018** (Bitemporal evidence memory + disclosure-tier, Accepted 2026-06-11, extends 0014) —
  every evidence atom carries valid-time / knowledge-time / disclosure-tier; a "pass" is a
  knowledge-horizon filter. **Substrate accepted; the multi-pass engine that drives it is explicitly
  deferred to Part 2** (not built, per the ADR's own text).
- **ADR-0044** (Evidence-vs-Context boundary + forensic transcript data model, Accepted 2026-06-27,
  renumbered 2026-08-05) — hard rule that AI chats never enter the evidence schema; one
  `normalized_record` per message, never blended speakers; structured source beats markdown beats
  whole-file; whole-file parser BANNED for evidence.
- **ADR-0057** (Claim-centered evidence assembly + immutable established facts, Accepted 2026-08-15,
  D-062/D-064) — candidate claims → bounded cross-system investigation → human review → immutable
  established fact with exact source-span provenance; corroboration counted by independent source
  family, not raw hit count. **Closest thing to a "bundling" concept in the ADR set — but it is a
  fact-assembly/provenance model, not a document/exhibit output generator.**
- **ADR-0058** (Investigation Search + behavioral-analysis modes, Accepted 2026-08-15, D-063) —
  Find Evidence / Reconstruct Event / Discover Patterns intents; immutable scope manifests; hindsight
  vs as-lived-so-far vs paired modes. "Case-prep export transforms shorthand into conduct-first
  language" is the ONLY "export" mention, and it is about wording transformation, not assembly.
- Per the index, later ADRs continue the arc: **0053** (five-lane AI-chat ingestion), **0055**
  (Matter/CourtCase boundary), **0056** (Surreal governed projection), **0059** (first-party /
  acquired-third-party message projections, most recent, 2026-08-18) — all Accepted-but-activation-held.

**No ADR describes a bundling/exhibit/production-set/Bates feature as built or formally decided.**

## 3. `docs/PROJECT_CANON.md`

Byline chain runs from 2026-06-13 creation through a **2026-08-18** amendment (ADR-0059). The most
actively maintained doc in the repo — every amendment dated, attributed, stating what changed and why,
with explicit strikethrough-and-correct for superseded claims (Milvus→Weaviate, LiteLLM→Portkey,
SurrealDB retirement). **Reads as CURRENT.** Claims authority: "§5 Locked Decisions here wins" over ADRs.

- **§1 (three-part arc):** "Part 1 — Evidence. Custody → parse → normalize → store → **court-ready
  export**." Stated as a GOAL, no mechanical detail. **Aspirational** — nothing in §4 (current stack)
  or §5 (locked decisions) describes an export/bundling subsystem as deployed.
- **§3 (knowledge engine):** five structural lanes (`platform`, `legal`, `personal_history`, `context`,
  `evidence`) in Weaviate, one collection per lane; AI chats land as parent-conversation/child-message
  pairs, chunked, then classified; the evidence collection is custody-only. Entity/claim/time/event
  candidate extraction runs async post-chunking; only humans promote candidates to timeline events.
- **§4 (current stack, rewritten 2026-07-29 from live Coolify inventory):** 4-box Coolify fleet
  (`ion-control`, `ovh-app`, `ovh-data`, `ovh-files`). Confirms **`data-vector` (Milvus) is
  deliberately DOWN since 2026-08-10**; Weaviate is the live vector substrate on `ovh-files`
  (`data-weaviate`, `http://100.91.190.107:8081`).
- **§5 (locked decisions):** PostgreSQL is now canonical belief/knowledge authority (corrected
  2026-08-15); Graphiti is a "run-scoped belief projection, not canonical evidence"; SurrealDB is
  RETIRED/zero-callers operationally, though ADR-0056 gives it a new, still-unactivated analytical role.
- **§6 (roadmap):** P2 "evidence spine" is 🟡 — "parser core-swap DONE" but **"Evidence schemas
  populated by a real pipeline" is still explicitly open** (near-empty live PG evidence schema,
  `evidence_hash` = 26 rows at last verified count). P4 (SBV/universal import engine) is "largely
  landed." **No roadmap phase names a bundling/exhibit deliverable.**

## 4. `docs/DECISION_LOG.md` and `docs/DEBT.md`

**DECISION_LOG.md** — grep for bundle/exhibit: zero relevant hits (only D-006's unrelated MCP-infra
"bundle"). Most recent decisions D-060..D-066 (2026-08-15→18) are Matter/CourtCase identity,
message-projection source clocks, Surreal governed projection, and the native-Weaviate evidence-vector
cutover (**D-066, most recent, "activation held"**). None touch bundling.

**DEBT.md** — zero hits for bundle/exhibit. Relevant:
- "Court-readiness compatibility debt (2026-08-15)" — about VERSIONING the custody-event digest
  writer/verifier, not document assembly.
- Known-debt row **"Evidence schemas populated by a real pipeline" = `planned`**.
- "ADR-0053 implementation follow-ups": CDC worker/replay/alert = manual drains only; classifier
  quality = deterministic keyword baseline only; OCR/VLM selection = extractor seam + optional Docling,
  not benchmarked; **"Timeline extraction … investigation-register UI" not yet built.**
- "Horizon Swift MVP audit items (2026-08-16)": several ingest pieces resolved LOCALLY, but every
  row's "Activation held" column shows no live DB write, no production deployment, no credentials.
- "Agno JSON-metadata evidence vectors": native Weaviate V1 contract accepted locally; live cutover
  (migrations 0026–0029, backfill, alias switch) held pending release gates — matches D-066.

**Verdict:** the team's own debt register identifies the INGEST pipeline as incomplete. It has NOT
identified evidence bundling as a gap, because no such feature has ever been scoped.

## 5. `docs/MASTER-TODO-2026-08-18.md` + newest handoffs

**MASTER-TODO-2026-08-18.md** (Codex · GPT-5 · 2026-08-18) — a "production resume ledger" with the rule
*"Mockups are never completion… every item requires production implementation, Coolify deployment, and
live verification."*

| Surface | Status |
|---|---|
| Custody, ingest, parsers, normalized spine | IMPLEMENTED LOCAL ONLY |
| Conversations / acquired third-party approval | IMPLEMENTED LOCAL ONLY |
| Chunks / native Weaviate | IN PROGRESS |
| Knowledge / curated works | IN PROGRESS |
| Case/matter evidence desk | IMPLEMENTED LOCAL ONLY |
| Human review | IMPLEMENTED LOCAL ONLY |
| Horizon walk | IN PROGRESS |
| Agents / Graphiti / Neo4j | IN PROGRESS |
| Surreal experimental surface | HISTORICAL/MOCKUP ONLY |
| Workbench/API | IMPLEMENTED LOCAL ONLY (deployed URL stale) |
| Backup / observability / security | IN PROGRESS |
| Deployment | BLOCKED |

**"No item is classified DONE+LIVE VERIFIED."** This is the most authoritative current status statement
in the doc tree: as of 2026-08-18, nothing evidence/ingest/retrieval-related is confirmed live.

**HANDOFF-2026-08-18-evidence-desk-backend.md** (STATUS: PARTIAL, BUILD_STATUS: PASS) — adds two read
endpoints (`source-content`, `conversation-context`); 47+27 tests pass locally; "Live deployment and
DB/schema verification — blocked by the documented down exec tier."

**HANDOFF-2026-08-18-evidence-operations-desk-mvp.md** — defines the target drill-through UX
(custody jacket → original source message → normalized message(s) → surrounding conversation →
human-reviewed content/decisions → custody/provenance). This is a **read/review UI, not an export
generator.** Deployed Workbench at `100.72.169.40:8020` is stale; "NOT COMPLETE — resume at step 1."

## 6. Grep: bundle / exhibit / production set / bates / packet / disclosure

- **bundle** — ~35 file hits, all unrelated infra ("exec bundle", "coolify-write … hosted read-only
  bundle"). Evidence-adjacent hits only inside the DRAFT `docs/planning/forensic-db-architecture/` tree.
- **exhibit** — ~35 hits, almost all in `docs/planning/forensic-db-architecture/`,
  `docs/planning/forensic-db-reconciliation/`, `docs/wiki/` (archived), `docs/planning/chat-sample-analysis/`.
- **production set** — **zero hits anywhere in docs/.**
- **bates** — 2 hits, same file:
  `docs/wiki/project-docs/components/orchestration/contextforge/IMPLEMENTATION_ANALYSIS.md:334`, a regex
  `"bates_number": r"\b[A-Z]{2,4}\d{6,8}\b"` for **detecting** Bates numbers in imported text, not
  generating them. Archived wiki tree.
- **packet** — ~30 hits, overwhelmingly `docs/awaiting-verification/`, `docs/plans/` pre-mortems, and the
  forensic-db-architecture planning tree. One is COORDINATION.md's "R11 owner packet" (a sign-off
  document, unrelated to legal exhibit packets).
- **disclosure** — 100+ hits, overwhelmingly the ADR-0018 **disclosure-tier** bitemporal concept.

**Answer:** the only substantive exhibit/bundle design lives in
`docs/planning/forensic-db-architecture/FORENSIC_DB_ARCHITECTURE_DRAFT.md` (729KB) and its `sections/`:
- `sections/12-evidence-plan.md:113-114` — a table row: *"Court-ready exhibits | gated by HITL;
  produced by export lane (§9 provenance) … | Evidence packets | assembled downstream from `verified`
  tasks | feeds §9 `provenance.export`"*.
- `sections/20-workproduct-memory.md` — an `artifact_registry` schema including enum values
  `court_export_draft` and `human_review_packet` with HITL gating.

**But this document is explicitly a DRAFT, not ratified:** *"⚠ DRAFT — HUMAN-IN-THE-LOOP REVIEW
REQUIRED ⚠ … NOT a ratified specification and NOT a court-facing artifact… on any conflict the SSOT
docs (PROJECT_CANON.md + ADRs) win over this draft."* Dated 2026-06-30, modified through 2026-08-05,
never promoted into an ADR or canon. Cross-checked: neither PROJECT_CANON §5 nor DEBT.md reflects any
of this draft's export-lane/artifact_registry design as adopted. No later ADR (0057/0058/0059) picks up
"evidence packet" or "court_export_draft" terminology.

**Partially-live counterpoint:** `analysis.vw_court_export`, a **read-only court-export-READINESS view**
(commit `7b6aaf6`, per `docs/BUILD_PLAN.md:60-64` and
`docs/plans/COURT-READINESS-pre-mortem-2026-08-15.md`). Reports whether a promoted evidence item is a
member of the view and whether it passes stricter readiness checks. **Performs no release mutation and
produces no document/bundle output** — a status row for one item at a time. Status: "COMPLETE LOCALLY —
read-only slice; no schema, mutation, deployment, or legal-release action."

**Bottom line:** no authoritative doc describes bundling/exhibit assembly as BUILT. It is aspirational
in one large unratified DRAFT. The one real committed artifact is a narrow read-only readiness view.
Nothing says the feature is formally "deferred" — it has simply never been scoped into an ADR, the
roadmap, or the debt register at all.

## 7. Dead-weight audit

- **`to_be_deleted/`** — **empty.** Zero files, no README. A fully-drained staging folder.
- **`_stale/`** — 8 items, all consistent with archival intent (matches the never-delete rule):
  `00_analysis_graph.surql.SUPERSEDED`, `compose.browser.yaml.SUPERSEDED`,
  `compose.data.yaml.SUPERSEDED`, `compose.ui.yaml.SUPERSEDED`, `gen_validate_0008.py.SUPERSEDED`,
  `git-index.lock-stale-20260810`, `index.lock.git-debris-20260810-0157`,
  `sbv_sms_map_message_legacy.py`. The `.SUPERSEDED` suffix is self-documenting. **Live and correctly
  used, not dead weight.**
- **`vendored/` (root) and `server/vendored/`** — real, actively-referenced, NOT dead weight:
  `vendored/sbv/` (SBV Go forensic-parser fork; ADR-0048/0049, canon §6 P4 "largely landed"),
  `server/vendored/chatminer/` (ADR-0035), `server/vendored/semantica/` (ADR-0043).
- **`scripts.zip` (134,398 B) and `server/tools.zip` (408,503 B)** — both dated 2026-08-09 15:53
  (same batch). Not unzipped. **Not referenced anywhere in `docs/`** (grep returned zero). No manifest
  explains why they exist alongside the live unzipped dirs. Best guess (UNVERIFIED): pre-refactor
  snapshots from the 2026-08-09 docs true-up. **Flag as unexplained dead weight** for owner decision.
- **`AGENTS.md.backup_*`** — three backups + live file. Diffs against live: 128 / 115 / 71 lines
  (oldest→newest), **monotonically converging** — a pre-edit-snapshot convention, not drift. The live
  file gained: mandatory integration tests, a "Documentation lifecycle" section, an "Owner delivery
  rule — production means production" section (2026-08-18), a "Repository-wide discovery rule"
  (CocoIndex/ccc), and the full "LIVE ONLY, SPRINT MODE" policy block (2026-08-20) — the same block
  that appears verbatim in the user's global `~/.claude/CLAUDE.md`, confirming they are synchronized.
- **`knowledge/`** — real subsystem, lightly populated: `legal/` (2 coercive-control rubrics),
  `personal_history/README.md`, `platform/conversations/` (2 perplexity txt), `platform/docs/` (2 docs),
  `platform/notes/.gitkeep`, `relationship_timeline/README.md`. Each populated dir carries a one-line
  README per **ADR-0050** ("Drop curated source docs here; `scripts/ingest_knowledge.py` walks this root…
  NEVER case evidence"). Real, structurally correct, **sparsely populated**. Note ADR-0050 is itself
  marked "Superseded in part by ADR-0053" — worth confirming the ingest script still targets the right
  structure.
- **`iceberg` (repo root)** — **NOT a directory, a single file.** `file` reports **"DuckDB database
  file, version 64"**, 12,288 bytes. Querying it (`SHOW TABLES`) returns **`[]`** — zero tables. An
  essentially empty stray DuckDB file named `iceberg`, NOT an Apache Iceberg catalog. **Flag as dead
  weight / naming trap**; candidate for `_stale/`.
- **`analytics/`** — **real, working integration.** An Evidence.dev BI project at
  `analytics/visit-locations/`: README (Claude Code · Fable 5 · 2026-07-05, updated Codex · GPT-5 ·
  2026-08-14) describing 3 real pages (index verification table of 93 locations, per-location and
  per-group drill-downs), `sources/visits/` + `data/visit_locations_2023_clustered.original.csv`
  (10,332 B, 93 clustered locations), `evidence.config.yaml`, `package.json`, `pages/`. A genuine
  buildable app. **Flag for reconciliation** against the owner's "Takeout Timeline = PARKED" rule — it
  is dated 2026-07-05 and may be a pre-existing approved exception rather than a violation; nothing in
  `docs/` reconciles it either way.

## 8. `docs/COORDINATION.md` — explains the backup churn

Active multi-lane, multi-agent-session workflow:

- **2026-08-15 "framework-neutral migration lanes"** — 10 lettered lanes (R0–R9), mostly Codex·GPT-5,
  all "Partial"/"held"/"no cutover". **R9 Matter MVP** ties to the `7b6aaf6` court-readiness commit —
  "Built/tested and pushed; readiness `7b6aaf6`; migration unapplied, undeployed."
- **2026-08-15 "R10 Surreal analytical memory and investigation design"** — 5 sub-lanes R10A–R10E.
  **R10E "Retrieval"**: *"Source-aware chunks, multi-axis routing, versioned isolated embedding
  profiles, rank fusion + reranking | Proposed contracts; bake-off required"* — direct confirmation
  that search/retrieval design is at the proposed-contract stage, NOT built.
  **R10B "Facts"**: *"Candidate-driven federated evidence assembly → reviewed immutable fact subgraphs |
  Accepted design; no schema"* — ADR-0057's concept, confirmed schema-less.
- **2026-08-16 "R11 Surreal investigation Phase 0 review package"** — contracts/evaluation/canary only;
  "changed no application, database, migration, deployment, corpus, or service state."
- **2026-08-18 "R14/ADR-0059"** and "Production delivery rule and authoritative resume documents" —
  newest entries, tying back to MASTER-TODO-2026-08-18 and the evidence-desk-mvp handoff.

This explains the `.backup_<timestamp>` siblings across COORDINATION.md, DEBT.md, DECISION_LOG.md,
PROJECT_CANON.md, CHANGE-ORDER.md, ADR files, and AGENTS.md: multiple lettered lanes worked by
concurrent/sequential agent sessions against a shared doc set, each taking a pre-edit snapshot. Not
disagreement or corruption — a heavy-handed manual versioning convention layered on top of git.

## Overall summary for this lane

1. **Ingest**: architecturally designed (ADR-0017/0044/0053), partially built (parsers vendored and
   working, custody hashing live via SBV), but **schema population by a real end-to-end pipeline is
   explicitly "planned"** per DEBT.md and canon §6; per MASTER-TODO the whole custody/ingest/normalize
   surface is "IMPLEMENTED LOCAL ONLY."
2. **Search/retrieval**: the vector substrate (Weaviate) is live, but the evidence-specific retrieval
   design (source-aware chunking, multi-axis routing, rank fusion + reranking — R10E) is at "proposed
   contracts; bake-off required," i.e. **not built**. Native evidence-vector cutover (D-066) is
   "activation held."
3. **Evidence bundling / exhibit assembly**: **no built feature exists.** The only real artifact is a
   narrow, local-only, read-only court-export-READINESS view producing no document. The larger
   "court_export_draft"/"human_review_packet" vision exists only in one explicitly-disclaimed,
   unratified DRAFT that canon and later ADRs never adopted. Nothing formally defers it — it has simply
   never been scoped.
4. **Dead weight**: `to_be_deleted/` empty; `_stale/` legitimately archival; `vendored/` load-bearing;
   `scripts.zip`/`server/tools.zip` unexplained; root `iceberg` file is an empty DuckDB red herring;
   `knowledge/` real but sparse; `analytics/visit-locations` real and working, needs reconciliation
   against the Timeline-parked rule.

---

> _Note added 2026-08-25 by Claude Code · Fable 5: the LIVE-ONLY / grounded-mode testing policy referenced above was REMOVED by owner order ("you're grounded — remove it entirely"). Text above is historical record, left intact per the doc-drift rule; it no longer reflects active policy. Confirm-and-discuss-before-changing is back in force._
