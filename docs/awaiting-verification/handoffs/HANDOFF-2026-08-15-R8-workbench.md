# HANDOFF — R8 Custom Workbench Product Surface (2026-08-15)

> _Byline: Codex · GPT-5 · 2026-08-15_
STATUS: PARTIAL
BUILD_STATUS: UNKNOWN

## Verified-live state (do not re-derive)

| Thing | State |
|---|---|
| Frontend | `workbench/web` is a Next.js application with existing operational screens and uncommitted classification additions |
| Backend | `workbench/api` is FastAPI with existing knowledge/Graphiti/OpenCode service wrappers |
| Product decision | Customize the Workbench rather than cloning Agno Studio |
| Runtime boundary | Frontend must consume neutral APIs and remain unaware of Agno versus AG2 |

## Findings / work done

- The visual product must expose evidence, extraction, horizons, belief evolution, handoffs, provider routes, approvals, OpenCode workspaces, traces, cost, health, and recovery using platform vocabulary.
- AgentOS database IDs and framework objects are infrastructure details and must not dominate the UI.
- Model selection needs scope/effect labels: next call, next stage, session, or agent default.
- Requested versus effective model, fallback, billing, context, and capability state must be visible after every response.

## UNRESOLVED (mandatory)

- Final information architecture and which existing pages are retained, merged, or quarantined.
- Neutral event-stream schema and AG-UI translation decision.
- Exact operator journey for court-safe export and restore status.

## Pending owner decisions

- Adopt the custom product map — WHAT: make the existing Workbench the primary control plane · WHY: AgentOS Studio is rigid and omits core project features · APPROACHES: customize Workbench, clone Studio, or build new app · SHORTCOMINGS: Workbench expansion requires sustained UX/API work. Recommendation: expand Workbench incrementally.

## Next steps (work in order)

1. Produce the three-layer app blueprint and screen inventory.
2. Freeze neutral session/run/event/model/approval/workspace APIs.
3. Build the horizon designer and delta experience first.
4. Add provider switching and handoff graph.
5. Add belief provenance, extraction review, and workspace operations.
6. Complete intake-to-export E2E and accessibility/responsive tests.

## Owner working-style contract

- UI speaks product concepts; failures and uncertainty are visible; no framework-specific client lock-in.
