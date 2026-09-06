# Prompt: plan the split of the analysis engine as `indagatio` (D-139)

> _Byline: Claude Code · Fable 5.1 · 2026-09-06. Agent-ready prompt file. Read `README.md` in this folder for the standing rules._

## Goal
The analysis engine (horizon walks, ignorant and hindsight agents, the delta; SurrealDB as its store, D-073/D-080) becomes its own product **Indagatio Veri** / `indagatio` with its own Go front end and its own tsnet identity (D-134). Produce a `/make-plan` style plan. STATUS: ITERATING until the owner says it is done; the owner decides when a plan is done, never the agent.

## Must cover
- The boundary contract between `probata` (evidence record, `working.*` / `evidence.*`) and `indagatio` (analysis over it): what crosses, by reference only (D-130 rule 5).
- What moves out of `modules/engine` (packages, activities, stage-graph nodes) and what stays. The SurrealDB namespace name (R-9) must be ruled first.
- tsnet service `svc:indagatio`, a tagged auth key (`tag:docker`), a Coolify app, and watch paths.
- The knowledge-horizon invariants from AGENTS.md "WHY THIS EXISTS": the horizon is a pre-filter in every store, dict filters only on Weaviate, and contamination is silent.
