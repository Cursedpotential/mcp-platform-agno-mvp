# HANDOFF — Agno role dissection (what Agno still does, and what it should)

> _Byline: Claude · Opus 5 · 2026-08-29, from an owner directive._

STATUS: SCOPED — inventory complete, analysis not started. This is a dissection task, **not** a
removal task. Nothing in this packet authorizes deleting, replacing, or refactoring Agno.
BUILD_STATUS: N/A — no code change is in scope.

## Why this exists

Agno used to be the primary home of the knowledge bases, the sole writer of the tables, and the
viewing/work surface. **It is none of those things now.** Agents may still be used for specific
tasks inside n8n and Temporal.

The code never got the memo. Agno is still imported by **28 production files** and is still the
process host for the API. On 2026-08-29 the owner asked for a task that *"completely dissects what
Agno's role still is in the code, so that we can decide how best to address that — and if it needs
to be addressed at all."*

The last time a retirement ruling failed to propagate (Graphiti, 2026-08-27), the register still
said "implementation pending" two days later and blocked a lane that was already closed. This
packet exists so that does not repeat: **decide from an inventory, not from an assumption.**

## Owner rulings already made — treat as settled input, not open questions

| Ruling | Owner language (2026-08-29) |
|---|---|
| Agno must have **no role in the knowledge vector** | "Agno should definitely not have anything to do with the knowledge vector." |
| **Providers and model registry are not needed** | "We don't need the providers or the model registry because I'm not going to be doing chat through there." |
| Session and factory are **undecided, possibly load-bearing** | "Session might be important, factory might be important… maybe these things are necessary for the couple of agents that actually happen." |
| `server/api/main.py` is **unknown to the owner** — explain it before proposing anything | "I don't know what main dot pie does." |
| Agents survive **only inside n8n/Temporal** | "We might utilize some agents to do certain tasks within the confines of n8n and temporal." |

## Inventory — verified 2026-08-29 by import scan

28 production files plus 3 test files import Agno. Grouped by surface, not by folder.

### S1 · Process host and API surface — **the largest and least understood dependency**
- `server/api/main.py` — `agno.os.AgentOS`, `agno.registry.Registry`, `agno.team.team.Team`,
  `agno.workflow.factory.WorkflowFactory`, `agno.workflow.remote.RemoteWorkflow`,
  `agno.workflow.workflow.Workflow`, `agno.utils.log`
- `server/api/workflow_registry.py` — `WorkflowFactory`, `agno.utils.log`
- `server/api/mcp_main.py` — `agno.utils.log`

**This is the answer to "I don't know what main.py does": Agno is not a library here, it is the
application server.** `AgentOS` hosts the API. Any Agno decision is therefore a decision about how
the platform is served. Dissect this first — everything else is downstream of it.

### S2 · Knowledge / vector / embedding — **owner has ruled Agno out; confirm blast radius**
- `server/core/knowledge_vectordb.py` — `agno.vectordb.weaviate.Weaviate`, `agno.knowledge.document`
- `server/core/embedder.py` — `agno.knowledge.embedder.openai.OpenAIEmbedder`
- `server/core/reranker.py` — `agno.knowledge.reranker.base.Reranker`, `agno.knowledge.document`
  (**note: zero callers as of the 2026-08-29 audit — likely deletable outright**)
- `server/core/session.py` — `agno.knowledge.Knowledge`, `agno.vectordb.search.SearchType`

### S3 · Session and database handles — **undecided; highest coupling risk**
- `server/core/session.py` — `agno.db.postgres.PostgresDb`, `agno.db.surrealdb.SurrealDb`

Agno owns the Postgres **and** SurrealDB handles. Flag: this sits directly against ADR-0056/D-061,
where Surreal is a governed projection and PostgreSQL is the canonical authority. Determine whether
Agno's DB layer is in the write path for anything canonical. **If it is, that is a finding, not a
refactor ticket — report it.**

### S4 · Model providers and registry — **owner has ruled these out**
- `server/core/settings.py` — 8 model imports (`OpenAILike` ×3, `Ollama`, `OpenAIChat`, `Claude`,
  `Gemini`, `Groq`)
