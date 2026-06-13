---
title: CopilotKit
type: reference
status: active
created: 2026-03-30
updated: 2026-03-30
reviewed: 2026-03-30
tags:
  - dial-stack
  - wiki
  - frontend
  - copilotkit
  - hitl
summary: Reference note for CopilotKit as the likely analyst-facing HITL framework for the future UI layer in dial-stack.
repo_usage_state: partial
repo_version: @copilotkit/react-core and @copilotkit/react-ui ^1.53.0 in client/package.json
upstream_version: CopilotKit 1.54.0 latest GitHub release reviewed 2026-03-30
official_docs:
  - https://docs.copilotkit.ai/
official_repo:
  - https://github.com/CopilotKit/CopilotKit
official_downloads:
  - https://www.npmjs.com/package/@copilotkit/react-core
  - https://github.com/CopilotKit/CopilotKit/releases
---

# CopilotKit

## At a Glance

- **What it is**: A React framework for AI copilots, agentic UI patterns, and human-in-the-loop flows.
- **Current role in `dial-stack`**: Candidate framework for the future analyst-facing UI and review workflows.
- **Current repo state**: Dependency is present, but the client is still under-implemented and not yet a finished analyst surface.

## How `dial-stack` Uses It

Current local anchors:

- [client/package.json](C:/Users/matts/Projects/TheBigOne/dial-stack/client/package.json)
- [docs/wiki/architecture/ARCHITECTURE.md](C:/Users/matts/Projects/TheBigOne/dial-stack/docs/wiki/architecture/ARCHITECTURE.md)

Current intended responsibilities:

- human-in-the-loop evidence review
- analyst guidance and contextual copilot behavior
- tool-assisted review flows on top of the same backend tool surface

## Repo Version vs Upstream Version

| Posture | Value | Notes |
|---|---|---|
| Repo packages | `^1.53.0` | Declared in the client package |
| Upstream latest reviewed | `1.54.0` | Latest GitHub release reviewed 2026-03-30 |
| Current UI reality | partial | Frontend integration is present only at an early stage |

## How We Could Expand Its Use

- analyst-side HITL review queues
- guided approval and exception handling for extracted facts
- stateful review workflows connected to the same MCP tool surfaces
- future coagent-style collaboration patterns where helpful

## What We Need to Watch

- the frontend is not currently mature enough to imply full CopilotKit adoption
- UI copilot flows must remain traceable back to evidence and canonical record IDs
- action handlers should call backend tools, not reimplement business logic in the frontend
- version drift is modest now, but still worth pinning more tightly during stabilization

## Key Repo Files

- [client/package.json](C:/Users/matts/Projects/TheBigOne/dial-stack/client/package.json)
- [ARCHITECTURE.md](C:/Users/matts/Projects/TheBigOne/dial-stack/docs/wiki/architecture/ARCHITECTURE.md)
- [ROADMAP.md](C:/Users/matts/Projects/TheBigOne/dial-stack/docs/plans/ROADMAP.md)

## Official Sources

- [CopilotKit Docs](https://docs.copilotkit.ai/)
- [CopilotKit GitHub](https://github.com/CopilotKit/CopilotKit)
- [CopilotKit React Core Package](https://www.npmjs.com/package/@copilotkit/react-core)
- [CopilotKit Releases](https://github.com/CopilotKit/CopilotKit/releases)

## Related Notes

- [[skills/infrastructure/ai-dial-core|AI DIAL Core]]
- [[skills/orchestration/contextforge/INDEX|ContextForge Integration]]
- [[architecture/ARCHITECTURE|dial-stack Architecture]]
- [[INDEX|dial-stack Wiki Index]]
