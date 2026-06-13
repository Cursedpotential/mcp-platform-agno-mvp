---
title: OpenRouter
type: reference
status: active
created: 2026-03-30
updated: 2026-03-30
reviewed: 2026-03-30
tags:
  - dial-stack
  - wiki
  - utility
  - openrouter
  - llm
summary: Reference note for OpenRouter as the current external multi-model API endpoint configured behind the DIAL runtime.
repo_usage_state: active
repo_version: OPENROUTER endpoint and key wiring present in docker-compose.yml and DIAL config
upstream_version: API v1 docs reviewed 2026-03-30
official_docs:
  - https://openrouter.ai/docs
official_downloads:
  - https://openrouter.ai/docs/api-reference/overview
---

# OpenRouter

## At a Glance

- **What it is**: Multi-model API router exposing many upstream model providers behind a unified API.
- **Current role in `dial-stack`**: External model endpoint configured behind DIAL Core.
- **Why it matters**: It gives the current stack broad model access without every client owning direct provider integrations.

## How `dial-stack` Uses It

Current local anchors:

- [docker-compose.yml](C:/Users/matts/Projects/TheBigOne/dial-stack/docker-compose.yml)
- [infrastructure/core/config.json](C:/Users/matts/Projects/TheBigOne/dial-stack/infrastructure/core/config.json)

Current use:

- DIAL routes model traffic through OpenRouter
- server-side API key handling
- model provider abstraction for current internal chat usage

## What We Are Not Using It For

- evidence storage
- direct provenance or custody logic
- frontend-exposed direct API usage

## How We Could Expand Its Use

- controlled model-cost routing by workflow type
- separating cheap classification lanes from more expensive reasoning lanes
- fallback model policies for non-evidence-critical tasks
- better model inventory notes in the wiki once provider usage stabilizes

## What We Need to Watch

- API keys must remain server-side only
- provider/model naming drift needs explicit config discipline
- model routing should never blur evidence provenance with model output provenance
- external model changes should be documented as dependency changes, not just config tweaks

## Official Sources

- [OpenRouter Docs](https://openrouter.ai/docs)
- [OpenRouter Models](https://openrouter.ai/models)
- [OpenRouter API Reference](https://openrouter.ai/docs/api-reference/overview)

## Related Notes

- [[skills/infrastructure/ai-dial-core|AI DIAL Core]]
- [[skills/infrastructure/docker-compose|Docker Compose]]
- [[INDEX|dial-stack Wiki Index]]