- `server/core/model_registry.py` — `agno.utils.log` only (trivial coupling)
- `server/agents/providers.py` — `agno.context.database.DatabaseContextProvider`,
  `agno.context.workspace.WorkspaceContextProvider`, `agno.learn`

Check against D-093: model-backed work is supposed to route through **Portkey**, never a direct
provider call. If `settings.py` still constructs providers directly, that is an existing violation
independent of any Agno decision.

### S5 · Agents and agent tooling — **survive only inside n8n/Temporal**
- `server/agents/factory.py` — `Agent`, `Team`, `TeamMode`, `approval`, `tool`,
  `FileGenerationTools`, `UserControlFlowTools`
- Agent modules: `analysis_orchestrator.py`, `dev_copilot.py`, `document_digest.py`,
  `forensic_data_agent.py`, `ingestion_orchestrator.py`, `project_pal.py`,
  `review_gatekeeper.py`, `transcript_miner.py`, `claude_code_agent.py`
- Agent tools: `tools/gateway_tools.py`, `tools/realization_tools.py`, `tools/sbv_tools.py`

**The central question for this surface:** which of these nine agents actually runs in production,
and which are dead? The owner expects "a couple." Nine exist. Establish the real number by call-site
and workflow-registration evidence, not by file presence.

### S6 · Workflow engine — **direct conflict with the durable-spine ruling**
- `server/evidence/workflows.py` — `agno.workflow.Step`, `Workflow`, `OnError`, `StepInput`,
  `StepOutput`

D-068 states **Temporal is the durable spine and n8n is the agent/integration layer.** Agno
workflows in the evidence path contradict that. Determine whether these execute in production or are
vestigial.

### S7 · Chunking — **partially superseded already**
- `server/analysis/chonkie_chunkers.py`, `server/analysis/chunking_policy.py` —
  `agno.knowledge.chunking.*`

The 2026-08-29 chunker bake-off concluded document-class markdown needs **no chunking library at
all** and belongs in Go beside the coordinator. Determine what still legitimately routes through
Agno chunking after that finding.

### S8 · Scripts and tests — lowest priority
- `scripts/check_model.py`, `scripts/verify_direct_providers.py`, `scripts/migrate_milvus_to_weaviate.py`
- `tests/test_agent_authority_boundary.py`, `tests/test_c26_resilience.py`, `tests/test_chonkie_chunkers.py`

## What the dissection must produce

One document. For **every** file above:

1. **Live or dead** — is it reachable from a running entry point? Cite the call path or state that
   none exists. File presence is not evidence of use.
2. **What Agno actually provides** — the specific capability, not the import name.
3. **Canonical write path?** — does it write anything the platform treats as authoritative? This is
   the question that decides whether an item is a cleanup or a governance finding.
4. **Replacement cost** — trivial (logging shim), bounded (one adapter), or structural (API host).
5. **Conflicts with a standing decision** — especially D-068 (Temporal spine), D-093 (Portkey
   routing), ADR-0056 (Surreal as projection).

Then a single ranked table: **remove now · replace later · keep deliberately · needs owner ruling.**

## Boundaries — read these before starting

- **Do not remove, replace, or refactor anything.** The output is analysis. The owner decides after
  reading it, including deciding to do nothing.
- **Do not delete files.** If something is provably dead, say so and cite the evidence; moving it to
  `to_be_deleted/` requires a separate owner go.
- **Do not start the Workbench/UIW lane's work**, and do not touch files in flight there.
- **`server/api/main.py` is explained first.** The owner has said plainly he does not know what it
  does; every other recommendation depends on that answer.
- Agno currently starts the API. **Any proposal that breaks startup is not a proposal, it is an
  outage.** State the startup impact of every suggested change.
- Record the ruling in `DECISION_LOG.md` in the same change that closes this task — per **D-096**.

## Related

D-095 (Graphiti retired — the precedent for a ruling that failed to propagate), D-096 (no task
closes without a logged ruling), D-093 (Portkey routing / SATemporal-Semantica A/B), D-068
(Temporal spine, n8n integration layer), ADR-0056 (Surreal governed projection), ADR-0061 (unified
operator surface).
