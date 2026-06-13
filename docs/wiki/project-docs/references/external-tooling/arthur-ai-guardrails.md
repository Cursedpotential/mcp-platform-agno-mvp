---
title: Arthur AI Guardrails
type: reference
status: active
created: 2026-03-30
updated: 2026-03-30
tags:
  - dial-stack
  - wiki
  - external-tooling
  - guardrails
  - gateway
summary: Reference page for Arthur AI Guardrails, focused on gateway/runtime safety fit rather than evidence ingest.
recommendation: reference-only
integration_stage: future-gateway-evaluation
---

# Arthur AI Guardrails — External Tool Reference

## Overview

- **What**: Commercial runtime guardrail and observability layer for LLM applications.
- **Best fit**: Gateway and model-safety layer, not evidence ingest.
- **Primary value**: Real-time checks around prompt injection, sensitive data leakage, hallucinations, and toxic outputs.

## Feature Breakdown

- **Bidirectional guardrails**: Evaluates both incoming prompts and outgoing model responses.
- **Safety categories**: Emphasizes prompt injection, hallucinations, toxicity, and sensitive data leakage.
- **Operational posture**: Positioned as a production safety and observability product rather than a small library.
- **Model-agnostic framing**: Intended to sit between applications and model providers.

## How It Could Help `dial-stack`

- **ContextForge boundary**: Arthur is most relevant if the project later wants a commercial safety layer at the ingress/gateway boundary.
- **Analyst surfaces**: Could protect future chat or copiloted analysis surfaces from unsafe generations.
- **Benchmarking**: Useful reference for what a mature enterprise guardrail product covers, even if not adopted.

## What It Would Enhance

- LLM-facing runtime safety
- policy enforcement on prompt/response traffic
- observability for harmful or risky model behavior
- enterprise-style monitoring and intervention

## Implementation Approach

- **Placement**: In front of or alongside the model gateway layer, not inside the ingest pipeline.
- **Integration pattern**: Request enters gateway -> guardrail check -> allowed traffic continues -> detections logged as derived events.
- **Persistence**: Any guardrail flags should be stored as derived platform signals, not as replacements for raw evidence.

## Roadblocks and Watch-Outs

- **Commercial dependency**: Adds cost, vendor coupling, and evaluation overhead.
- **Wrong layer risk**: It does not solve parser, custody, storage, or evidence normalization work.
- **Overlap risk**: Some policy/guardrail responsibilities may already belong to ContextForge or internal tooling.

## Planning Guidance

1. Keep Arthur as a benchmark while defining gateway policy capabilities.
2. Only evaluate it seriously if the project later decides it wants enterprise guardrail SaaS.
3. Do not let Arthur-shaped thinking displace evidence-safe ingest priorities.

## Recommendation

- **Current lane**: `Reference / benchmark only`

## Related Notes

- [[references/external-tooling/INDEX|External Tooling Reference]]
- [[proposals/external-tool-adoption-proposals|External Tool Adoption Proposals]]
- [[skills/orchestration/contextforge/INDEX|ContextForge Integration]]
- [[INDEX|dial-stack Wiki Index]]

## Sources

- [Arthur AI Built-in Guardrails](https://www.arthur.ai/built-in-guardrails)
