---
title: External Tool Adoption Proposals
type: proposal
status: active
created: 2026-03-30
updated: 2026-03-30
tags:
  - dial-stack
  - wiki
  - proposals
  - external-tooling
summary: Action-oriented adoption guidance for the current seven-tool evaluation set, aligned to the evidence-safe platform architecture.
proposal_scope: external-tool-adoption
---

# External Tool Adoption Proposals

## Purpose

This page turns the external-tool reference material into action-oriented adoption guidance for `dial-stack`.

The goal is not to "pick winners" in the abstract. The goal is to decide which tools deserve:

- immediate bounded adoption
- pilot status
- deferment
- reference-only treatment

All recommendations are constrained by the current architecture:

- evidence handling comes first
- all source data must be preserved
- `DuckDB -> PostgreSQL -> Semantica + LanceDB in parallel -> PostgreSQL enrichment`
- `ContextForge` is the main ingress direction
- `SBV` remains the preferred standalone SMS tool base

## Decision Summary

### Adopt now

- `Outlines`
- `Guidance`

### Pilot

- `FLAML`
- `GABRIEL`
- `Haystack`
- `EmoClassifiers`

### Reference only

- `Arthur AI Guardrails`

## Proposal Sections

## 1. Outlines

**Reference note**: [[references/external-tooling/outlines|Outlines]]

### Proposal

Adopt now for one high-value structured output path in the Python analysis layer.

### Why this proposal makes sense

- It improves reliability immediately.
- It has low architectural disruption.
- It fits tightly with evidence-safe derived analysis because it does not need to touch ingest or custody.

### Best initial use cases

- abuse screening result objects
- entity/event extraction records
- contradiction candidate records
- typed post-analysis writebacks into PostgreSQL

### Implementation sketch

1. Define a small set of Pydantic models for derived analysis outputs.
2. Wrap one Python analysis tool with Outlines.
3. Persist validated structured output and raw prompt/model provenance.
4. Compare parse failure and analyst usefulness against the current approach.

### Decision

- `Status`: Adopt now
- `Risk`: Low to medium
- `Expected payoff`: High

## 2. Guidance

**Reference note**: [[references/external-tooling/guidance|Guidance]]

### Proposal

Adopt now for one multi-step prompt-program workflow where branching or iterative control is clearly needed.

### Why this proposal makes sense

- Guidance complements Outlines rather than replacing it.
- It is especially useful where structured outputs alone are not enough and workflow logic matters.
- It can reduce brittle prompt chaining in post-ingest analysis.

### Best initial use cases

- behavioral screening with explicit branch logic
- multi-pass abuse analysis
- contradiction prechecks before deeper review
- controlled review-queue preparation

### Implementation sketch

1. Choose one currently fragile prompt flow.
2. Rebuild it as a Guidance program.
3. Keep the scope narrow and post-ingest only.
4. Measure validity, repeatability, and cost.

### Decision

- `Status`: Adopt now
- `Risk`: Medium
- `Expected payoff`: High

## 3. FLAML

**Reference note**: [[references/external-tooling/flaml|FLAML]]

### Proposal

Pilot FLAML earlier than originally planned as the foundation for narrow, custom, non-LLM classifiers.

### Why this proposal is elevated

- The platform is not only an LLM orchestration system. It is also meant to become a custom evidence-analysis platform.
- FLAML can help move stable narrow tasks away from prompt-only classification.
- It supports the preference for proven components plus customization where useful.

### Best initial use cases

- binary abuse-risk flags
- message triage/routing
- conversation severity scoring
- classifier baselines for later Semantica-adjacent features

### Implementation sketch

1. Pick one narrow classification target.
2. Create a modest labeled dataset from already-ingested evidence.
3. Build a feature extraction notebook or service.
4. Run FLAML as an offline training utility.
5. Expose the resulting model behind a Python MCP inference tool.

### What must be true first

- clear labels
- reproducible evaluation
- model metadata logging
- versioned deployment of trained artifacts

### Decision

- `Status`: Pilot
- `Risk`: Medium
- `Expected payoff`: High if labels exist

## 4. GABRIEL

**Reference note**: [[references/external-tooling/gabriel|GABRIEL]]

### Proposal

