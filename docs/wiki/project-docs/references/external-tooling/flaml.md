---
title: FLAML
type: reference
status: active
created: 2026-03-30
updated: 2026-03-30
tags:
  - dial-stack
  - wiki
  - external-tooling
  - automl
  - classifiers
summary: Reference page for FLAML as a near-term pilot candidate for narrow custom classifier development.
recommendation: pilot
integration_stage: post-ingest-modeling
---

# FLAML — External Tool Reference

## Overview

- **What**: Lightweight AutoML and tuning library from Microsoft.
- **Best fit**: Custom classifier development after normalized evidence is already stored.
- **Primary value**: Fast baseline models, efficient tuning, and lower-cost experimentation.

## Feature Breakdown

- **Task-oriented AutoML**: Supports classification, regression, ranking, forecasting, and user-defined tuning workloads.
- **Economical search**: Designed to reduce time and compute spent finding workable models.
- **Zero-shot defaults**: Can produce useful baselines quickly with less hand-tuning.
- **Python-friendly**: Fits naturally into the existing Python analysis environment.

## How It Could Help `dial-stack`

- **Custom classifiers**: Strong candidate for building case-specific or platform-specific models for abuse, manipulation, coercive control, or triage.
- **Prompt fallback reduction**: Gives the platform a path away from prompt-only classification once labeled data exists.
- **Evidence-derived features**: Can learn from structured features derived from message, conversation, and analysis tables.

## What It Would Enhance

- repeatable baseline classifier training
- low-cost model comparison
- faster iteration on custom narrow models
- safer movement from heuristics to trained classifiers

## Implementation Approach

- **Training lane**: Pull labeled or pseudo-labeled data from PostgreSQL after normalization.
- **Feature layer**: Build feature extractors from message text, metadata, participation patterns, timing, and prior analysis signals.
- **Inference lane**: Expose trained models through Python MCP tools as a derived-analysis capability.
- **Governance**: Log model version, training inputs, metrics, and deployment metadata into platform tables.

## Why It Matters More Than a Typical "Later" Tool

- **You want custom tooling without reinventing everything**: FLAML helps bootstrap custom models from proven components.
- **It can reduce brittle prompt dependence**: Especially useful for stable, repeatable narrow tasks.
- **It fits the long-term plan**: The platform is not just a prompt router. It is meant to become a serious evidence-analysis system with customized components.

## Roadblocks and Watch-Outs

- **Needs labels**: FLAML is powerful once there is data and evaluation discipline.
- **Feature design matters**: Weak features will make fast AutoML look better than it is.
- **Model governance**: Even small models need evaluation, versioning, and drift tracking.

## Planning Guidance

1. Define one narrow classification task with real value.
2. Build a small labeled dataset or pseudo-label set from existing analysis outputs.
3. Train a baseline FLAML model.
4. Compare it against prompt-based classification before operationalizing.

## Recommendation

- **Current lane**: `Near-term pilot candidate`

## Related Notes

- [[references/external-tooling/INDEX|External Tooling Reference]]
- [[proposals/external-tool-adoption-proposals|External Tool Adoption Proposals]]
- [[skills/nlp/semantica|Semantica]]
- [[INDEX|dial-stack Wiki Index]]

## Sources

- [FLAML Getting Started](https://microsoft.github.io/FLAML/docs/Getting-Started/)
- [FLAML Best Practices](https://microsoft.github.io/FLAML/docs/Best-Practices/)
