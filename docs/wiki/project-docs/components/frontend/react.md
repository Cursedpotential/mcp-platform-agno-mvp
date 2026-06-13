---
title: React, Vite, and Tailwind
type: reference
status: active
created: 2026-03-30
updated: 2026-03-30
reviewed: 2026-03-30
tags:
  - dial-stack
  - wiki
  - frontend
  - react
  - vite
  - tailwind
summary: Reference note for the current frontend stack and how it fits into the future analyst-facing UI direction.
repo_usage_state: partial
repo_version: React 19.2.4, Vite 8.0.0, and related frontend stack pinned in client/package.json
upstream_version: current React, Vite, and Tailwind docs reviewed 2026-03-30
official_docs:
  - https://react.dev/
  - https://vite.dev/guide/
  - https://tailwindcss.com/docs
---

# React, Vite, and Tailwind

## At a Glance

- **What it is**: The current frontend implementation stack for the future analyst-facing UI.
- **Current role in `dial-stack`**: Under-implemented application shell for the custom UI direction.
- **Why it matters**: This is the most likely home for the analyst experience that will sit alongside internal DIAL usage.

## How `dial-stack` Uses It

Current local anchors:

- [client/package.json](C:/Users/matts/Projects/TheBigOne/dial-stack/client/package.json)
- [client/src/App.tsx](C:/Users/matts/Projects/TheBigOne/dial-stack/client/src/App.tsx)
- [docs/wiki/architecture/ARCHITECTURE.md](C:/Users/matts/Projects/TheBigOne/dial-stack/docs/wiki/architecture/ARCHITECTURE.md)

Current reality:

- the dependency stack is present
- the custom analyst UI is not yet fully integrated
- the frontend should consume the same tool surface as other clients instead of recreating backend logic

## How We Could Expand Its Use

- build the analyst-facing evidence review UI
- surface HITL workflows with CopilotKit
- connect to tool surfaces exposed through the gateway and MCP layers
- add richer views for provenance, review queues, and evidence lineage

## What We Need to Watch

- current frontend state should not be overstated as a finished product
- UI logic should remain thin over backend tools
- dependencies and build health need stabilization before deep product-layer work

## Official Sources

- [React Docs](https://react.dev/)
- [Vite Guide](https://vite.dev/guide/)
- [Tailwind CSS Docs](https://tailwindcss.com/docs)

## Related Notes

- [[skills/frontend/copilotkit|CopilotKit]]
- [[skills/frontend/dial-chat|AI DIAL Chat]]
- [[architecture/ARCHITECTURE|dial-stack Architecture]]
- [[INDEX|dial-stack Wiki Index]]