Pilot GABRIEL for one evidence-coding task and one de-identification task.

### Why this proposal makes sense

- It offers unusually rich post-ingest analysis primitives.
- It is well suited to coding and comparative review, which are hard to build cleanly from scratch.
- It stays on the safe side of the evidence boundary if used correctly.

### Best initial use cases

- coding message themes
- classifying abuse-related categories
- de-identifying derived review exports
- comparing competing narratives across threads

### Implementation sketch

1. Wrap a very small subset of GABRIEL capabilities in Python MCP tools.
2. Feed it only already-ingested, hashed, linked evidence.
3. Persist outputs in analysis/result tables.
4. Log model, prompt, input hash, and output hash.

### Decision

- `Status`: Pilot
- `Risk`: Medium
- `Expected payoff`: High for derived analysis workflows

## 5. Haystack

**Reference note**: [[references/external-tooling/haystack|Haystack]]

### Proposal

Pilot Haystack as a bounded post-ingest workflow engine, not as a wholesale platform replacement.

### Why this proposal makes sense

- Haystack is a good candidate for workflow-as-tool composition.
- It may reduce custom glue in the analysis tier.
- It fits the platform's preference for modular, callable workflows.

### Best initial use cases

- configurable enrichment pipelines
- post-ingest routing and branching
- orchestration of Semantica-adjacent derived analysis
- service-exposed workflow tools

### Implementation posture

- Complement first
- Replace later only if proven
- Never put Haystack in front of evidence-safe ingest

### Decision

- `Status`: Pilot
- `Risk`: Medium to high
- `Expected payoff`: Strategic, not immediate

## 6. EmoClassifiers

**Reference note**: [[references/external-tooling/emoclassifiers|EmoClassifiers]]

### Proposal

Run a narrow pilot as a secondary affective-signal layer.

### Why this proposal makes sense

- It may improve emotional-intensity routing and secondary validation.
- It is small enough to test without large platform changes.
- It may provide useful prompt and aggregation patterns even if not adopted directly.

### Best initial use cases

- emotional-intensity routing
- secondary signal for distress/escalation
- comparison against sentiment outputs

### Implementation sketch

1. Adapt its prompt logic into a bounded Python tool.
2. Run it only on a representative subset.
3. Compare with existing sentiment and abuse signals.
4. Keep only if it adds meaningful routing or validation value.

### Decision

- `Status`: Pilot
- `Risk`: Medium
- `Expected payoff`: Moderate, narrow

## 7. Arthur AI Guardrails

**Reference note**: [[references/external-tooling/arthur-ai-guardrails|Arthur AI Guardrails]]

### Proposal

Do not adopt now. Keep it as a benchmark/reference for future gateway safety design.

### Why this proposal makes sense

- It is commercial and not aligned with the current core bottlenecks.
- It belongs to gateway policy and runtime safety, not parser/ingest/store work.
- ContextForge and internal tooling are already the closer path for that layer.

### When it becomes worth revisiting

- if the platform needs enterprise-grade model safety/observability
- if external-facing LLM surfaces become much more important
- if internal guardrail ownership becomes too costly

### Decision

- `Status`: Reference only
- `Risk`: Low now, higher if adopted too early
- `Expected payoff`: Low near term

## Recommended Sequencing

### Phase 1: immediate reliability and structure

1. `Outlines`
2. `Guidance`

### Phase 2: bounded capability pilots

3. `FLAML`
4. `GABRIEL`
5. `EmoClassifiers`

### Phase 3: strategic orchestration pilot

6. `Haystack`

### Ongoing reference lane

7. `Arthur AI Guardrails`

## Important Guardrail

None of these tools should be allowed to:

- bypass `DuckDB` first-touch handling
- mutate or replace raw evidence
- become the new custody boundary
- quietly create a second undocumented orchestration center

The platform wins by wrapping these tools into the existing evidence-safe architecture, not by letting one of them take over the architecture by default.

## Related Notes

- [[proposals/INDEX|Proposals]]
- [[references/external-tooling/INDEX|External Tooling Reference]]
- [[proposals/haystack-incremental-parallel-deployment|Haystack Incremental Parallel Deployment]]
- [[INDEX|dial-stack Wiki Index]]
