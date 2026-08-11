# BUILD PLAN — the one forward plan

> **Authoritative for:** what we build next, in order. Entry point: `docs/PROJECT_CANON.md` (§0 Document Contract).
> Supersedes `docs/planning/*` (EXECUTION_PLAN, BUILD_TODO, MIGRATION_PLAN_v8) for **forward** work — those are history.
> Last updated: 2026-06-13 (phase statuses refreshed 2026-07-11).
> _Byline: Claude Code · Opus 4.8 · 2026-06-13 (phase-status refresh 2026-07-11 Claude Code · Sonnet 5)_

## Anchor: the owner's critical path

**Knowledge-gathering from old AI-chat transcripts comes FIRST** — ingest them, extract the
development plans/decisions/strategy already discussed, feed the knowledge engine so the Builder
agents can help continue the build (the **bootstrap loop**). Evidence/SMS forensics come *after*.
Everything below is phased so each phase ships something usable and every write is HITL-gated.

**Where we are (updated 2026-07-11):** P0 ✅, P1 (HITL) ✅ deployed+verified, P2 evidence spine 🟡 —
**Phase A parser core-swap below is DONE** (chatminer vendored + 11 real modules in
`server/tools/parsers/ai_chat/`, verified 2026-07-11; the "4 shallow placeholders" framing is
obsolete). Still open: schema population by a real ingest pipeline remains `planned` (`DEBT.md`) —
live evidence schema is near-empty (`evidence_hash`=26 rows, verified 2026-07-11); the RESTART-0001
per-source raw-table redesign is DRAFT awaiting owner sign-off (D-008, `docs/DECISION_LOG.md`).
Inventory complete (`EVIDENCE_MERGE_MAP.md`).

---

## Phase A — Parser core swap (transcripts become real) — ✅ DONE (verified 2026-07-11)

**Goal:** replace the 4 shallow `evidence/tools/` (now `server/tools/parsers/ai_chat/`) parsers with the vendored **chatminer** core so AI-chat exports parse correctly.
- Vendor `chatminer` (10 format parsers + sentence-transformers segmenter + artifact extractor) into `server/tools/parsers/ai_chat/` as **atomic, self-registering modules** (one per format) per `CONVENTIONS.md`. — **done**: `server/vendored/chatminer/` present; 11 modules in `server/tools/parsers/ai_chat/` (9 chatminer-backed via `server/tools/_chatminer_adapter.py`; 2 genuinely custom formats — claude.ai export JSON, Claude Code JSONL — chatminer has no equivalent for those).
- Write an adapter: `ParsedMessage`/`ParsedConversation` → `NormalizedRecord` (content/role/timestamp/source → fields; rest → `attrs`). — **done**: `server/tools/_chatminer_adapter.py` (`run_chatminer_parser`), covered by `tests/test_chatminer_adapter.py`.
- Add **`RELATIONSHIP_HISTORY`** to the `TopicTag` enum; keep `TopicTag` a **separate segment-level metadata field** (not a knowledge domain). Decide: keep case-tuned segmenter keywords vs. config-load them (open Q from merge map §5). — enum addition **done** (`server/vendored/chatminer/core/types.py`); the case-tuned-vs-config-load decision is status unverified as of 2026-07-11 (not re-checked this pass).
- Delete the 4 placeholder parsers. Deploy to VPS; smoke-test parse of real exports. — placeholder deletion **done** (no placeholder files remain in `server/tools/parsers/ai_chat/`); VPS redeploy/smoke-test of real exports is status unverified as of 2026-07-11 (local module presence + `uv run pytest` coverage confirmed only, not a live VPS parse run).
- **Done when:** real ChatGPT/Claude/Gemini/Perplexity exports parse → `NormalizedRecord`s with segment tags, verified on the VPS. — code-level goal met; VPS verification status unverified as of 2026-07-11.

## Phase B — Knowledge ingestion + bootstrap loop

