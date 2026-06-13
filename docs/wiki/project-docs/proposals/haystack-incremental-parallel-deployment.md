---
title: Haystack Incremental Parallel Deployment
type: proposal
status: active
created: 2026-03-30
updated: 2026-03-30
tags:
  - dial-stack
  - wiki
  - proposals
  - haystack
  - deployment
  - workflows
summary: Proposal for evaluating Haystack through a bounded parallel rollout after canonical evidence writes, without disrupting ingest and custody boundaries.
proposal_scope: haystack-pilot
---

# Haystack Incremental Parallel Deployment

## Purpose

This proposal describes how to evaluate `Haystack` inside `dial-stack` without destabilizing the current architecture.

It is intentionally designed as:

- incremental
- parallel to the existing stack
- post-ingest only
- easy to cut if it does not earn its place

## Core Position

Haystack should **not** replace the evidence pipeline.

Haystack should be evaluated as:

- a workflow engine for derived analysis
- a workflow-as-tool layer
- a possible replacement for some custom internal orchestration glue

Haystack should **not** be evaluated as:

- the custody boundary
- the first-touch ingest layer
- the canonical evidence store
- the ingress/gateway authority

## Current Architecture Baseline

The current working pipeline is:

`source evidence -> DuckDB -> PostgreSQL -> Semantica + LanceDB in parallel -> PostgreSQL enrichment`

That means Haystack, if adopted, should slot in only after canonical Postgres write or within the derived-analysis phase.

## Why a Parallel Deployment Matters

Parallel deployment is the safest way to evaluate Haystack because it lets us answer the real question:

> Does Haystack reduce complexity and improve maintainability enough to justify itself?

without forcing the whole platform to bet on it early.

## Deployment Model

## Stage 0: No replacement, no traffic cutover

### Goal

Stand up Haystack in isolation with zero impact on the current ingest path.

### Shape

- Existing ingest flow remains unchanged.
- Existing TS/Py MCP tools remain the source of truth.
- Haystack runs as a sidecar analysis/workflow service.

### Required outputs

- working service container or local dev service
- one documented workflow
- one input contract
- one output contract

## Stage 1: One post-ingest workflow

### Goal

Build one useful workflow that starts from already-ingested evidence.

### Good first candidates

- derived abuse screening
- post-ingest classification pipeline
- analyst-facing summarization/coding prep
- review-queue preparation pipeline

### Flow

1. Evidence lands in DuckDB.
2. Evidence is written canonically to PostgreSQL.
3. Haystack workflow reads normalized Postgres data.
4. Workflow runs one or more derived-analysis steps.
5. Results are written back to PostgreSQL as derived records.

### Why this is the right first step

- no custody risk
- no parser risk
- clean success/failure boundaries
- easy comparison against existing Python-tool flows

## Stage 2: Workflow as tool

### Goal

Expose the Haystack workflow as a callable platform tool.

### Shape

- Haystack stays behind a service boundary.
- Existing MCP/tool layer calls it like any other workflow-tool.
- The platform does not yet depend on Haystack for core routing.

### Success criteria

- workflow can be called repeatably
- input and output are versioned
- provenance fields are preserved
- failures are isolated and recoverable

## Stage 3: Multiple bounded workflows

### Goal

Evaluate whether Haystack is materially better for a family of workflow use cases.

### Candidate categories

- analyst preparation workflows
- classification workflows
- comparative review workflows
- retrieval-assisted derived analysis

### Decision point

At this stage, decide whether Haystack is:

- clearly reducing complexity
- roughly neutral
- adding one more orchestration layer without enough payoff

## Stage 4: Optional DIAL-role reduction

### Goal

Only after proven success, evaluate whether Haystack can replace some internal workflow glue currently associated with DIAL.

### Important limit

This is **not** the same as replacing DIAL outright.

The most plausible outcome is:

- `ContextForge` remains ingress/gateway direction
- `Haystack` absorbs some workflow composition duties
- `DIAL` shrinks or becomes less central internally

That is a very different decision from "replace DIAL with Haystack."

## What Needs to Be Built

For this deployment strategy to be sound, the following pieces need to exist:

- a narrow workflow contract
- workflow result schema
- provenance logging for workflow runs
- input hash and output hash capture
- clear Postgres tables for derived workflow outputs
- review queue integration for risky results
- service health and timeout handling

## What You Might Be Missing

These are the pieces most likely to get missed in a Haystack pilot:

- **Provenance adapter**: workflow outputs need the same trace discipline as any other derived analysis.
- **Result schemas**: without a stable schema, Haystack adds ambiguity instead of reducing it.
- **Failure policy**: decide whether a failed workflow blocks nothing, blocks analyst views, or only marks a task incomplete.
- **Version tracking**: workflow definitions need version IDs, not just code history.
- **Evaluation harness**: you need a side-by-side comparison against the current way of doing the same task.
- **Scope discipline**: Haystack must not quietly absorb ingest or gateway responsibilities while still in pilot mode.

## Risks

### Architectural risks

- Haystack becomes a second orchestration center.
- The team starts encoding business logic in workflows without documenting it elsewhere.
- It overlaps awkwardly with ContextForge and internal MCP workflow ideas.

### Operational risks

- another service to run and monitor
- more runtime dependencies
- Python-first assumptions leaking into a broader multi-service design

### Product risks

- good demo, weak long-term fit
- workflow sprawl without real simplification
- attractive abstraction that does not actually reduce maintenance

## Success Criteria

The pilot is a success if Haystack gives you:

- clearer workflow composition than the current approach
- less custom glue
- easier iteration on workflow changes
- clean provenance and persistence
- no compromise to evidence handling boundaries

The pilot is not a success if it mainly gives:

- another service to maintain
- another DSL/config layer to debug
- no measurable reduction in code or complexity

## Recommended Pilot Sequence

1. Stand up Haystack as an isolated sidecar.
2. Implement one post-ingest workflow.
3. Expose it as a callable tool.
4. Add provenance and Postgres writeback.
5. Compare against the current implementation path.
6. Expand only if the comparison is decisively positive.

## Recommendation

Proceed with a **bounded parallel pilot**, not a replacement project.

Haystack is promising because it aligns with workflow-as-tool design. It is risky because it could easily become a second center of orchestration before it proves that it deserves to exist.

The right move is to make it earn its place one workflow at a time.

## Related Notes

- [[references/external-tooling/haystack|Haystack]]
- [[proposals/INDEX|Proposals]]
- [[proposals/external-tool-adoption-proposals|External Tool Adoption Proposals]]
- [[skills/infrastructure/ai-dial-core|AI DIAL Core]]
- [[skills/orchestration/contextforge/INDEX|ContextForge Integration]]
- [[INDEX|dial-stack Wiki Index]]
