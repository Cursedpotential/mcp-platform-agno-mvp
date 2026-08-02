# Agno Cookbook Adoption Backlog

> _Byline: Claude Code · Fable 5 · 2026-08-02 — distilled from three read-only
> cookbook walks (91_tools; 07_knowledge + 04_workflows; 05_agent_os +
> 08_learning pending) cross-checked against the v2.8.0 tag. Everything below
> is version-safe at our pin unless marked._

## ADOPT NOW (highest value, verified at 2.8.0)

| # | Adoption | Replaces / fixes | Ours to change | Cookbook ref |
|---|---|---|---|---|
| 1 | `Workflow(db=...)` native run persistence (`get_run`, `cancel_run`, background) | The 360-line custom run ledger (`server/evidence/run_ledger.py`) + `_wrap_step_for_ledger` | `server/evidence/workflows.py` builders | 04_workflows/06_advanced_concepts/run_control, background_execution |
| 2 | Native workflow HITL: `HumanReview(timeout=, on_timeout=)`, `requires_confirmation`, `OnError.pause` + `.retry()/.skip()` | Hand-rolled `asyncio.sleep(2)` gate-poll loop with 24h ceiling (`_wrap_step_for_run_control`) | `server/evidence/workflows.py` | 04_workflows/08_human_in_the_loop |
| 3 | Multiple named `Knowledge` instances sharing one vector_db (`linked_to`) + dict `knowledge_filters` | The single-KB-in-UI complaint; evidence/legal domains written but never filterable (DEBT.md:46, still open) | `server/api/main.py:253`, `server/core/knowledge_handle.py`, agent wiring | 07_knowledge/03_production/04_agent_os.py, 02_building_blocks/04_filtering.py |
| 4 | Reranker wiring — pass `reranker=NvidiaReranker(...)` into the vectordb ctor | `server/core/reranker.py` is dead code (built, never instantiated) | `server/core/session.py:317-323` (1 line, once NVIDIA rerank endpoint verified live) | 07_knowledge/02_building_blocks/03_reranking.py |
| 5 | `tool_hooks=[tool_call_ledger_hook]` agent-wide | `ops.tool_call_ledger` exists in SQL, zero references in server/ (unwired) | `server/agents/factory.py` | 91_tools/tool_hooks |
| 6 | `session_state` + pre-hook as the HORIZON ENFORCEMENT mechanism — hook checks/advances the `knowledge_time` cursor before every read tool call | Horizon currently relies on each tool remembering to filter | `server/agents/factory.py` + providers | 91_tools/tool_hooks/tool_hook_in_toolkit_with_state.py |

## ⚠ LANDMINE (recorded in AGENTS.md §WHY, 2026-08-02)

agno's Weaviate adapter **silently drops FilterExpr filters** (`filters = None` +
a warning) — dict filters only. Any horizon/disclosure_tier pre-filter MUST be a
dict, or it applies nothing in prod while passing tests on other vectordbs.
Verified in `.venv/.../agno/vectordb/weaviate/weaviate.py`, identical at v2.8.0.

## ADOPT LATER (queued, do not start without a reason)

- `@tool(cache_results=True)` on idempotent gateway reads · per-tool
  `instructions=` · Pydantic tool arg models (typed `execute_tool` payload)
- `RetryAgentRun`/`StopAgentRun` guided-retry — needs an ADR-sized decision so
  it doesn't erode the gateway's raise-don't-swallow contract
- `MultiMCPTools` + `allow_partial_failure` — at the Phase-7 multi-MCP point
- `knowledge_retriever=` custom retriever — strong fit for hard-coding the
  disclosure-tier boundary per agent; consider WITH adoption #3
- `input_schema` on workflows · `workflow_as_a_step` (custody→parse reuse) ·
  `step_history` · CEL conditions (needs optional `agno[cel]` extra — install
  gate, not version gate)
- `enable_agentic_knowledge_filters` — cautious: an agent choosing its own
  filter is the wrong shape for a non-negotiable horizon boundary
- `isolate_vector_search` per-tenant pattern as template for per-agent isolation

## Rejected / N-A

- FilterExpr on Weaviate (see landmine) · KnowledgeProtocol (Weaviate fits) ·
  `prefix_match` (PgVector-only) · `skip_if_exists` (custody sha256 dedupe
  already covers) · agno Toolkits replacing `server/tools/` registry
  (deliberate architecture, ADR-0035)

## Process note