**Goal:** parsed+segmented transcripts land in the domain-partitioned knowledge engine so agents can answer "what did we decide/plan."
- Route segments into ~~the four domains (`platform_design` / `legal_strategy` / `timeline_relationship` / `personal_history`)~~ **the SIX lanes (`platform` · `legal` · `personal_history` · `relationship_timeline` · `context` · `evidence`) — superseded 2026-08-10 by ADR-0050** by segment-level tags, `MIXED`/`UNKNOWN` catch-alls; lanes stay structurally separate (one Weaviate collection each, ADR-0050 §1; CANON §3). Migration map: `platform_design`→`platform`, `legal_strategy`→`legal`, `timeline_relationship`→`relationship_timeline`, `personal_history`→`personal_history`. One conversation routes into MULTIPLE lanes at the segment level (ADR-0051 invariant 5). — _corrected Claude Code · Opus 4.8 · 2026-08-10_
- Ingest the platform-design + legal-strategy conversation history first (fuels the bootstrap loop).
- **Done when:** a Builder agent answers a grounded question about a past design decision, citing the source transcript.

## Phase C — Gateway proof (Agno-first) — 🟡 gateway decision DONE, dial-stack wrap open

**Goal:** establish how far Agno's native tool-serving/proxying reaches before deciding on IBM ContextForge.
- Prove Agno can **serve** spine tools and **consume** an external MCP server. Register the first dial-stack capabilities as **MCP services behind Agno** — start highest-value: the **document-intelligence engine layer** (Google DocAI / IBM watsonx / Tesseract / Docling …) and the **bi-temporal Graphiti KG**. — status unverified as of 2026-07-11 (dial-stack wrap-order item not re-checked this pass; see open decision #2 below).
- **Decision gate:** Agno covers the gateway role → done; if not → stand up **IBM ContextForge** (`IBM/mcp-context-forge`) as the tool gateway. (Tool gateway ≠ LiteLLM model gateway.) — **decided and done**: verified from agno source (`agno/os/app.py:588-595`) that AgentOS's native MCP surface exposes only ~19 AgentOS *operations*, never granular `@tool` functions — so the **facade stays** as the only granular-tool MCP surface (`docs/planning/facade-collapse-plan.md`, superseded-banner corrected 2026-07-10) and **IBM ContextForge is the tool gateway** (ADR-0025, D-006 `docs/DECISION_LOG.md`; CF v1.0.4 live). All 14 facade tools are registered directly in ContextForge as REST tools in virtual server `platform_tools` (2026-07-10), alongside `agno`/`coolify`/`graphiti`/`exa`.
- **Done when:** a tool served by the platform is invocable from at least one external surface, and the gateway decision is recorded as an ADR. — **met**: `platform_tools` virtual server (2026-07-10); gateway decision recorded in ADR-0025.

## Phase D — Bitemporal substrate (P3) + two-pass machinery

**Goal:** the cognition substrate that makes Part 2 possible.
- Wire `occurred_at` / `knowledge_time` / `disclosure_tier` through `store.py` + Graphiti; stand up the decision/provenance layer (Semantica).
- Rebuild the **two-pass shape on Agno** (donor reference: dial-stack `multi-pass-classifier` = Pass 1; `forensic-workflow` = preliminary→meta→reconciliation w/ HITL) — drop the LangGraph runtime.
- **Done when:** the Pass-1-vs-final-pass delta is queryable for a sample event over the bitemporal graph.

## Phase E — Evidence verticals + custody hardening + tests

**Goal:** Part 1 forensic completeness.
- Wrap dial-stack forensic parsers (SMS/FB/iMessage) + **SQLite WAL deleted-message recovery** as MCP services; SBV as Workflow A (custody-gated vertical + iframe + CLI + export). — SBV side 🟡 **largely landed** (verified 2026-07-11): forensic fork LIVE in prod with H1/H2/H3 custody hashing (`ghcr.io/cursedpotential/sbv-forensic:0.2.3-forensic`, deployed 2026-07-09); Phase 5a native Go automation endpoints (`/api/automation/extract`+`status`/`export`/`backups`) are BUILT on fork branch `worktree-agent-abe280ccbefefe136` but not yet shipped through the subtree→fork→CI→tag-bump sequence (`docs/COORDINATION.md`); Phase 5b `/x/sbv/` UI embed DEFERRED to the G2/VPS window. dial-stack SMS/FB/iMessage parser wrap status unverified as of 2026-07-11.
- Harden custody toward dial-stack's **Ed25519 signed chain-of-custody**; `custody.py` stays the only `evidence`-schema writer. — status unverified as of 2026-07-11.
- Harness-first tests (pytest + evals) per layer; R2 backups. — pytest suite green (208, `uv run pytest -q`, verified 2026-07-11); evals still `CASES=()` per `DEBT.md`; R2 backups status unverified.
- **Done when:** an SMS/FB export ingests through custody → normalize → store with verifiable signed custody chain, evals green. — not yet met: evals remain empty (`DEBT.md`).

---

## Later (own rounds)

- **Part 2 — Analysis:** behavioral/legal layer — vendor/wrap **Tether** (HF models, deferred at `dial-stack/utilities/apps/ml-nlp/Tether/`), `pattern-analyzer` (~25 modules→MCL), `ConflictAnalysisApp` RuleEngine, `priority-screener`; multi-pass over knowledge horizons.
- **Part 3 — AI Legal Team:** port the owner's Gemini Gems personas to Agno; MCL 722.23 ontology + Michigan legal skills.
- **Hardening:** self-hosted evidence vector store at scale; multi-user auth; living wiki (ADR-0022).

## Delegation map — who/what does each kind of work

The SSOT is tool-agnostic (`CONVENTIONS.md` § cross-tool), so work can be split across agents/models by
*judgment required* vs *volume*. Every delegated artifact carries a byline (`tool · model · date`).

| Work type | Best executor | Why |
|---|---|---|
| **Bulk scanning / reading / summarizing into the inventory** (unread plugin bodies, 9 doc-intel engine bodies, loaders/pipelines, drizzle schemas) | **Cheaper model** (Sonnet/Haiku) or OpenCode/Codex agent, read-only | High volume, low judgment; just extract + record |
| **ADR supersession sweep + planning/* reconciliation** (flag conflicts vs the new SSOT) | **Cheaper model**, read-only, *proposes* — human/Opus confirms | Mechanical cross-check; decisions stay with owner/canon |
| **Mechanical porting** (vendor a chatminer parser into `server/tools/parsers/ai_chat/` to the atomic-tool contract) | OpenCode/Codex agent or cheaper model, per `CONVENTIONS.md` | Pattern is fixed; contract is explicit |
| **Wrapping a donor TS tool as an MCP service** | OpenCode/Codex (strong at codegen) | Self-contained, testable |
| **Architecture/decisions, conflict reconciliation, plan changes, anything touching CANON §5** | **This tier (Opus/Fable)** — NOT delegated | Judgment + cross-cutting consistency; the debacle came from un-reconciled decisions |
| **Anything that writes evidence/HITL/custody** | reviewed here, HITL-gated | Trust boundary |

### Recommended: cheaper-agent PRE-SCAN before Phase A (my recommendation: do it)

Before building, dispatch a **cheaper read-only agent** to close the last mechanical gaps so Phase A starts on solid ground. Scoped task (it writes findings into the inventory + a reconciliation note, makes NO code/decisions):
1. Read the ~40 `plugins/*.ts` bodies + 9 `document_intelligence/engines/*.py` bodies + `loaders/`/`pipelines/` + remaining `drizzle/*` → append concise capability notes to `EVIDENCE_MERGE_MAP.md` §7.
2. ADR sweep: list which of ADR-0001…0022 are superseded/affected by the 2026-06-13 locked decisions (gateway/Agno-not-DIAL, donor reconciliation) → write `docs/ADR_RECONCILIATION.md` (proposals only).
3. Flag any contradiction between `docs/planning/*` and the new SSOT.
Output is reviewed here before Phase A. **This is the cheap, safe way to de-risk; judgment work stays at this tier.**

## Open decisions to confirm before/within phases (from EVIDENCE_MERGE_MAP §5)

1. Segmenter keywords: keep case-tuned vs generalize + config-load case terms? (Phase A)
2. dial-stack wrap order — confirm document-intelligence + Graphiti first. (Phase C)
3. Custody hardening timing — now vs Phase E. (default: Phase E)
4. How far Agno native tool-serving reaches before ContextForge. (Phase C gate)
