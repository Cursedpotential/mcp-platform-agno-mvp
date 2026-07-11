# BUILD PLAN — the one forward plan

> **Authoritative for:** what we build next, in order. Entry point: `docs/PROJECT_CANON.md` (§0 Document Contract).
> Supersedes `docs/planning/*` (EXECUTION_PLAN, BUILD_TODO, MIGRATION_PLAN_v8) for **forward** work — those are history.
> Last updated: 2026-06-13.
> _Byline: Claude Code · Opus 4.8 · 2026-06-13_

## Anchor: the owner's critical path

**Knowledge-gathering from old AI-chat transcripts comes FIRST** — ingest them, extract the
development plans/decisions/strategy already discussed, feed the knowledge engine so the Builder
agents can help continue the build (the **bootstrap loop**). Evidence/SMS forensics come *after*.
Everything below is phased so each phase ships something usable and every write is HITL-gated.

**Where we are:** P0 ✅, P1 (HITL) ✅ deployed+verified, P2 evidence spine 🟡 built locally (not
redeployed; 4 parsers are shallow placeholders). Inventory complete (`EVIDENCE_MERGE_MAP.md`).

---

## Phase A — Parser core swap (transcripts become real)

**Goal:** replace the 4 shallow `evidence/tools/` (now `server/tools/parsers/ai_chat/`) parsers with the vendored **chatminer** core so AI-chat exports parse correctly. (Vendoring appears to have landed since this phase was written — see `server/tools/parsers/ai_chat/` + `server/vendored/chatminer/` — not re-verified in this doc-sync pass.)
- Vendor `chatminer` (10 format parsers + sentence-transformers segmenter + artifact extractor) into `server/tools/parsers/ai_chat/` as **atomic, self-registering modules** (one per format) per `CONVENTIONS.md`.
- Write an adapter: `ParsedMessage`/`ParsedConversation` → `NormalizedRecord` (content/role/timestamp/source → fields; rest → `attrs`).
- Add **`RELATIONSHIP_HISTORY`** to the `TopicTag` enum; keep `TopicTag` a **separate segment-level metadata field** (not a knowledge domain). Decide: keep case-tuned segmenter keywords vs. config-load them (open Q from merge map §5).
- Delete the 4 placeholder parsers. Deploy to VPS; smoke-test parse of real exports.
- **Done when:** real ChatGPT/Claude/Gemini/Perplexity exports parse → `NormalizedRecord`s with segment tags, verified on the VPS.

## Phase B — Knowledge ingestion + bootstrap loop

**Goal:** parsed+segmented transcripts land in the domain-partitioned knowledge engine so agents can answer "what did we decide/plan."
- Route segments into the four domains (`platform_design` / `legal_strategy` / `timeline_relationship` / `personal_history`) by segment-level tags, `MIXED`/`UNKNOWN` catch-alls; domains stay separate (CANON §3).
- Ingest the platform-design + legal-strategy conversation history first (fuels the bootstrap loop).
- **Done when:** a Builder agent answers a grounded question about a past design decision, citing the source transcript.

## Phase C — Gateway proof (Agno-first)

**Goal:** establish how far Agno's native tool-serving/proxying reaches before deciding on IBM ContextForge.
- Prove Agno can **serve** spine tools and **consume** an external MCP server. Register the first dial-stack capabilities as **MCP services behind Agno** — start highest-value: the **document-intelligence engine layer** (Google DocAI / IBM watsonx / Tesseract / Docling …) and the **bi-temporal Graphiti KG**.
- **Decision gate:** Agno covers the gateway role → done; if not → stand up **IBM ContextForge** (`IBM/mcp-context-forge`) as the tool gateway. (Tool gateway ≠ LiteLLM model gateway.)
- **Done when:** a tool served by the platform is invocable from at least one external surface, and the gateway decision is recorded as an ADR.

## Phase D — Bitemporal substrate (P3) + two-pass machinery

**Goal:** the cognition substrate that makes Part 2 possible.
- Wire `occurred_at` / `knowledge_time` / `disclosure_tier` through `store.py` + Graphiti; stand up the decision/provenance layer (Semantica).
- Rebuild the **two-pass shape on Agno** (donor reference: dial-stack `multi-pass-classifier` = Pass 1; `forensic-workflow` = preliminary→meta→reconciliation w/ HITL) — drop the LangGraph runtime.
- **Done when:** the Pass-1-vs-final-pass delta is queryable for a sample event over the bitemporal graph.

## Phase E — Evidence verticals + custody hardening + tests

**Goal:** Part 1 forensic completeness.
- Wrap dial-stack forensic parsers (SMS/FB/iMessage) + **SQLite WAL deleted-message recovery** as MCP services; SBV as Workflow A (custody-gated vertical + iframe + CLI + export).
- Harden custody toward dial-stack's **Ed25519 signed chain-of-custody**; `custody.py` stays the only `evidence`-schema writer.
- Harness-first tests (pytest + evals) per layer; R2 backups.
- **Done when:** an SMS/FB export ingests through custody → normalize → store with verifiable signed custody chain, evals green.

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
