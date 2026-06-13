---
title: AI DIAL Chat
type: reference
status: active
created: 2026-03-30
updated: 2026-03-30
reviewed: 2026-03-30
tags:
  - dial-stack
  - wiki
  - frontend
  - dial
  - chat
summary: Reference note for AI DIAL Chat as the current internal chat UI in dial-stack, distinct from the future analyst-facing UI direction.
repo_usage_state: partial
repo_version: docker.io/epam/ai-dial-chat:0.26.0 in docker-compose.yml
upstream_version: repo-pinned DIAL Chat reviewed 2026-03-30
official_docs:
  - https://docs.dialx.ai/
official_repo:
  - https://github.com/epam/ai-dial-chat
official_downloads:
  - https://github.com/epam/ai-dial-chat/releases
---

# AI DIAL Chat

## At a Glance

- **What it is**: The current DIAL chat UI paired with DIAL Core.
- **Current role in `dial-stack`**: Internal chat and operator-facing interface.
- **Why it matters**: It gives the current stack a usable chat surface without implying that chat is the final product boundary.

## How `dial-stack` Uses It

Current local anchors:

- [docker-compose.yml](C:/Users/matts/Projects/TheBigOne/dial-stack/docker-compose.yml)
- [infrastructure/core/config.json](C:/Users/matts/Projects/TheBigOne/dial-stack/infrastructure/core/config.json)

Current use:

- internal chat UI for DIAL-backed interactions
- operator-oriented surface for the current runtime
- internal application shell while the broader platform boundary evolves

## What It Is Not

- not the final analyst UI
- not the main ingress direction
- not the place where evidence business logic should live

## How We Could Expand Its Use

- keep it as an internal developer/operator chat surface
- use it for internal workflow testing while the analyst UI matures elsewhere
- expose selected tool workflows for power-user operations without making it the whole platform

## What We Need to Watch

- docs should not describe DIAL Chat as the final or only UI
- frontend behavior is tied to the pinned DIAL stack versions
- tool and evidence semantics should stay in backend tools, not in chat-layer assumptions

## Official Sources

- [DIAL Docs](https://docs.dialx.ai/)
- [DIAL Chat GitHub](https://github.com/epam/ai-dial-chat)
- [DIAL Chat Releases](https://github.com/epam/ai-dial-chat/releases)

## Related Notes

- [[skills/infrastructure/ai-dial-core|AI DIAL Core]]
- [[skills/frontend/copilotkit|CopilotKit]]
- [[skills/orchestration/contextforge/INDEX|ContextForge Integration]]
- [[INDEX|dial-stack Wiki Index]]
