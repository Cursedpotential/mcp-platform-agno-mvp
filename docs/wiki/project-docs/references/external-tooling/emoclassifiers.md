---
title: EmoClassifiers
type: reference
status: active
created: 2026-03-30
updated: 2026-03-30
tags:
  - dial-stack
  - wiki
  - external-tooling
  - emotion
  - sentiment
summary: Reference page for EmoClassifiers as a narrow pilot or reference pattern for affective signal analysis.
recommendation: pilot
integration_stage: post-ingest-secondary-analysis
---

# EmoClassifiers — External Tool Reference

## Overview

- **What**: OpenAI repository for affective classification of user-chatbot conversations.
- **Best fit**: Secondary emotional-signal or sentiment-adjacent analysis after ingest.
- **Primary value**: Reference patterns and possible narrow pilot for affective cue detection.

## Feature Breakdown

- **Prompt-defined classifiers**: Ships prompt sets and classifier patterns.
- **Chunking and aggregation**: Includes ways to break conversations up and recombine scores.
- **Hierarchical logic**: Supports classifier families and grouped analysis patterns.
- **Parallel runs**: Includes example flows for asynchronous processing.

## How It Could Help `dial-stack`

- **Secondary signal layer**: Could augment sentiment or emotional-intensity routing.
- **HITL support**: Might help prioritize emotionally intense conversations for analyst review.
- **Prompt pattern reference**: Useful even if not adopted directly, because it shows working affective-analysis patterns.

## What It Would Enhance

- affective cue detection
- conversation chunking strategies
- secondary validation for emotion-related derived outputs
- analyst review prioritization

## Implementation Approach

- **Placement**: Python MCP derived-analysis layer only.
- **Use narrowly**: Run it as a secondary, optional analysis pass rather than a first-line classifier.
- **Persistence**: Store emotion/affect tags as derived analysis outputs linked to source hashes and conversation IDs.

## Roadblocks and Watch-Outs

- **Domain mismatch risk**: Chatbot-conversation framing may not map perfectly to evidentiary SMS/Facebook material.
- **Misclassification warning**: The repository explicitly warns about classification errors.
- **Narrow scope**: It should not crowd out more general analysis tooling.

## Planning Guidance

1. Test on a small SMS/Facebook sample.
2. Compare output against existing sentiment and abuse-screening signals.
3. Keep only if it adds meaningful recall or routing value.

## Recommendation

- **Current lane**: `Limited pilot / reference`

## Related Notes

- [[references/external-tooling/INDEX|External Tooling Reference]]
- [[proposals/external-tool-adoption-proposals|External Tool Adoption Proposals]]
- [[skills/nlp/semantica|Semantica]]
- [[INDEX|dial-stack Wiki Index]]

## Sources

- [EmoClassifiers GitHub README](https://github.com/openai/emoclassifiers)
