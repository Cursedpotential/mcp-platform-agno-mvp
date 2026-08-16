# Horizon Platform (mcp-platform-agno-mvp) — Structured Audit

> _Byline: Owner-provided audit · captured by Codex · GPT-5 · 2026-08-16_
>
> **Status note:** This is the accepted baseline at commit `229baff`, not a statement of current
> implementation state. Later source, dated R-series handoffs, ADRs, and `docs/DEBT.md` govern
> subsequent verification and resolution status.

**Repository:** [Cursedpotential/mcp-platform-agno-mvp](https://github.com/Cursedpotential/mcp-platform-agno-mvp) · reviewed at commit `229baff` (main)
**Baseline for comparison:** the current R0–R12 handoff set indexed in [docs/HANDOFFS.md](https://github.com/Cursedpotential/mcp-platform-agno-mvp/blob/main/docs/HANDOFFS.md)
**Method:** direct inspection of the cloned repository (`pyproject.toml`, `requirements.txt`, `server/`, `sql/`, `docs/adr/`, `docs/DEBT.md`, the R0–R12 handoffs, Workbench, SBV compose, Chonkie seam) plus framework-documentation verification via Context7 for Agno (AgentOS/MCP) and SurrealDB.
**Addendum:** 2026-08-16 Swift-MVP pass — SBV ingest, Semantica VIP, Chonkie lockfile, Agno-to-framework-neutral / Vercel AI SDK.

---

## 1. Gaps & Blockers

| Sev | Finding | Location | Evidence | Recommendation |
|---|---|---|---|---|
| High | Migrations are not a from-zero build. A fresh-schema restore (`sql/0001`–`0025` from empty) fails at `0008` (`relation "evidence.source" does not exist`) — no migration creates it, and `docker/postgres/` has no init SQL. The base schema is bootstrapped outside tracked migrations. This blocks the automated restore-drill gate and is a real disaster-recovery risk. | `sql/`, `docker/postgres/` | [DEBT.md — "NEW DEBT — migrations are NOT a from-zero build"](https://github.com/Cursedpotential/mcp-platform-agno-mvp/blob/main/docs/DEBT.md) | Capture the live bootstrap DDL (or a dump of the live base schema) into the repo so `sql/` + bootstrap is a complete, reproducible restore. Not yet reported as fixed in any R0–R12 packet. |
| High | Horizon-clock predicate is inert. `working.horizon_visible` filters on superseded `row_knowledge_time` instead of ADR-0045's `visible_from = COALESCE(realized_at, occurred_at)` — live-confirmed against the running DB, so the filter currently does nothing. | `working.horizon_visible` (SQL) | [DEBT.md — Wave 0 live inventory finding 1](https://github.com/Cursedpotential/mcp-platform-agno-mvp/blob/main/docs/DEBT.md); [R0](https://github.com/Cursedpotential/mcp-platform-agno-mvp/blob/main/docs/HANDOFF-2026-08-15-R0-wave1-audit.md), [R2](https://github.com/Cursedpotential/mcp-platform-agno-mvp/blob/main/docs/HANDOFF-2026-08-15-R2-horizon-engine.md) | Land the Wave 1 clock migration (`realization_event` → `visible_from` derivation) already scoped in R2; treat as blocking for any feature that depends on horizon visibility being real. |
| High | Semantica is a VIP with no runtime. ADR-0043 / R3 require integrating Semantica fully and never forking around it, but `server/analysis/semantica_wiring.py` still only emits configuration dictionaries. There is no production worker, normalized-input adapter, candidate-submission path, or observed write. | `server/analysis/semantica_wiring.py` | [R3 — Semantica VIP](https://github.com/Cursedpotential/mcp-platform-agno-mvp/blob/main/docs/HANDOFF-2026-08-15-R3-semantica.md); [ADR-0043](https://github.com/Cursedpotential/mcp-platform-agno-mvp/blob/main/docs/adr/0043-semantica-governed-extraction-worker.md) | For a Swift MVP, freeze the ExtractionPort + candidate/provenance contract and stand up an isolated worker that submits findings for promotion. Do not give Semantica custody authority, and do not revive the S8 direct-Neo4j worker (it conflicts with ADR-0043). |
| High | Knowledge ingest still goes through an Agno-owned insert path. `scripts/ingest_knowledge.py` hands paths to Agno's native `knowledge.ainsert()`. That is the opposite of the accepted framework-neutral cutover. | `scripts/ingest_knowledge.py` | Direct file read; [PLAN-2026-08-15-platform-runtime-migration.md](https://github.com/Cursedpotential/mcp-platform-agno-mvp/blob/main/docs/PLAN-2026-08-15-platform-runtime-migration.md) | Build a framework-neutral ingest port that SBV/Go, folder-walk, and Workbench `/intake` all call. Agno may remain a consumer during shadow cutover; it must not own the public ingest contract. |
| Medium | Eval harness is still a skeleton. `evals/cases.py` retains `CASES: tuple[Case, ...] = ()` — the `agno.eval` framework is adopted in principle but has zero actual cases. | `evals/cases.py` | Direct file read; [DEBT.md](https://github.com/Cursedpotential/mcp-platform-agno-mvp/blob/main/docs/DEBT.md) | Out of Swift-MVP scope unless an ingest/chunking/horizon canary is needed. Do not expand the Agno-native eval harness as a substitute for framework-neutral contract tests. |
| Medium | No recurring backup lane. Only a one-time host-retirement snapshot script exists (`scripts/backup_ovhdata_hot.sh`). | `scripts/backup_ovhdata_hot.sh` | [DEBT.md — "Backups" row](https://github.com/Cursedpotential/mcp-platform-agno-mvp/blob/main/docs/DEBT.md) | Out of Swift-MVP scope. Do not block ingest/Workbench on this. |
| Medium | R9's Workbench auth key is not provisioned. Code enforces a mandatory fail-closed `WORKBENCH_API_KEY` (only `/health` is public), but the key is not provisioned or deployed. | Workbench API | [R9 — Knowledge to Case MVP](https://github.com/Cursedpotential/mcp-platform-agno-mvp/blob/main/docs/HANDOFF-2026-08-15-R9-knowledge-to-case-mvp.md) | Provision a local/dev key so `/intake` and `/knowledge` can actually be used. Do not lift live Coolify/Weaviate/Graphiti holds without owner approval. |
| Medium | Go ingestion concurrency still single-threaded in practice. `RunImportSequential` uses a global mutex. Marked "UNRESOLVED (mandatory)" in R1. | `vendored/sbv` | [R1](https://github.com/Cursedpotential/mcp-platform-agno-mvp/blob/main/docs/HANDOFF-2026-08-15-R1-go-ingestion.md) | Sequential SBV is acceptable for Swift MVP. Do not block ingest on parallelization. Do require per-import identity and `SBV_SERVICE_PASS` to be wired. |
| Medium | Workbench has no Vercel AI SDK yet. `workbench/web/package.json` has no `ai` / `@ai-sdk/*` dependency, even though the architecture blueprint assigns TypeScript/Next.js/AI SDK the experience plane. | `workbench/web/package.json` | [ARCHITECTURE-BLUEPRINT-2026-08-15.md](https://github.com/Cursedpotential/mcp-platform-agno-mvp/blob/main/docs/ARCHITECTURE-BLUEPRINT-2026-08-15.md) | Add the Vercel AI SDK to the self-hosted Next.js Workbench. Do not claim to self-host Vercel Functions or Vercel Sandbox. Keep the frontend unaware of Agno vs AG2. |
| Medium | Chonkie is decided and verified, but not in the prod lockfile. D-046 still has step (4) open: add torch-free extras to `requirements.txt`. Default ingest still uses Agno `RecursiveChunking` (`tuned=False`). | `pyproject.toml` optional extra `chunking`; `server/analysis/chunking_policy.py` | [D-046](https://github.com/Cursedpotential/mcp-platform-agno-mvp/blob/main/docs/DECISION_LOG.md) | Pin `chonkie[semantic,code,table]==1.7.0` in prod requirements and flip the knowledge/transcript ingest seam to the existing wrappers. Keep Neural/Late/Slumber remote-only. |

## 2. Inconsistencies

| Sev | Finding | Location | Evidence | Recommendation |
|---|---|---|---|---|
| Low | Version-citation drift. `AGENTS.md`, `CONVENTIONS.md`, and canon §8 still cite `agno==2.8.0` as current, while `requirements.txt` actually pins `agno==2.8.7`. | `AGENTS.md`, `requirements.txt` | [DEBT.md — "Agno-native audit" note](https://github.com/Cursedpotential/mcp-platform-agno-mvp/blob/main/docs/DEBT.md) | Quick docs-sync fix; low risk but easy to close in the next doc pass. |
| Low | Stale code comment on a resolved issue. `server/api/main.py:409` still reads `# ... mounted /mcp 500s, see that file`, pointing at `server/api/mcp_main.py` — but that file's own docstring says the mount issue was fixed natively in agno 2.8.0. Verified against [Agno AgentOS/MCP docs](https://docs.agno.com/agent-os/mcp/mcp) via Context7. | `server/api/main.py:409`, `server/api/mcp_main.py` | Direct file read | Update the comment so a future engineer doesn't reintroduce the retired standalone-MCP workaround. |
| Medium | ADR-0044's evidence blob-ban is unenforced in code. The whole-file fallback parser (`transcripts.markdown`) registers under `parse.transcript`, making it reachable from evidence-lane workflows. | `server/tools/parsers/generic/whole_file_fallback.py:25`, `server/evidence/workflows.py:533` | [DEBT.md — Parser-lane follow-ups, item 0](https://github.com/Cursedpotential/mcp-platform-agno-mvp/blob/main/docs/DEBT.md) | Apply one of DEBT.md's two proposed fixes and add the regression test it specifies before any evidence-lane ingest is declared usable. |
| Medium | S8 Semantica docs drift vs ADR-0043. R3 states the later S8 handoff's direct-Neo4j worker conflicts with ADR-0043 and must be corrected before implementation. | R3 vs S8 | [R3 UNRESOLVED](https://github.com/Cursedpotential/mcp-platform-agno-mvp/blob/main/docs/HANDOFF-2026-08-15-R3-semantica.md) | Treat ADR-0043 as authoritative. Correct S8 docs before writing any Semantica worker. |
| Medium | Parked Surreal vs new Surreal. `compose.data-surreal.yaml` is explicitly PARKED / do-not-deploy (ADR-0043 d3). R10–R12 authorize a *new disposable* Surreal analytical projection, not reactivation of the parked Agno operational store. | `compose.data-surreal.yaml`; R10–R12 | File header; [GOALS-2026-08-15-surreal-investigation-memory.md](https://github.com/Cursedpotential/mcp-platform-agno-mvp/blob/main/docs/GOALS-2026-08-15-surreal-investigation-memory.md) non-goals | Never point the MVP at the parked instance. A minimal Surreal surface must be a new isolated disposable target with owner-gated creation. |
| Info | Prior third-party review contained a materially wrong finding. A previous external review claimed a "disclosure_tier hardcode" bug; the project formally refuted it against ADR-0045. | — | [DEBT.md — "Report re-verification corrections"](https://github.com/Cursedpotential/mcp-platform-agno-mvp/blob/main/docs/DEBT.md) | Verify this report's findings against source before acting. |

## 3. Misconfigurations & Poor Implementations

| Sev | Finding | Location | Evidence | Recommendation |
|---|---|---|---|---|
| Medium | SMS-XML parser bypasses its own streaming design. `parse()` has a working `iter_records()` generator but accumulates every record in memory. The malformed-XML fallback loads the whole file plus a full DOM. | `server/tools/parsers/messaging/sms_xml.py` | [DEBT.md — Parser-lane follow-ups, item 0b](https://github.com/Cursedpotential/mcp-platform-agno-mvp/blob/main/docs/DEBT.md) | Wire `parse()` through `iter_records()` and spill to NDJSON. Sequential SBV remains the primary path; this is the fallback and is still load-bearing for malformed dumps. |
| Medium | SBV is primary again but dead without a password. Demotion was lifted by PR #18 / D-040. `_sbv_enabled()` gates solely on `SBV_SERVICE_PASS`. Compose defaults that password to empty, so coverage-based routing silently falls back to the Python SMS-XML parser. | `server/tools/parsers/messaging/sbv_sms.py`; `compose.yaml`; `docker/tools/Dockerfile` (`ghcr.io/cursedpotential/sbv-forensic:0.2.4-forensic`) | Direct file read; compose comments | For MVP, provision `SBV_SERVICE_PASS` in the local/dev exec env and prove one SMS/XML or chat export round-trip through the Go importer, not the Python fallback. |
| Low | Embedding calls bypass the model gateway. NVIDIA NIM `nv-embed-v1` calls NIM directly rather than Portkey. Explicit owner decision 2026-08-01. | `server/core/session.py` | [DEBT.md](https://github.com/Cursedpotential/mcp-platform-agno-mvp/blob/main/docs/DEBT.md) | Out of Swift-MVP scope. |
| Low | Auth intentionally disabled platform-wide. `AgentOS(... authorization=False)`. | `server/api/main.py` | Direct file read | Keep Workbench fail-closed on `WORKBENCH_API_KEY`. Do not expose AgentOS as the operator UI. |
| Low | Custody-event digest lacks version stamping. | Custody-digest trigger | [DEBT.md — court-readiness debt](https://github.com/Cursedpotential/mcp-platform-agno-mvp/blob/main/docs/DEBT.md) | Out of Swift-MVP scope. Do not rewrite historical rows. |

## 4. Opportunities

| Finding | Detail | Recommendation |
|---|---|---|
| Thin vertical slice is now possible | Workbench already has `/intake`, `/knowledge`, `/matter`, `/evidence-queue`. Matter/CourtCase APIs exist on `main` (undeployed). SBV image and facade exist. Chonkie wrappers exist. Surreal Phase-0 contracts pass. | Do not rebuild these. Wire them into one local ingest → view → query loop. |
| Under-used native Agno features | `output_schema`, `tool_hooks`, native Knowledge readers. | Do **not** deepen Agno coupling. Prefer framework-neutral ports + Vercel AI SDK on Workbench. |
| Test suite trending well | 688 → 750 → 768 passed; 24 skips flat. | Keep the 18 framework-neutral Surreal contract tests as the MVP's source of truth, not Agno evals. |
| Formalize audit-refutation | DEBT.md already refutes bad external findings with file/line citations. | Apply the same scrutiny to this report before acting. |
| Six R11 owner decisions closed cleanly | R12 accepted S1–S6 same day. | Reuse that pattern: bundle remaining MVP owner gates (local key, disposable Surreal target, Semantica image pin) into one ruling packet. |

---

## Progress / Regression vs. the R0–R12 Baseline

**Resolved**
- Unit test suite grew from 688 passed (R0) → 750 (R9) → 768 passed / 24 skipped (R12).
- R0 format-gate failure is reported passing in R12.
- R9 Matter/CourtCase + evidence-promotion foundation is on `main` (ADR-0055/D-060), still undeployed pending migration `0030`.
- R11 S1–S6 owner rulings accepted in R12; 18/18 framework-neutral contract tests pass.

**Regressed**
- None identified in the R0–R12 window.

**Persistent**
- Live adapter / deployment proof for Surreal remains UNKNOWN through R10, R11, and R12.
- R9 activation holds remain in force (migration `0030`, Workbench key, no live Weaviate/Graphiti/Coolify mutation).
- From-zero migration/restore gap (`sql/0008`) is unfixed.
- R1 Go-ingestion global mutex is unfixed.
- Semantica remains config-only.
- Chonkie remains an optional extra, not a prod dependency.
- Knowledge ingest remains Agno-central (`ainsert`).

**New (Swift-MVP addendum)**
- Confirmed SBV is PRIMARY again (D-040) but silently disabled when `SBV_SERVICE_PASS` is empty.
- Confirmed Workbench has no Vercel AI SDK package.
- Confirmed parked Surreal compose must not be the MVP target.
- Confirmed D-046 Chonkie install+verify is done; lockfile + ingest-seam flip is not.

---

## Swift MVP implication

The platform is over-documented and under-looped. A usable Swift MVP is **not** Waves 0–10 and **not** Agno retirement. It is one local, fail-closed loop:

1. Ingest a file (Workbench `/intake` or folder-walk) through a **framework-neutral ingest port**.
2. Parse via **SBV/Go when coverage matches**; Python fallback only when SBV cannot.
3. Chunk via **Chonkie** (torch-free local wrappers already written).
4. Persist canonical rows in **PostgreSQL**; project rebuildable retrieval to Weaviate only if already available locally.
5. View the result in Workbench `/knowledge` (and Matter-scoped `/matter` if `0030` is applied locally).
6. Optionally project an approved slice into a **new disposable Surreal** surface behind `HorizonContextPort` — never the parked Agno operational store.
7. Chat/stream in Workbench through the **Vercel AI SDK** against framework-neutral routes, not AgentOS Studio.

Highest-priority actions for that loop, in order: provision local Workbench + SBV credentials; land the framework-neutral ingest port; put Chonkie in the prod lockfile and turn it on; stand up Semantica as a governed candidate worker (no custody writes); add a disposable Surreal retrieve pane only after owner approval of an isolated target.

---

## Executive Summary

- **Overall health is solid.** Debt register, source-cited refutations, and +80 passing tests with zero identified regressions.
- **The product is not yet usable end-to-end.** Ingest is Agno-owned, SBV is password-gated off by default, Semantica has no worker, Chonkie is not in the image, Workbench has no AI SDK, and Surreal has no live adapter.
- **Highest-priority DR action remains** the from-zero migration/restore gap (`sql/0008`). That does not block a *local* Swift MVP if you build against the live schema, but it does block any claim of reproducible restore.
- **Highest-priority product action:** close the ingest → Workbench view loop on a framework-neutral port, with SBV actually enabled and Chonkie actually installed.
- **Treat Surreal as design-complete, not production-ready.** Minimal surface only, new isolated instance, owner-gated.
