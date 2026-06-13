---
title: Outlines
type: reference
status: active
created: 2026-03-30
updated: 2026-03-30
tags:
  - dial-stack
  - wiki
  - external-tooling
  - structured-outputs
  - analysis
summary: Reference page for Outlines as the best immediate fit for typed structured outputs in the Python analysis layer.
recommendation: adopt-now
integration_stage: post-ingest-analysis
---

# Outlines — External Tool Reference

## Overview

- **What**: Structured output and constrained generation library centered on typed outputs.
- **Best fit**: Post-ingest typed extraction and schema-safe analysis outputs.
- **Primary value**: Reliable structured generation using types and schemas instead of fragile free-form parsing.

## Feature Breakdown

- **Typed outputs**: Supports literal values, primitives, and typed models.
- **Schema discipline**: Strong fit for Pydantic-backed structured extraction.
- **Constrained generation**: Designed to keep outputs inside expected shapes.
- **Production utility**: Especially useful where malformed output breaks downstream persistence.

## How It Could Help `dial-stack`

- **Typed analysis records**: Excellent fit for storing derived message/conversation analysis in PostgreSQL.
- **Safer enrichment**: Good match for post-ingest `NER`, sentiment, abuse labels, and other tightly-typed outputs.
- **Lower failure rate**: Reduces the need for repair parsing and brittle output cleanup.

## What It Would Enhance

- schema-safe extraction
- analysis output reliability
- easier Postgres persistence
- lower downstream parser fragility

## Implementation Approach

- **Placement**: Python MCP analysis layer, after normalized evidence is already written.
- **Initial use cases**:
  - abuse screening result objects
  - entity/event extraction objects
  - contradiction candidate records
- **Persistence**: Write validated output plus raw model metadata for traceability.

## Roadblocks and Watch-Outs

- **Not for everything**: It is strongest where the target schema is clear.
- **Schema quality matters**: Poor or overly rigid schema design can hide nuance.
- **Model/provider fit**: Needs testing against the specific model backends you want to use.

## Planning Guidance

1. Pick one high-value structured output shape.
2. Define the typed model cleanly.
3. Build an Outlines-backed extraction path.
4. Compare failure rate with current free-form outputs.
5. Expand only where the reliability gain is obvious.

## Recommendation

- **Current lane**: `Adopt now`

## Related Notes

- [[references/external-tooling/INDEX|External Tooling Reference]]
- [[proposals/external-tool-adoption-proposals|External Tool Adoption Proposals]]
- [[skills/nlp/semantica|Semantica]]
- [[tools/py-mcp-server|Py MCP Server Tools]]
- [[INDEX|dial-stack Wiki Index]]

## Sources

- [Outlines GitHub README](https://github.com/dottxt-ai/outlines)
