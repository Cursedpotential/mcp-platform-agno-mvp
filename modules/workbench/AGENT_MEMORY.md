---
scope: workbench
status: current
verified_at: 2026-08-27
superseded_by: null
authority:
  - AGENTS.md
  - docs/design/0061-unified-operator-surface/spec.md
  - docs/reviews/2026-08-27-workbench-auth-rotation.md
  - workbench/design-mockups/unified-operator-surface/AGENTS.md
watches:
  - workbench/**
  - docs/design/0061-unified-operator-surface/spec.md
contains_secrets: false
---

# Operator Surface Memory

> _Byline: Codex · GPT-5 · 2026-08-27._

## Owner-approved product direction

- The unified surface combines an everyday **Evidence Operations Desk** with a more advanced
  **Modular Service Cockpit**, using one coherent visual language and light/dark themes.
- Finish a functional vertical slice before adding another destination. Do not expand navigation
  with stubs, disconnected dashboards, or backend claims that are not wired.
- The surface is single-user and single-case. Prefer plain-language labels, visible case/court
  context, compact operational density, and no unexplained two-letter abbreviations.
- Timesketch should be available as a timeline view across the operator experience. Temporal, n8n,
  Semantica, database, graph, and storage interfaces remain tools over canonical authority.
- Traces, logs, and progress should stream to the surface in real time, including LLM operations.

## Critical correction

The legacy Operator Console and its LanceDB staging design are not the approved unified product.
Do not revive, redeploy, or present that surface as progress toward the approved UI.

## Child memory

For the approved implementation, read
`workbench/design-mockups/unified-operator-surface/AGENT_MEMORY.md`.

<!-- freshness
watches_hash: 8f36944
last_verified: 2026-08-27
watches:
  - workbench/**/*.py
  - workbench/**/*.ts
  - workbench/**/*.tsx
  - docs/design/0061-unified-operator-surface/spec.md
-->