The run-ledger and gate-poll replacements (#1, #2) are a rebuild-toward-intent —
load the `zero-tech-debt` skill when executing them, and keep `run_routes.py`'s
external API contract stable while swapping the internals.

## The deep-research shape (docs.agno.com/use-cases/deep-research, owner-flagged 2026-08-02)

Agno's deep-research pattern — `Step` → `Parallel(specialists)` → synthesis →
typed deliverable → committee decision — is structurally THE analysis-phase
pipeline for the knowledge-horizon mechanism:

| Deep-research stage | Our analysis phase |
|---|---|
| Parallel specialist investigations | `Parallel(ignorant-walk assessment, hindsight analysis)` — each agent horizon-bound by permissions |
| Synthesis step | The DELTA computation (what you were led to believe vs what was true vs when you found out) |
| Typed structured deliverable (`output_schema`) | `analysis.finding` rows — machine-checkable, citing spine records |
| Committee decision | `review_gatekeeper` HITL gate (existing `mode='supervised'` primitive) |
| Grounding library per specialist | Named `Knowledge` instances per domain (adoption #3) with dict horizon filters |
| Institutional learning (shared store/namespace) | `learned_knowledge` lane — once verified functional (currently PROPOSE, unverified) |
| Attach db to Workflow for per-run inspection | Adoption #1 (`Workflow(db=...)`) |

Verdict: **ADOPT as the analysis-workflow blueprint** when the walk engine gets
built — it composes entirely from adoptions #1-#3 plus `output_schema`, nothing
new to invent. Docs index for deeper pages: https://docs.agno.com/llms.txt
(agno-docs MCP server is wired for retrieval).

## 05_agent_os + 08_learning walk (landed 2026-08-02, all verified at 2.8.0)

**DONE same day:**
- ✅ LearningMachine db → PostgresDb (`main.py`): SurrealDb's learning methods
  all `raise NotImplementedError`, swallowed by LearningMachine's broad
  `except` — THE root cause of the silent-no-op prod bug. Fixed, not worked
  around.
- ✅ `available_models` populated (109 ids: ollama 18 + nvidia 91) via
  `scripts/update_available_models.py` → `config.yaml` — fixes "only one
  model available". Re-run the script after catalog changes.

**ADOPT NOW (small, queued):**
- `AgentOSTools(db=admin_db)` on an ops-facing agent (~5 lines,
  `server/agents/factory.py`) — self-observability that routes around the
  broken Studio traces pane (which is likely a Studio front-end bug: the
  `/traces` REST backend verified working in the cookbook; smoke-test ours).
- `DecisionLogConfig` — log motion-strategy/factor-analysis decisions with
  reasoning, `record_outcome` closes the loop later. Near-perfect
  legal-platform fit, present at 2.8.0.
- Smoke-test `GET /learnings` live — now meaningful post-Postgres-swap; proves
  the fix end-to-end.
- `max_updates_per_run` caps on learning stores (cheap runaway valve).

**ADOPT LATER (design decisions first):**
- `@approval(type="required"/"audit")` on destructive tools + `/approvals`
  REST. NOTE a verified nuance: `LearnedKnowledgeConfig(mode=PROPOSE)` is a
  PROMPT-INJECTED soft gate, not framework-enforced — a confused model can
  still call `save_learning`. Hard HITL on the built-in learning tools needs
  a thin custom `LearningStore` proxy (08_custom_stores pattern).
- Per-agent `namespace=` isolation — currently ALL 6 agents/3 teams share
  `namespace="platform"`; dev_copilot and forensic_data_agent read/write the
  same memory. Decide per-agent vs per-role first.
- `AuthorizationConfig(user_isolation=True)` — the moment this goes multi-user.
- `AgentFactory` + `RequestContext.trusted` tiered models — pairs with the
  model catalog for a real picker UX.
- Two conflicting walker claims on whether `@approval` is already used in
  `factory.py` — reconcile by reading before adopting.

## Golden-set eval (owner-flagged docs page, 2026-08-02)

`analysis.human_label_gold` (1,918 hand-labelled rows, FK-free) IS the golden
set for `AccuracyEval` over the detection pipeline: run detection → serialize →
`eval.run_with_output()` with `db=` to store scores → compare across
prompt/model changes. Per-field `ConfidentField` confidence + threshold
routing maps onto the 0016 candidate confidence + review gate (application
code owns the threshold). Approval-gated writes at the system boundary =
exactly the 0016 promotion CHECK, plus `@approval` at the tool boundary.

## Research pointers (owner-dropped, not yet walked)

- https://docs.agno.com/reference/cli/agnoctl#agno-connect — agnoctl CLI
- https://docs.agno.com/agent-os/multi-framework/claude-agent-sdk — Claude
  Agent SDK inside AgentOS; bears on the parked ClaudeAgent
  mount-and-compliance question (HANDOFF-2026-08-01 pending decisions)
- https://docs.agno.com/llms.txt — full docs index (agno-docs MCP wired)
