---
title: Guidance
type: reference
status: active
created: 2026-03-30
updated: 2026-03-30
tags:
  - dial-stack
  - wiki
  - external-tooling
  - prompting
  - analysis
summary: Reference page for Guidance as a bounded near-term adoption candidate for multi-step prompt programs in the Python analysis layer.
recommendation: adopt-now
integration_stage: post-ingest-analysis
---

# Guidance — External Tool Reference

## Overview

- **What**: Pythonic control framework for steering LLMs with structured, programmable prompt logic.
- **Best fit**: Post-ingest extraction, classification, and multi-step tool-aware analysis.
- **Primary value**: Constrained outputs, explicit control flow, and reusable prompt programs.

## Feature Breakdown

- **Constrained generation**: Supports regex, CFG-style constraints, and bounded output control.
- **Prompt programs**: Combines control flow, generation, and tool-like steps in code.
- **Branching and looping**: Useful when one analysis step depends on another.
- **Backend flexibility**: Works across multiple LLM backends, including OpenAI-compatible paths.

## How It Could Help `dial-stack`

- **Structured evidence analysis**: Good fit for analysis steps that are too complex for a single one-shot prompt.
- **Workflow discipline**: Lets us encode multi-step reasoning/classification flows in a reusable program instead of loose prompt text.
- **Safer derived outputs**: Can help keep structured results stable before they are written back to PostgreSQL.

## What It Would Enhance

- multi-step classification pipelines
- repeatable extraction logic
- prompt reliability and reuse
- controlled routing within Python analysis tools

## Implementation Approach

- **Placement**: Python MCP server only, after evidence has already been ingested and normalized.
- **Initial use cases**:
  - abuse screening with explicit label sets
  - behavioral coding with branch logic
  - contradiction prechecks before deeper review
- **Persistence**: Store both the structured output and the raw model exchange metadata.

## Roadblocks and Watch-Outs

- **Complexity creep**: Guidance can become its own little orchestration layer if used everywhere.
- **Latency**: Multi-step prompt programs can get slower and more expensive than a typed extraction call.
- **Learning curve**: Team members need to understand the control model to maintain it well.

## Planning Guidance

1. Start with one fragile analysis task.
2. Rebuild it as a Guidance program with explicit outputs.
3. Compare validity, consistency, and cost against the current method.
4. Expand only where prompt programs clearly outperform simpler alternatives.

## Recommendation

- **Current lane**: `Adopt now for a bounded prototype`

## Related Notes

- [[references/external-tooling/INDEX|External Tooling Reference]]
- [[proposals/external-tool-adoption-proposals|External Tool Adoption Proposals]]
- [[skills/nlp/semantica|Semantica]]
- [[tools/py-mcp-server|Py MCP Server Tools]]
- [[INDEX|dial-stack Wiki Index]]

## Sources

- [Guidance GitHub README](https://github.com/guidance-ai/guidance)
