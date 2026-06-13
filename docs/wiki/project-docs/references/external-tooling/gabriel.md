---
title: GABRIEL
type: reference
status: active
created: 2026-03-30
updated: 2026-03-30
tags:
  - dial-stack
  - wiki
  - external-tooling
  - coding
  - derived-analysis
summary: Reference page for GABRIEL as a pilot candidate for post-ingest evidence coding, comparison, and de-identification workflows.
recommendation: pilot
integration_stage: post-ingest-derived-analysis
---

# GABRIEL — External Tool Reference

## Overview

- **What**: OpenAI toolkit for measuring and coding quantitative attributes in text, images, and audio.
- **Best fit**: Post-ingest derived analysis, qualitative coding, de-identification, and comparative review.
- **Primary value**: Rich analysis primitives that can accelerate evidence coding and large-scale review tasks.

## Feature Breakdown

- **Task primitives**: Includes `rate`, `rank`, `classify`, `extract`, `discover`, `compare`, `codify`, `merge`, `deduplicate`, `filter`, and `deidentify`.
- **Research-style workflows**: Strong fit for coding corpora and generating measured outputs over large datasets.
- **De-identification support**: Useful where derived datasets need privacy-preserving transformations.
- **Comparative analysis**: Helpful for cross-message or cross-document coding and scoring.

## How It Could Help `dial-stack`

- **Evidence coding**: Could accelerate post-ingest tagging of abuse, themes, or evidentiary patterns.
- **Comparative review**: Useful for comparing threads, timelines, or participants.
- **Derived sharing layers**: De-identification capabilities could support future export/reporting workflows.

## What It Would Enhance

- qualitative coding at scale
- comparative analysis of evidence corpora
- de-identification experiments for derived outputs
- candidate deduplication or clustering support

## Implementation Approach

- **Placement**: Derived-analysis layer only, after evidence has been stored canonically.
- **Wrap in tools**: Expose a bounded set of GABRIEL-backed capabilities through the Python MCP server.
- **Provenance**: Persist input hash, output hash, model metadata, and operator/workflow metadata.
- **Storage**: Write only derived results back into analysis tables; never replace raw evidence.

## Roadblocks and Watch-Outs

- **Provider coupling**: GABRIEL is closely tied to OpenAI ecosystem assumptions.
- **Cost exposure**: Large-corpus analysis can get expensive.
- **Boundary discipline**: It must not drift into evidence intake or mutate source-of-truth evidence records.

## Planning Guidance

1. Choose one evidence coding task and one de-identification task.
2. Pilot them on a representative but bounded sample.
3. Compare utility against current prompt or rules-based workflows.
4. Keep only the capabilities that clearly improve throughput or quality.

## Recommendation

- **Current lane**: `Pilot`

## Related Notes

- [[references/external-tooling/INDEX|External Tooling Reference]]
- [[proposals/external-tool-adoption-proposals|External Tool Adoption Proposals]]
- [[skills/nlp/semantica|Semantica]]
- [[tools/py-mcp-server|Py MCP Server Tools]]
- [[INDEX|dial-stack Wiki Index]]

## Sources

- [GABRIEL GitHub README](https://github.com/openai/GABRIEL)
