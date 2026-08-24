# The knowledge-step bake — Agno-as-library vs PydanticAI

> _Byline: Claude Code · Opus 5 · 2026-08-23_

- **Status:** open. Neither side has won. Both are shipped INERT behind one env var.
- **Relates:** `docs/plans/TEMPORAL-INTEGRATION-PLAN-2026-08-23.md` (P1), DECISION_LOG **D-067**
- **Contract under test:** `run_knowledge_step(records_ref, lane, run_meta) -> KnowledgeResult`
  (defined in `server/temporal/knowledge_harness/__init__.py`)

## What is actually being compared

Both sides call the **same governed door** — `server/evidence/workflows.py::_knowledge_step_impl`
(:483), over the same `store.py::load_records_for_artifact` (:576) rows, into the same lane handle
from `context_chat_ingest.py::create_lane_knowledge` (:64). Nothing about *what touches the data*
differs. That is the whole point: with the pipeline held fixed, the only variable left is the
framework's shape.

- **Side A — `agno_harness.py`.** Assemble the ctx the existing step reads, await it, translate its
  `StepOutput` into `KnowledgeResult`. No model, no agent, no prompt.
- **Side B — `pydantic_ai_harness.py`.** An `Agent` with a deps-injected engine handle and exactly
  one typed tool. The tool is the only pipeline access the agent has; the agent's typed output is
  the caller's contract. Needs a model (`KNOWLEDGE_BAKE_MODEL`) to drive the single tool call.

## Scoring sheet

Fill this in from live runs on the fleet. Do not score from reading the code.

| Criterion | Weight | Side A (agno) | Side B (pydantic_ai) |
|---|---|---|---|
| **Fewest lines** — non-docstring, non-blank lines in the harness module | 1x | _measure_ | _measure_ |
| **Clearest failure behavior** — when Weaviate is down, what does the caller see? Is the exception the real one, or wrapped/retried/summarized into something vaguer? Does a zero-doc outcome ever read as success? | 3x | _observe_ | _observe_ |
| **Best typed contract** — what class of bug does the boundary actually catch? Does the type system prevent a wrong-shaped result reaching the workflow, or is it decoration over a call that was already typed? | 2x | _observe_ | _observe_ |
| Operational cost — tokens/latency per projection, and whether a model is needed at all | 1x | _measure_ | _measure_ |
| Determinism under Activity retry — same input, same result, no drift across attempts | 3x | _observe_ | _observe_ |

Weightings reflect what the plan says this stage is for: it is the stage that actually fails in
production (`workflows.py:36-44`), so failure legibility and retry determinism outrank elegance.

### The specific thing to watch on side B

A model sits between the caller and the tool result. The instructions tell it to call
`project_records` once and return the result unchanged, but "the model returned a *different*
`KnowledgeResult` than the tool produced" is a failure mode side A cannot have. If it happens even
once, that is decisive — an evidentiary pipeline cannot have a projection count that a language
model had an opinion about.

## Running each side live (env flip, one live path at a time)

Per the no-parallel-stacks rule, this is a flip, not a side-by-side deploy.

    # Side A (default — the env var may simply be unset)
    KNOWLEDGE_HARNESS=agno

    # Side B
    KNOWLEDGE_HARNESS=pydantic_ai
    KNOWLEDGE_BAKE_MODEL=<pydantic-ai model id>     # no default; unset is an error

Both are read by `activities.py::knowledge_activity` at Activity execution time, so a flip needs a
worker redeploy — remember Coolify renders env values as literals into the materialized compose at
deploy, so changing the variable does not reach a running container until a redeploy.

Install side B's dependency (never in the prod image by default):

    uv pip install -e ".[temporal-bake]"

Absent the extra, side B raises a `RuntimeError` naming the extra. It never degrades to side A —
a silent fallback would make a mistyped flip look like a successful A/B.

### What a scoring run looks like

1. Pick one real chat-transcript artifact already in custody (side B never re-ingests; it reads
   records back out of Postgres by `artifact_id`).
2. Run it through each side, recording `KnowledgeResult` and wall-clock.
3. Then run each side again **with Weaviate deliberately unreachable** — the failure column is
   worth 3x and cannot be filled in from a happy path.
4. Purge the test-run rows afterward. Test data never becomes canonical.

## The rule

**The loser gets deleted.** Not kept behind a flag, not left as a "reference implementation", not
renamed to `_legacy`. When the bake is called, the losing module and its branch in `get_harness()`
come out in the same commit, and `HARNESSES` shrinks to one name. If the winner is side A, the
`temporal-bake` extra comes out of `pyproject.toml` too.

Two live paths for one job is the thing this codebase keeps paying for. The bake is time-boxed by
that rule, not by a date.
