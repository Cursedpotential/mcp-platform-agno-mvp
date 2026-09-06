# Open-Work Register — every unfinished thing hiding in `docs/`

> _Byline: Claude Code · Opus 5 · 2026-09-05_
> _(Session began 2026-09-05; assembled across the 09-05/09-06 boundary.)_

**STATUS: ITERATING — NOT DONE. Done only when the owner says so.**

## Why this document exists

The owner's directive, verbatim: *"Ensure that if it's pushed aside or archived or moved out
of the working space that everything has been completed. Not all been completed — it needs to
be recompiled into a new document."*

This is that document. **Nothing may be archived until its open items appear here.** That is
the gate, and it is the whole point of the consolidation.

## How to read it

| Column | Meaning |
|---|---|
| **ID** | `OW-nnn`, stable. Cite it when closing an item. |
| **Item** | What is actually unfinished, in one sentence. |
| **Source** | The document it was found in — the doc that cannot be archived until this row exists. |
| **Raised** | Date first raised in that source. |
| **Evidence** | What was checked to determine the current status, this pass. |
| **Status** | `OPEN` · `OWNER` (needs an owner decision) · `DONE-NOT-CLOSED` (landed, doc never updated) · `SUPERSEDED` · `STALE-CLAIM` (the doc's assertion is now wrong). |

### Scope boundary — read before using this as a to-do list

This register captures **open work discovered in documents being considered for archive**, plus
the open items of the living registers those documents point at. It does **not** replace the
living registers themselves, which stay in place and stay authoritative:

- `docs/URGENT-TODO.md` — the loud stub/broken/deferred register (rows 1–33+).
- `docs/DEBT.md` — the activation-hold and technical-debt register.
- `docs/DOC_DEBT.md` — the documentation backlog.
- `docs/GUARD-TRIGGER-DISPOSITION.md` — the 131 guard triggers and their four buckets.
- `docs/MASTER-TODO-2026-08-18.md` — the production resume ledger.
- `docs/reviews/2026-09-05-ingest-day-live-chain.md` — the current ingest-day state.

Where a row below points at one of those, the register row is a **pointer**, not a copy. Copying
them here would create a seventh competing ledger, which is the disease, not the cure.

### Owner-grounded triage principle (D-142, 2026-09-05)

> Owner, 2026-09-05 (late): *"We have zero committed and live evidence… All we have is
> reference materials, training materials, tables of examples, definitions,"* and *"trying to
> preserve shit that isn't actually there is what drove two weeks worth of bullshit with the
> databases… you need to remember that."*

D-142's design discipline applies to documents exactly as it applies to schemas: **"no plan,
pre-mortem, migration step, or 'keep this path for the data' caveat may be written to protect a
stock that is empty. First question is always 'does that data exist yet?'"** Several rows below
are marked SUPERSEDED for precisely that reason — they guard work whose subject no longer
exists.

---

## P0 — act before anything is moved

| ID | Item | Source | Raised | Evidence | Status |
|---|---|---|---|---|---|
| OW-001 | **Credential-shaped literals are committed in git-tracked documentation.** Five tracked files under `docs/` contain values in `KEY=value` form for `MYSQL_ROOT_PASSWORD`, `MYSQL_PASSWORD`, `POSTGRES_PASSWORD`, `CHROMA_API_KEY`, `LITELLM_MASTER_KEY`, `DIRECTUS_TOKEN`, `NEO4J_PASSWORD`, `NEXTAUTH_SECRET`, `JWT_SECRET`, `OPENAI_API_KEY`. Files: `docs/wiki/archive/.planning/agent-reviews/agent-reviews/02-security-audit.md`, `.../agent-reviews/HANDOFF_TO_GEMINI.md`, `docs/wiki/archive/.planning/codebase/INTEGRATIONS_LEGACY.md`, `docs/wiki/.plannotator/history/cusersmatts/plan-docker-compose-service-pr-2026-03-07/001.md`, `docs/planning/Claude - chat pipeline for PostgreSQL - Claude.md`. The values describe a **different project's** `deploy/salem-trinity/phase3-vps3-platform/.env`, so they may be long dead — but that is the owner's call, not an auditor's. | wiki + planning trees | 2026-03 (imported) | `git ls-files --error-unmatch` returns success on the file; `git grep -l` finds the literal in 2 tracked files and credential-shaped assignments in 5. Values were **not** printed in this audit. | **OWNER — the git-tracked hard line.** Decide: rotate, redact-in-place, or accept-as-dead. Archiving these files does not remove them from git history. |
| OW-002 | **`docs/archive/` was created 2026-08-18 and has never been used.** It contains exactly one file: its own `README.md`. Every "archive it" decision since has stopped at proposal. | `docs/archive/README.md` | 2026-08-18 | `find docs/archive -type f` → 1 file. Last commit touching it: `1598bb0`, 2026-08-23. | **OPEN** — this consolidation's move manifest is the fix. |
| OW-003 | **`DOC_CLEANUP_MANIFEST-2026-08-15.md` proposed a quarantine set that was never executed**, and carries five UNRESOLVED questions: canonical blueprint location (`docs/blueprint/` vs `.agents/blueprint/`); which compact summaries hold unique facts; whether inactive deployment manifests are rollback assets; whether the Knowledge/Matter implementation is approved for deployment; when migrations `0026`–`0030` get approved. | `docs/DOC_CLEANUP_MANIFEST-2026-08-15.md` | 2026-08-15 | Its own STATUS: "ENTRY-POINT REPAIR COMPLETE; QUARANTINE STILL PROPOSED — no files moved or deleted". Migration sub-question is now answered (OW-030). | **OWNER** on the first three; the migration question is DONE-NOT-CLOSED. |
| OW-004 | **`docs/awaiting-verification/` disposition was inventoried 2026-09-01 and never ruled on.** 75 files were classified 13 verified→archive · ~37 stale→quarantine · ~25 still-pending→keep, "report-only; owner rules on each" (H-09 task 3). No ruling exists. | `docs/CLAIMED_COMPLETE_LIKELY_LIES/awaiting-verification-inventory-20260901.md` | 2026-09-01 | The tree still holds 78 files; `docs/archive/` is empty. | **OWNER** — the single biggest unblocked decision in this consolidation. |

---

## P1 — live build work, currently open

| ID | Item | Source | Raised | Evidence | Status |
|---|---|---|---|---|---|
| OW-010 | **NUL bytes (`0x00`) in raw records need a ruled substitution strategy.** PostgreSQL TEXT cannot store them; D-136 holds content immutable with byte-exactness in the envelope/H2 hash, but the TEXT rendering needs a ruled substitution plus a `sanitized` flag. Parse-to-raw cannot be proven until this is ruled. | `docs/reviews/2026-09-05-ingest-day-live-chain.md` §"Open owner rulings" 1 | 2026-09-05 | Live: run `r2f-1788614408` failed at `execute_parser` with `invalid byte sequence for encoding "UTF8": 0x00` on `element:8`. | **OWNER — blocking.** |
| OW-011 | **n8n→worker webhook error contract.** A parser 4xx surfaces to Temporal as an opaque `decode n8n StageResult: EOF` instead of a typed `StageResult` error. "Needs a contract fix, not another silent catch." | same, §"Open owner rulings" 2 | 2026-09-05 | Observed live on the same run. | **OPEN** |
| OW-012 | **Owner is blocked on two concrete actions, unchanged since 2026-09-02:** mint a tagged (`tag:docker`) Tailscale auth key for the gateway, and add the shared materialize mount to platform-tools. | `docs/planning/2026-09-03-ingest-simplification-plan.md:294` | 2026-09-02 | Not resolved in DECISION_LOG or SETTLED.md. *(The materialize mount appears to have landed via `7feea1f`/deployment `l9y8ft…`; the auth key is separate.)* | **OWNER** — re-confirm which half remains. |
| OW-013 | **Migration-ledger backfill decision.** The ledger held 0 rows before 2026-09-05 and now holds exactly the two rows for `0071`/`0072`. Whether to backfill it for migrations already live on `platform` is an explicit open owner decision. | `docs/reviews/2026-09-05-ingest-day-live-chain.md` §"Migration ledger note" | 2026-09-05 | Stated verbatim as "not yet made". | **OWNER** |
| OW-014 | **Weaviate `EvidenceChunkV1` holds 0 objects; the write probe is blocked on zero chunk rows because the Go chunker is unbuilt.** | `docs/reviews/2026-09-05-ingest-day-live-chain.md` "What's live now" table | 2026-09-05 | Class created at 2048-d; 0 objects. | **OPEN** |
| OW-015 | **Two identical Weaviate instances still run; the D-066 native-evidence cutover was stood up and abandoned.** `EvidenceChunkV1` existed in neither at the time; `Evidence_knowledge` is 0 objects in both; the alias resolves to nothing. `WEAVIATE_HTTP_PORT` defaults to `8082` — the instance never cut over to. | `docs/DECISION_LOG.md` D-104; `docs/plans/WEAVIATE-NATIVE-EVIDENCE-CUTOVER-RUNBOOK-2026-08-18.md` | 2026-08-18 / 2026-08-29 | D-104 states "**Owner decision required: finish the cutover, or retire the blue instance.**" | **OWNER — blocking**, and named as such in the decision log. |
| OW-016 | **Structure-preserving chunking has no viable candidate** (measured 2026-08-29). `sql/0072`'s chunk↔message bridge addresses linkage, not chunker quality. | `docs/HANDOFF-2026-08-29-derived-document-ingest-wiring.md` WP-1..9 | 2026-08-29 | No closing ruling in SETTLED.md. | **OPEN** |
| OW-017 | **DOCX / PPTX / XLSX / HTML ingest fails on a default install.** `server/ingest/service.py:_extract_document` appends the `documents.extract-text` fallback only for `.pdf`; `docling` lives in the `document-ai` extra and is absent from `requirements.txt`, so the extractor registers then raises at call time. | `docs/URGENT-TODO.md` #17; `HANDOFF-2026-08-29-derived-document-ingest-wiring.md` WP-11 | 2026-08-23 | Still marked OPEN in URGENT-TODO; no closing entry found. | **OPEN** |
| OW-018 | **Scanned / image-only PDFs do not OCR by default.** `pytesseract` + `pdf2image` live in the `ocr` extra and are absent from `requirements.txt`. Scanned exhibits ingest as empty text, silently. | `docs/URGENT-TODO.md` #18; same handoff WP-10 | 2026-08-23 | Same. | **OPEN** |
| OW-019 | **The evidence lane cannot ingest PDFs or DOCX at all.** `server/ingest/service.py:197` skips document extraction entirely for `IngestLane.evidence`; combined with the `_whole_file_text` ban (ADR-0044) a scanned court order has **no ingest path into the evidence lane**. | `docs/URGENT-TODO.md` #19 | 2026-08-23 | URGENT-TODO marks it "OPEN — needs an owner ruling on whether this is intended (ADR-0044 scope)". | **OWNER** |
| OW-020 | **Finish and prove the OCR/document-extraction surface** — contract tests plus addressable structural-output proof. | `docs/MASTER-TODO-2026-08-18.md:111` | 2026-08-30 | Unchecked; matches OW-017/018/019. | **OPEN** |
| OW-021 | **Tool-gateway watch paths were changed via the Coolify API and the change was never recorded formally.** | `docs/reviews/2026-09-05-ingest-day-live-chain.md` §"Owed follow-ups" | 2026-09-05 | Stated verbatim. | **OPEN** |
| OW-022 | **A probe fixture was left on ovh-app** at `/data/agno/volumes/tool-gateway/materialize/probe-fixture.xml`; never-delete applies, so the owner clears it. | same | 2026-09-05 | Stated verbatim. | **OWNER** |
| OW-023 | **A stray `.review_hold/store_…txt.body` from an aborted heredoc needs quarantine review.** | same | 2026-09-05 | Present in `git status` as untracked. | **OPEN** |
| OW-024 | **Root `AGENTS.md` `deploy/docker/` row and `deploy/compose.yaml`'s platform-tools block still need reconciling against the 2026-09-01 restructure.** | same, §"Owed follow-ups" | 2026-09-05 | Stated verbatim as owed. | **OPEN** *(a concurrent session is editing `AGENTS.md` for the rename; check before duplicating)* |
| OW-025 | **`docs/reviews/2026-08-29-sbv-workbench-preview-client-refactor.md` carries `REVIEW_STATUS: … RE-REVIEW REQUIRED`** and no re-review receipt exists. | that file | 2026-08-29 | No later review found closing it. | **OPEN** |
| OW-026 | **NocoDB quarantine — "STOPPED — OWNER DELETE PENDING".** | `docs/reviews/2026-08-29-nocodb-quarantine-receipt.md:5` | 2026-08-29 | No later doc, D-entry or SETTLED row addresses it. | **OWNER** |
| OW-027 | **OCR / semantic-chunking / compact-tagging options are "pending owner review; research and design only".** | `docs/CLAIMED_COMPLETE_LIKELY_LIES/OCR-SEMANTIC-CHUNKING-AND-TAGGING-OPTIONS-2026-08-30.md` | 2026-08-30 | No ruling anywhere. Overlaps OW-016/017/018. | **OWNER** |
| OW-028 | **Golden-clone template + teardown mechanism** for the working database (schema + `reference.*` + labels), replacing purge/migrate. Assigned by the owner to "the ingest session that has a full ingest test on hold (hundreds of errors) awaiting the rename." | `docs/DECISION_LOG.md` D-142 item 3 | 2026-09-05 | Ruled and assigned; not built. | **OPEN — assigned** |
| OW-029 | **The full ingest test is on hold with "hundreds of errors", blocking on the rename.** | same | 2026-09-05 | Stated verbatim in D-142. | **OPEN — blocked** |

---

## P2 — held activations and the deploy backlog

These are the "BUILT / HELD / UNDEPLOYED / ACTIVATION HELD" statuses scattered across
`docs/plans/` and `docs/DEBT.md`. Each source document is archivable **only** because its hold
is recorded here.

| ID | Item | Source | Raised | Evidence | Status |
|---|---|---|---|---|---|
| OW-030 | **Migrations `0026`–`0030` are APPLIED**, but five plan documents still say "BUILT, HELD, UNAPPLIED" / "NOT applied to prod; NOT pushed". | `docs/plans/MATTER-FOUNDATION-pre-mortem-2026-08-15.md`, `WAVE1-W1.2/W1.3/W1.4/W1.5-pre-mortem-2026-08-14.md` | 2026-08-14/15 | `docs/INDEX.md`: "Corrected 2026-08-23 (CH-15/CH-16): migrations `0026`–`0030` are **APPLIED** to live PG18 (`100.91.190.107:5432`, db `ai`)" — 0026–0029 found already live behind stale banners, 0030 applied the same night. `docs/CHANGE-ORDER.md` CH-15 repeats it. | **DONE-NOT-CLOSED.** The *feature* (Matter/CourtCase pipeline, native evidence vectors) remains undeployed — that half stays OPEN. |
| OW-031 | **Evidence-vector cutover activation is still held**: live collection creation, PG-chunk backfill, exact count/hash/canary receipt, `EvidenceChunks` alias switch, reader rebinding, and deploy each require their release gate. Preserve the old Agno evidence collection for rollback. | `docs/DEBT.md` (Agno JSON-metadata evidence vectors row) | 2026-08-16 | D-066 activation status unchanged by the migration correction. Related: OW-014, OW-015. | **OPEN** |
| OW-032 | **`agno_app` role cutover not switched over.** The role exists on live PG18 with full grants and is verified non-superuser, but the app still connects as superuser `ai` (`rolsuper=True`, `rolbypassrls=True`, owns all 253 objects), so `sql/0029`'s role-scoping grants are **inert** — a superuser bypasses every GRANT. Cutover is an owner action: set `DB_USER`/`DB_PASS` in Coolify and **redeploy** (env values bake into the rendered compose; a bare restart will not pick it up). | `docs/DEBT.md` (CH-15 row) | 2026-08-23 | Stated verbatim. | **OWNER** |
| OW-033 | **Semantica activation held**: the PostgreSQL adapter is contract-tested but no database write, worker deployment, credential provisioning, projection, promotion, or live corpus execution has been performed. | `docs/DEBT.md`; `docs/plans/SEMANTICA-SWIFT-SLICE4-2026-08-16.md` | 2026-08-16 | Stated verbatim. | **OPEN** |
| OW-034 | **Workbench Vercel-AI-SDK `/copilot` stream activation held** — needs owner approval plus `PORTKEY_CONFIG` / credential provisioning before advancing the branch or redeploying. | `docs/DEBT.md` | 2026-08-16 | Stated verbatim. | **OWNER** |
| OW-035 | **MCP registry activation held** — provision a separate PG database/role on ovh-files, migrate and reconcile the SQLite registry, establish a hosted/enterprise Portkey MCP control plane (the OSS LLM gateway is insufficient proof), publish exact virtual servers, provision credentials, produce correlated ContextForge/Portkey/`ops.audit_ledger` traces, then advance/redeploy. | `docs/DEBT.md`; `docs/plans/MCP-GATEWAY-CHAIN-PHASE1-2026-08-16.md` | 2026-08-16 | Stated verbatim. | **OPEN** |
| OW-036 | **Surreal disposable-slice execution held.** D1/D2 complete; the parked deployment remains denied. R12 requires separate **D3** (target/credential creation) and **D4** (schema/adapter/live-T0) authority. "Do not create an adapter, schema, compose overlay, target, or credential until the matching gate is explicitly approved." | `docs/DEBT.md`; `docs/plans/R12-PHASE1-DISPOSABLE-SLICE-pre-mortem-2026-08-16.md` | 2026-08-16 | Stated verbatim. | **OWNER** |
| OW-037 | **Matter/Workbench feature undeployed** — built locally and verified, never deployed. | `docs/plans/MATTER-WORKBENCH-pre-mortem-2026-08-15.md`, `EVIDENCE-CUSTODY-INSPECTION-pre-mortem-2026-08-15.md` | 2026-08-15 | STATUS lines: "BUILT LOCALLY, VERIFIED, UNDEPLOYED" / "COMMITTED/PUSHED (`be286a8`), UNDEPLOYED". | **OPEN** |
| OW-038 | **`uiw-preview-contract.md` (historical filename; the lane was renamed `proffer`, D-140): upstream Go surface, deployment, and live proof remain.** | `docs/plans/uiw-preview-contract.md` | 2026-08-29 | STATUS line verbatim. Partly overtaken by the 09-05 chain; needs a status pass. | **OPEN** |
| OW-039 | **AgentOS retirement release hold:** deploy and live-prove exec, Workbench, and branch-scoped LibreChat; then replace `server/evidence/workflows.py` and Agno Knowledge/provider/vector/session ownership before any code quarantine. | `docs/DEBT.md` (Horizon Swift MVP audit table) | 2026-08-16 | Stated verbatim; `docs/INDEX.md` still says "held for live Coolify proof". | **OPEN** |
| OW-040 | **`PLATFORM_DEV_AUTH_BYPASS` remains load-bearing** and cannot be retired until OIDC issuance and in-process validation are live and proven. Authentik has never been deployed — no Coolify application exists for it. | `docs/DECISION_LOG.md` D-133 | 2026-09-02 | D-133: "Nobody is to report the dev bypass as nearly retired until OIDC issuance and in-process validation are live and proven." | **OPEN — do not report as nearly done** |
| OW-041 | **`deploy/authentik.yaml` must be reworked, not deployed as written** — it encodes the rejected Traefik forward-auth architecture end to end. | `docs/DECISION_LOG.md` D-133; `docs/reviews/2026-08-29-authentik-traefik-implementation.md`, `2026-08-29-workbench-authentik-ingress.md` | 2026-09-02 | Recorded in SETTLED.md. | **OPEN** |
| OW-042 | **Outbox part 1 was "built + live-validated under rollback; NOT committed, NOT applied"** at the time of writing. | `docs/reviews/2026-09-04-outbox-part1-build.md` | 2026-09-04 | **Superseded within 24h:** `2026-09-05-ingest-day-live-chain.md` shows `sql/0071` applied live, one transaction, `09:54:35Z→09:54:40Z`, ledger 0→2 rows. | **DONE-NOT-CLOSED** |
| OW-043 | **`docs/reviews/2026-09-05-h04-bridge-and-weaviate-feed-rewire.md` header says "BUILT, NOT DEPLOYED… not applied live"** — but the later same-day consolidation reports `sql/0072` applied live. | that file vs `2026-09-05-ingest-day-live-chain.md` | 2026-09-05 | Direct contradiction between two same-day documents; newest wins. Commit `cc182a9`. | **STALE-CLAIM** — the header needs a dated correction. |

---

## P3 — the documentation system's own unfinished work

| ID | Item | Source | Raised | Evidence | Status |
|---|---|---|---|---|---|
| OW-050 | **F2 — the SETTLED.md `UserPromptSubmit` recall hook was proposed and never implemented.** It was explicitly gated on owner sign-off. | `docs/reviews/2026-09-02-relitigation-pattern-and-fix.md` §F2 | 2026-09-02 | Verified: `.claude/settings.json` and `settings.local.json` contain **no** `UserPromptSubmit` hook (only `PreToolUse`, `PreCompact`, `SessionStart`). | **OWNER** — this is the mechanical fix for the re-litigation loop. |
| OW-051 | **F3 — the cite-before-propose test was never added to `AGENTS.md`.** | same, §F3 | 2026-09-02 | Verified: `rg 'RE-OPENING\|cite the governing\|SETTLED' AGENTS.md` → no matches. | **OPEN** |
| OW-052 | **F4 — the owner-verbatim-first recording convention was never added to `docs/CONVENTIONS.md`.** | same, §F4 | 2026-09-02 | Verified: `rg -i verbatim docs/CONVENTIONS.md` → no matches. | **OPEN** |
| OW-053 | **152 broken intra-`docs/` markdown links already exist**, before any file is moved. The 2026-08-15 repair fixed *current entry points* only; the tail was never swept, and the repository-wide historical scan is listed as remaining in that manifest. | mechanical scan, this pass | 2026-08-15 | Link-resolution scan over `docs/**/*.md`: 152 relative targets do not exist. Concentrated in `docs/wiki/**` (~90) and `docs/awaiting-verification/**` (~20). | **OPEN** |
| OW-054 | **`AGENTS.md` points at `docs/pending-review/`, which does not exist.** Also `sql/bootstrap/platform_foundation.sql:23,101` and `tests/test_0048_context_fingerprint_uiw_repair.py:19` reference `docs/pending-review/plans/apply-0036-set-role-patch.md`. | `AGENTS.md:354`, `sql/bootstrap/platform_foundation.sql`, `tests/…` | broke 2026-08-23 | The directory was removed in the `1598bb0` reorg. The referenced plan now lives at `docs/awaiting-verification/plans/apply-0036-set-role-patch.md`. | **OPEN** — pre-existing breakage from the last reorg. |
| OW-055 | **`server/tools/repair/AGENTS.md:57` and `server/tools/repair/quarantine.py:53` name `docs/reports/damaged-artifacts.jsonl`, which does not exist.** (It is gitignored by design, so this may be correct-but-unpopulated — confirm before "fixing".) | those files | — | `docs/reports/README.md`: "everything in this directory except this file is gitignored"; `git ls-files docs/reports` → 0 tracked. | **OPEN — verify intent** |
| OW-056 | **`modules/workbench/AGENT_MEMORY.md:9` points at `docs/reviews/2026-08-27-workbench-auth-rotation.md`, which does not exist.** | that file | — | File absent from `docs/reviews/`. | **OPEN** |
| OW-057 | **Three documents still assert the retired "Milvus is DOWN" framing**, contradicting the 2026-09-03 owner correction: `docs/blueprint/architecture.md:99`, `docs/research/integration-audit-2026-08-24/stage-2-discovery-candidates.md:119`, `docs/reports/mcp-platform-agno-review.md:32`. | those files | 2026-08-11 → 2026-08-24 | `docs/registers/SETTLED.md`: "NEVER say 'Milvus is down'". | **STALE-CLAIM** |
| OW-058 | **`docs/URGENT-TODO.md` row 14 asserts "SurrealDB is formally RETIRED (ADR-0043, owner ruling 2026-08-06)"** as a whole-product claim. D-073/D-080 (2026-08-25) corrected this: only the legacy Agno *operational* adapter is retired; SurrealDB is the governed final temporal-graph/walk/analysis engine. | `docs/URGENT-TODO.md` #14 | 2026-08-20 | `docs/registers/SETTLED.md`: "SurrealDB = governed final temporal-graph/walk/analysis engine; only the legacy Agno operational adapter is retired". | **STALE-CLAIM** — needs strike-through + dated correction, not deletion. |
| OW-059 | **LiteLLM doc-drift across three documents, unresolved since 2026-07-29.** D-030 records retirement as "done (docs; teardown pending)"; `AGENTS.md` says flatly "LiteLLM retired" with no caveat; the container was never torn down and `gateway` on ovh-app still publishes port 4000 with nothing listening. | `docs/OWNER-REVIEW-2026-08-18-verified-todo-audit.md:80-82`; `docs/URGENT-TODO.md` #12, #16 | 2026-07-29 | Both sources still open. | **OPEN** |
| OW-060 | **`docs/CHANGE-ORDER.md` stops at CH-21 (2026-08-24)** despite its own "append in the same turn" rule. Temporal going live, D-130, the n8n go-live and the H-04 bridge are absent from it. | `docs/CHANGE-ORDER.md` | 2026-08-24 | Tail inspection. | **OPEN** |
| OW-061 | **`docs/HANDOFFS.md` R0 row still says "migrations held"**, never updated after the 2026-08-23 correction. | `docs/HANDOFFS.md:16` | 2026-08-15 | See OW-030. | **STALE-CLAIM** |
| OW-062 | **`docs/DOC_DEBT.md` has 9 open rows**, seeded 2026-06-13 and never worked: vendored `chatminer` internals (`core/base.py`, `core/types.py`, `core/pipeline.py`, `core/artifacts.py`, `parsers/discovery.py`, `segmenters/`, `skills/`); `server/evidence/schemas/*` canonical model; `server/evidence/config/case_terms*`; ContextForge + SurrealDB integration setup; Part 3 AI Law Firm persona inventory; plus five standing-target boxes. | `docs/DOC_DEBT.md` | 2026-06-13 | Unchecked in the live file. | **OPEN** (pointer — the register stays there) |
| OW-063 | **ADR-0022's comprehensive living wiki was never built.** `docs/wiki/` holds an imported *different project's* wiki ("dial-stack"), not this platform's. | `docs/adr/0022-comprehensive-living-wiki.md` (Accepted, "vision locked; build deferred"); `docs/PROJECT_CANON.md:596` | 2026-06-11 | `docs/wiki/INDEX.md:1-3` documents dial-stack's AI-DIAL/Caddy/Dragonfly/LanceDB stack. | **OWNER** — see the audit's UNCLEAR list. |
| OW-064 | **`docs/wiki/tools/utility/**` duplicates `docs/wiki/project-docs/components/tools/scripts/**`** — 10 byte-identical files, both introduced in the same 2026-06-13 commit (born-duplicate, not drift). | mechanical md5 comparison | 2026-06-13 | 10 exact md5 matches. | **OPEN** — survivor recommendation in the audit. |
| OW-065 | **`docs/wiki/.plannotator/history/**` holds another project's planning cache** — subdirectories named for `dial-stack`, `MCP_Tool_Platform`, `TheBigOne`, `Case Bible`. 51 files, 435 KB. | mechanical inventory | 2026-02/03 | Directory names are sanitized paths of other repositories. | **OWNER** — relocate or archive. |
| OW-066 | **Two documents have no byline**, against the standing byline rule: `docs/runbooks/MIGRATION-0036-CONTEXT-IMPORT.md`, `docs/design/classification-sentiment-test-system.md`. Also `docs/GUARD-TRIGGER-DISPOSITION.md` and `docs/RULINGS-SHEET-2026-08-09.md`. | mechanical scan | — | Byline regex returns empty. | **OPEN** |
| OW-067 | **The `GAP-001`…`GAP-034` register has no disposition pass.** Three gaps have resolution-log entries (GAP-004 partial, GAP-029 model-corrected, GAP-032 partial); the other 31 describe a database and AgentOS wiring torn down and rebuilt since (D-108…D-121, D-142) and AgentOS retired (D-107) — but **none carries a "moot because rebuilt" disposition**. | `docs/reviews/2026-08-25-schema-audit/AUDIT-GAP-REGISTER.md` | 2026-08-26 | Register read this pass. | **OPEN** — needs the same disposition pass `awaiting-verification-inventory-20260901.md` gave its own batch. |
| OW-068 | **`GAP-029`'s table row still states the original stricter acceptance criteria**; the resolution log records the owner's 2026-08-26 model correction (no per-request nonce table; lifecycle-transition proof only). A reader of the table alone gets the wrong bar. | same | 2026-08-26 | Table vs resolution-log mismatch inside one file. | **STALE-CLAIM** |
| OW-069 | **The `ISS-001`…`ISS-047+` cross-repo register has no disposition pass.** Some map onto later rulings (ISS-002 → D-124/D-077; ISS-006 → the two-chain clarification; ISS-023 Graphiti write-only → moot). Most P1 "missing capability" items (evidence bundling, EDRM export, cross-corpus search, exhibit-ID service) have **no later ruling and are likely genuinely still missing**. | `docs/reviews/2026-08-23-cross-repo-evidence-audit/ISSUES-AND-TODO.md` | 2026-08-23 | Register read this pass. | **OPEN** |
| OW-070 | **251 unchecked checkboxes across `docs/reviews/**` and `docs/CLAIMED_COMPLETE_LIKELY_LIES/**` were not individually triaged.** Concentrated in `TIMESKETCH-*`, `PARALLEL-GAP-EXECUTION-BOARD.md`, `SEMANTIC-AGENT-WORK-PACKAGES.md`, and the OCR-options doc. | mechanical `rg` sweep | — | Count is mechanical. | **OPEN** — a scoped follow-up pass, honestly declared rather than silently skipped. |
| OW-071 | **The `AUDIT-GAP-REGISTER.md` had to be reconstructed from Codex tool-call history because the original was never committed.** The reconstruction is itself a lost-work incident worth preserving as a lesson. | that file's header | 2026-09-02 | Stated in the file. | **NOTE — no action, keep the lesson** |
| OW-072 | **The H-0x dispatch queue (`repo-rereview` + `handoffs-v2`) needs a closure pass.** H-00 obsolete/done; H-02a DONE (`9da8815`); H-02, H-01, H-03, H-04, H-05, H-06, H-07, H-08/H-08a, H-09, H-10, H-11 were PENDING as of 2026-09-01, and several are likely subsumed by the September rebuild. H-08a specifically: `sql/0062` was written and swept but never applied, there is **no `registry` schema** live, and `0063`/`0064` were applied on top of the skipped `0062` while code still references `registry.*`. | `docs/CLAIMED_COMPLETE_LIKELY_LIES/handoffs-v2-validation-and-dispatch-plan.md`, `repo-rereview-validation-and-dispatch-2026-09-01.md` | 2026-09-01 | The dispatch table itself. H-04 has since progressed (`cc182a9`). | **OWNER** — one reconciliation pass over the H-0x list. |
| OW-073 | **The `.gitattributes` at repo root and `.github/workflows/validate.yml` (the only CI) were deleted during the H-09/H-10 parking-lot move.** Restoration was recommended 2026-09-01. | `handoffs-v2-validation-and-dispatch-plan.md` | 2026-09-01 | Flagged with "⚠". | **OPEN — verify current state** |

---

## P4 — infrastructure and fleet (pointer rows)

`docs/URGENT-TODO.md` is the live register for these. They are listed by number only, so the
register does not become a second copy that drifts.

| ID | Item | Source | Status |
|---|---|---|---|
| OW-080 | Docker subnet `192.168.0.0/20` collides with the owner's home LAN `192.168.10.0/24` on ovh-files and ovh-app; ovh-files and ovh-app use identical docker subnets so Tailscale can route only one host per CIDR; the fix (`default-address-pools` per host) requires recreating networks = restart all stacks. | URGENT-TODO #1, #2, #3 | **OPEN** |
| OW-081 | Traefik binds `0.0.0.0` on all four hosts; port 8080 published to `0.0.0.0` on all four with nothing behind it. | URGENT-TODO #4, #5 | **OPEN** |
| OW-082 | `Secrets/PLATFORM_REFERENCE.md` badly stale — `chat.` / `browser.` / `n8n.` / `milvus.` / `attu.` / `windmill.` subdomains all 503, containers absent. | URGENT-TODO #6 | **OPEN** |
| OW-083 | Coolify `*.sslip.io` domains catalogued but not wired to Traefik — they 404 and are not working hostnames. | URGENT-TODO #7 | **OPEN** |
| OW-084 | ovh-data VPS still needs terminating at OVH (billing; owner-only). Host powered off 2026-08-20; the disk with 5.1 GB of Surreal data is intact until termination. | URGENT-TODO #9 | **OWNER** |
| OW-085 | OVH private network never came up — netplan configures `ens7`, the actual second NIC is `ens4` (DOWN). Historical hazard: a `10.1.x` route once blackholed the owner's public IPv4 (2026-06-25) — re-check before advertising anything in 10.1.x. | URGENT-TODO #11, #13 | **OPEN** |
| OW-086 | Two Weaviate instances on ovh-files unexplained in every session log (`weaviate-o97r85b7`:8081 vs `weaviate-native-v1-v43tfq`:8082). Do not touch either until the owner decides. Same subject as OW-015. | URGENT-TODO #15 | **OWNER** |
| OW-087 | Brave AI web search still blocked — needs an owner-supplied key; Brave takes priority over SearXNG when both are set. (SearXNG itself: RESOLVED 2026-08-24.) | URGENT-TODO #21 | **OWNER** |
| OW-088 | n8n log streaming left UI-managed — needs a real destination URL (webhook/syslog/sentry). | URGENT-TODO #22 | **OPEN** |
| OW-089 | n8n owner account must be re-created after the SQLite→Postgres cutover (one-time manual setup). | URGENT-TODO #25 | **OWNER** |
| OW-090 | Coolify + fleet cleanup (owner order 2026-08-24): full triage table per server, mine-before-retiring, owner approves the kill/quarantine list. | URGENT-TODO §2026-08-24 | **OPEN** |
| OW-091 | Duplicate folders need consolidating — TESTS, EVALS, BUILD in particular (owner order 2026-08-24). *(Partly done: ADR-0054 amended 2026-09-01 fixed the tests/reports split.)* | URGENT-TODO §2026-08-24 | **OPEN** |
| OW-092 | `EvidenceChunkV1` needs numeric epoch mirror fields (`occurred_at_epoch`, `source_available_from_epoch`) added **before** backfill — n8n's Weaviate node range filters take numbers only; retrofitting later means a full re-projection. | URGENT-TODO §2026-08-24 | **OPEN — time-sensitive** |
| OW-093 | Cloudflare global API key rotation (owner-only; leaked in old repos, redacted 2026-07-04); revoke the one-time Tailscale auth key; rotate the Cloudflare token passed through chat. | `docs/COORDINATION.md:165`, `docs/INFRASTRUCTURE.md:82` | **OWNER** |
| OW-094 | Confirm n8n is not deployed from the old `deploy/n8n/` path (now `deploy/docker/n8n/`). | `docs/COORDINATION.md:166` | **OPEN** |
| OW-095 | `restore-heic` — find a better solution (owner: wants HEIC functional someday, down the road). | `docs/COORDINATION.md:182` | **OPEN — parked** |
| OW-096 | Enable the Coolify instance FQDN + dashboard TLS; decommission IONOS n8n after OVH-2 n8n is verified; finalize OVH-1 proxy strategy. | `docs/INFRASTRUCTURE.md:79-83` | **OPEN** |

---

## P5 — open questions inherited from documents proposed for archive

Each row is the reason its source document is classified **UNCLEAR** rather than ARCHIVE-CLEAN
in the audit.

| ID | Item | Source | Raised | Status |
|---|---|---|---|---|
| OW-100 | Seven GUI/shell open questions: UI shell placement (same-repo vs sibling); auth strategy (single vs per-surface JWT); how much AgentOS UI to keep or port; Kasm/OpenCode nav treatment; ContextForge version drift (0.8.0 vs 1.0.3); evidence-browser vs tool-catalog as the real MVP; `get_ref` content-cache location. | `docs/planning/gui-integration-spec.md` §8 | 2026-07-04 | **OWNER** — several are moot by implementation fact (`modules/workbench/` exists), none by ruling. |
| OW-101 | Three re-ingest ETL questions: SQL migration merge order (`sql/0008`–`0015` vs rebase); who productionizes `e2e_stream.py` into a real workflow; whether Phase-2 volume runs wait for the Semantica/NER extractor or proceed raw→working-only. | `docs/planning/reingest-etl-pipeline.md` §7 | 2026-08-02 | **OWNER** — largely overtaken by the 2026-09-03 ingest plans; needs a reconciliation, not a resurrection. |
| OW-102 | `messaging-csv` parser and `documents.extract-text` / `imessage_pdf` marked "blocked, fix required". | `docs/planning/reingest-etl-pipeline.md:150-152` | 2026-08-02 | **LIKELY DONE** — SETTLED.md records 11 live parsers in the Go tools gateway (2026-09-02/03) and mandates inventorying the gateway before proposing any parser build. Spot-check the two specific blockers against the current gateway roster. |
| OW-103 | Port-backlog items from the donor repos have no reconciliation pass; `server/mcp/auth/api-keys.ts` reimplementation is "DEBT: deferred until auth lands", and auth has not landed. | `docs/planning/port-backlog.md:60` | 2026-07-04 | **OPEN** |
| OW-104 | ContextForge adoption list: "Nothing adopted yet — this is the worklist," plus one scope change never confirmed to take effect. | `docs/planning/contextforge-adoption-list.md` | 2026-07-31 | **OPEN — trivial to re-verify live** |
| OW-105 | agno cookbook `08_learning` section never walked; a mount-and-compliance question referencing "HANDOFF-2026-08-01 pending decisions" is unresolved. | `docs/planning/agno-cookbook-adoptions.md:124-129` | 2026-08-02 | **OPEN** |
| OW-106 | The transcript-mining pipeline spec is a 2026-06-19 draft, but a `transcript_miner` agent now exists in the live topology — built or not is unrecorded. | `docs/planning/transcript-mining-pipeline-spec.md` | 2026-06-19 | **UNCLEAR — cross-check `server/agents/`** |
| OW-107 | `docs/planning/architecture-directives/` declares itself "ACTIVE design directives, not archived history" while every individual file is marked DRAFT / DESIGN-ONLY / not-deployed, three months and many ADRs later. | that directory's `INDEX.md` | 2026-06-14 | **OWNER** — active or archive; it cannot be both. |
| OW-108 | `docs/plans/MATTER-WORKBENCH` era Matter-MVP decisions: "get the 15 pending Matter-MVP decisions in front of the owner"; "add the five missing surfaces"; "decide whether `PLAN-2026-08-15-platform-runtime-migration.md` is live scope or shelved". | `docs/OWNER-REVIEW-2026-08-18-verified-todo-audit.md` tail 6–8 | 2026-08-18 | **OWNER** — no ruling row found for any of the three. |
| OW-109 | "Retrieval-side horizon filtering has zero wiring"; "Phase 4 agent→lane wiring confirmed not started"; "evals harness `CASES=()` stub, R2 blob-upload `dry_run`, recurring-backup lane (Neo4j/Milvus not covered)". | same, tail 9–11 | 2026-08-18 | **OPEN** — nothing closes these. **OW-109a (horizon filtering) is the project's core mechanism; treat it as the highest-value open item in this table.** |
| OW-110 | Analysis-engine (`indagatio`) split-off: what moves, what stays, and the `probata`↔`indagatio` boundary contract are explicitly deferred to a separate plan. | `docs/DECISION_LOG.md` D-139 | 2026-09-05 | **OPEN by design** |
| OW-111 | Rename execution (GitHub repo, Go module path + 97 imports and vendor, parent gitlink, Coolify apps, path-keyed memory dir) is ruled but **not authorized**; it happens under its own plan after the ingest-simplification plan is ratified, or when the owner says go. Includes retirement of the `graphiti*`, `phase1-surreal*`, and `unified-operator-surface` **compose file names** (not the architectures). | `docs/DECISION_LOG.md` D-137/D-138/D-140/D-141/D-142 | 2026-09-03 | **OPEN — gated on owner go** |
| OW-112 | `uiw` / `universal-import` / `ingest` (formerly) unify to one word in both Go and Python; `proffer` is the ruled name for the import lane (D-140). Execution is part of OW-111. | D-138 open items, D-140 | 2026-09-05 | **RULED, not executed** |
| OW-113 | TanStack / Glide data-grid: "declared but not yet installed — a queued integration owned by a separate lane… NOT a loss and NOT a re-decision." | `docs/DECISION_LOG.md` D-129 | 2026-09-02 | **OPEN — queued** |

---

## P6 — surfaced by the `awaiting-verification/` pass

`docs/awaiting-verification/` (78 files) was created 2026-08-18 as a purgatory tree in which
"Every item is `UNVERIFIED`, regardless of a document's own 'complete/live' language." Nothing
has ever been promoted out of it. Its disposition decision is OW-004; these are the individual
open items that must survive that decision.

| ID | Item | Source | Raised | Evidence | Status |
|---|---|---|---|---|---|
| OW-140 | **Six evidence-release questions are genuinely unruled:** R1 combined-or-separate decisions · R2 confidence policy · R3 authentication methods in the first mutation · R4 what redaction means · R5 who may release · R6 custody `released` vs legal release. *(The packet's §A multi-Matter framing — P1 people authority, P3 role cardinality, P5 cross-Matter identity — is **mooted** by D-072: "The platform is permanently one owner and one personal case. Do not build multi-Matter tenancy…")* | `docs/awaiting-verification/plans/PENDING-OWNER-DECISIONS-MATTER-MVP-2026-08-15.md` §B | 2026-08-15 | No D-number in `DECISION_LOG.md` or `SETTLED.md` names R1–R6. Its own STATUS: "PENDING OWNER RULING — review packet only". | **OWNER** — the highest-value unruled packet found in the purgatory tree. |
| OW-141 | **Migration `0046` (the `agno_app` role) has no file in `sql/`.** The role was created live and directly (CH-15) and is verified non-superuser, but there is no migration that reproduces it — the live database cannot be rebuilt from `sql/` alone. This matters more, not less, under D-142's golden-clone-template ruling (OW-028). | `docs/awaiting-verification/PG18-MIGRATION-REHEARSAL-2026-08-29.md`; `docs/DEBT.md` CH-15 row | 2026-08-29 | Verified this pass: `ls sql/0046*` → no file. Numbering gaps also at 0040–0041, 0044–0045, 0068, 0070. The rehearsal doc independently states 0046 "was not applied to the scratch database (role does not exist)". | **OPEN** — reproducibility gap, not a privilege bug. See OW-142 for the privilege half. |
| OW-142 | ~~`scripts/apply_0036_live.py` runs unprivileged instead of `SET LOCAL ROLE context_owner`.~~ **Corrected 2026-09-05 (this pass): the patch LANDED in a different form than proposed.** The script now executes `SET LOCAL ROLE platform_admin` (`scripts/apply_0036_live.py:341`), asserts `platform_admin` is a `MEMBER` of `context_owner` (`:107`), and verifies the `context` schema is owned by `context_owner` (`:151`). | `docs/awaiting-verification/plans/apply-0036-set-role-patch.md` | 2026-08-27 | Read the live script this pass. Two prior audits reported this as still-open by reading the plan, not the code. | **DONE-NOT-CLOSED** |
| OW-143 | **R9 knowledge-to-case MVP: "STATUS remains PARTIAL and BUILD_STATUS remains FAIL for the complete [feature]; live activation still held."** Largest R-series document; no D-number closes it, and Matter/case work has moved under D-072/D-126 since. | `docs/awaiting-verification/handoffs/HANDOFF-2026-08-15-R9-knowledge-to-case-mvp.md` | 2026-08-15 | Its own self-referential closing line. | **OPEN** — re-read against `server/case_management/` before promoting or archiving. |
| OW-144 | **`RELEASE-CUSTODY-2026-08-15`: "PARTIAL — partitioned commits pushed to `main`; nothing applied or deliberately deployed."** Custody hashing has been re-specified since (HASH-TAXONOMY, D-124/D-136), so the doc is stale — but its named commits should be diff-checked before archiving in case any never landed. | `docs/awaiting-verification/plans/RELEASE-CUSTODY-2026-08-15.md` | 2026-08-15 | STATUS line verbatim. | **OPEN — verify named commits** |
| OW-145 | **Two handoffs have no closing status at all** and no D-number records their disposition: `HANDOFF-2026-08-02-pg18-migration-permission-allowlist.md` and `HANDOFF-2026-08-02-semantica-platform-review.md` (34 KB). | those files | 2026-08-02 | No STATUS line; nothing in DECISION_LOG names them. | **OPEN — quick current-state check** |
| OW-146 | **`COMPACT-SUMMARY-2026-08-18.md` exists twice with *diverged*, non-overlapping content.** `docs/COMPACT-SUMMARY-2026-08-18.md` (23 lines, one `10:38:33` entry) vs `docs/awaiting-verification/summaries/COMPACT-SUMMARY-2026-08-18.md` (257 lines, entries up to `09:23:03`). Same log stream, split. Archiving either alone loses the `09:23`–`10:38` boundary. | both files | 2026-08-18 | Different md5s; shared header confirms one stream. | **OPEN — merge before archiving.** This is the one file in the whole consolidation where a naive move is lossy. |
| OW-147 | **The three `opencode-briefs-2026-08-29/` items are implemented locally and never deployed** — 0048 UIW integrity ("IMPLEMENTED AND LOCALLY VERIFIED / NOT APPLIED OR DEPLOYED"), SBV attachment sink ("NOT DEPLOYED / NOT LIVE-PROVEN"), UIW native preview API ("DEPLOYMENT/LIVE PROOF REMAIN"). Live work continues in exactly this area (`modules/engine/temporal/{activities,httpapi}.go`, `cmd/starter/upload_ingress.go`). | those three files + their matching `docs/reviews/2026-08-29-*` receipts | 2026-08-29 | STATUS lines verbatim; git status shows in-flight edits to the same files. | **OPEN — advancing.** Needs a live-deploy verification pass, not a design re-litigation. |
| OW-148 | **Five R-series handoffs are PARTIAL with `BUILD_STATUS: UNKNOWN` and describe a repository layout that no longer exists** (root `engine/`, `workbench/api`, `vendored/sbv`): R1 go-ingestion, R2 horizon-engine, R3 semantica, R6 provider-switching, R7 opencode-workspace. | `docs/awaiting-verification/handoffs/HANDOFF-2026-08-15-R{1,2,3,6,7}-*.md` | 2026-08-15 | STATUS lines; paths verified stale against the current `AGENTS.md` layout table. | **OPEN — re-audit, do not promote as-is** |

---

## Items confirmed DONE that their documents still show as open

Recorded so the mover can archive those documents with confidence, and so nobody re-opens them.

| ID | Item | Doc still says | Proof it landed |
|---|---|---|---|
| OW-120 | Migrations `0026`–`0030` | "BUILT, HELD, UNAPPLIED" in 5 plans; "migrations held" in `HANDOFFS.md:16` | `docs/INDEX.md` 2026-08-23 correction (CH-15/CH-16); `docs/CHANGE-ORDER.md` CH-15. See OW-030. |
| OW-121 | Migration `0024` apply | unchecked box in `docs/plans/chat-ingest-pipeline.md:33` | `sql/` now runs to `0072`; `0024` long since superseded. |
| OW-122 | Temporal adoption decision | `TEMPORAL-INTEGRATION-PLAN-2026-08-23.md`: "ADR-precursor… no decision recorded yet" | D-130 + the `AGENTS.md` ATOMICITY block; `docs/COMPACT-SUMMARY-2026-09-03.md` records n8n flows as Temporal Activities live at commit `d0b18f5`. |
| OW-123 | n8n classification pipeline "one step from first run" | `HANDOFF-2026-08-24-n8n-pipeline-golive.md` | Same D-130 / `d0b18f5` evidence, plus `docs/reviews/2026-09-02-n8n-uiw-binding.md` (historical filename; lane renamed `proffer`). |
| OW-124 | agno version drift (pin 2.8.7 vs venv 2.8.6) | `OWNER-REVIEW-2026-08-18…` tail item 5 | `AGENTS.md` drift-fix byline 2026-08-12: "agno 2.8.0 → 2.8.7 per `requirements.txt:3`". |
| OW-125 | DECISION_LOG D-072–D-081 backfill | `CLAIMED_COMPLETE_LIKELY_LIES/D-072-D-080-backfill.md` presented as a proposal | Verified this pass: `D-071`…`D-082` each return exactly one `^\| D-nnn ` row in `docs/DECISION_LOG.md`. **The backfill was merged.** |
| OW-126 | `sql/0071` outbox spine applied | `2026-09-04-outbox-part1-build.md`: "NOT committed, NOT applied" | `2026-09-05-ingest-day-live-chain.md`: applied live `09:54:35Z→09:54:40Z`, ledger 0→2 rows, `cdc_lag()` returns 36 rows. |
| OW-127 | `sql/0072` bridge applied | `2026-09-05-h04-bridge-and-weaviate-feed-rewire.md`: "BUILT, NOT DEPLOYED" | Same consolidation doc, same transaction. Commit `cc182a9`. See OW-043. |
| OW-128 | Tool-gateway build/redeploy defects | `2026-09-05-tool-gateway-live-deploy.md`: "BLOCKED on three committed-repo defects" | `2026-09-05-ingest-day-live-chain.md`: commit `8ed3191` "Clears the 5 defects blocking build/redeploy"; gateway container running, `svc:tool-gateway` VIP live. |
| OW-129 | H-02 cross-language contract location | `handoffs-v2-validation-and-dispatch-plan.md` frames it as a pending ruling | Ruled and recorded: `modules/contracts/` is in the root `AGENTS.md` layout table. Only the first schema file is still pending, correctly. |
| OW-130 | H-02a compilation restore | dispatch table row | `9da8815` — plus a second sweep-damage wave fixed in Python (`registry`→`reference` at usage sites, 12 files incl. `server/tools/registry.py`); go build/vet/test green, pytest collection restored. |
| OW-131 | Test/report location split | `handoffs-v2-…` table row | Root `AGENTS.md`: durable pytest reports write to `tests/_reports/`; configured in `server/observability/pytest_reporter.py`; recorded in `docs/CONVENTIONS.md` and ADR-0054 (amended). |
| OW-132 | ovh-data → ovh-files cutover | 12 unchecked boxes in `docs/planning/ovh-data-to-ovh-files-cutover.md` | PG moved to ovh-files 2026-08-02; the current `AGENTS.md` stack line reflects the post-cutover topology. |
| OW-133 | v8.1-era MVP build checklists (~50 unchecked boxes across `BUILD_TODO.md`, `EXECUTION_PLAN.md`, `MIGRATION_PLAN_v8.md`, `TOOL_SOURCES_INVENTORY.md`, `VERIFIED_AGNO_API.md`) | unchecked boxes | Each file's own banner: "Phases 1–9 are DONE; stack live on the VPS… retained as build history." The boxes were simply never ticked in frozen historical docs. |
| OW-134 | `facade-collapse-plan.md` OQ-1…OQ-7 | 7 open questions | **SUPERSEDED** — D-028: "the facade STAYS; Batches B/C are MOOT"; the plan's premise was disproven from source. |
| OW-135 | `sbv-fork-plan.md` five open questions | 5 open questions | **SUPERSEDED** — D-131: SBV is a DONOR, not a fork; absorbed into `modules/engine/decode/`. |
| OW-136 | `graphiti-image-rebuild-plan.md:221` hostfix-sidecar test | open question | **MOOT** — Graphiti retired (D-070). |
| OW-137 | Vault/Case Bible product name | D-138 item 2 left it open | **RESOLVED** by D-141: `consignatio`. |
| OW-138 | GAP-008 (Graphiti-retirement closure work) | "NOT committed, NOT pushed, NOT deployed, NOT live-verified" | **SUPERSEDED** — Graphiti is fully retired (D-070/D-095); the closure work is moot. |
| OW-139 | SearXNG web search, Daytona sandbox, Postgres 16→18 for n8n, `svc:n8n` tailnet service, node-root serve removal | URGENT-TODO rows 20, 21(SearXNG half), 24, 29, 30 | All marked **RESOLVED 2026-08-24** in `docs/URGENT-TODO.md` with live verification detail. Listed here only so the resolved rows are not re-triaged. |

---

## Reconciliation

| Class | Count |
|---|---|
| P0 — act before moving | 4 |
| P1 — live build work | 20 |
| P2 — held activations / deploy backlog | 14 |
| P3 — documentation system's own work | 24 |
| P4 — infrastructure (pointer rows) | 17 |
| P5 — inherited open questions | 14 |
| P6 — from the `awaiting-verification/` pass | 8 (OW-142 is DONE-NOT-CLOSED, not counted as open) |
| **Total open rows** | **101** |
| Confirmed DONE-but-never-closed | **21** (OW-120…OW-139, plus OW-142) |
| Of the open rows, needing an **owner decision** | **28** |

Three rows were **corrected during this pass by reading the code rather than the document**:
OW-142 (the `apply_0036` role patch landed in a different form than proposed), OW-126/OW-127
(`sql/0071` and `sql/0072` are applied live despite their own build docs saying otherwise), and
OW-128 (the tool-gateway defects were cleared by `8ed3191`). Each was reported as open by an
audit pass that read only the document. That is the register's central lesson: **a document's
own STATUS line is a claim about the past, not a fact about the present.**

**Known incompleteness, declared rather than hidden:** OW-070 (251 unchecked boxes in
`docs/reviews/**` not individually triaged), OW-067 and OW-069 (the GAP and ISS registers
carry ~34 and ~47 numbered items whose individual dispositions were not hand-verified this
pass). Those three rows are the honest boundary of this register. They are *counted as open*,
not quietly dropped — which is exactly the failure mode this document exists to prevent.
