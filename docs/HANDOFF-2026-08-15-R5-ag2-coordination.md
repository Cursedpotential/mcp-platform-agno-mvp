# HANDOFF — R5 AG2 Coordination Evaluation (2026-08-15)

> _Byline: Codex · GPT-5 · 2026-08-15_
STATUS: COMPLETE
BUILD_STATUS: UNKNOWN

## Verified-live state (do not re-derive)

| Thing | State |
|---|---|
| Current runtime | Agno 2.8.7 / AgentOS with route and coordinate team topology |
| AG2 target | AG2 v1 Network, not AG2 Classic; official PyPI reported 1.0.2 on 2026-08-15 |
| Current HITL | Agno-native approval remains the active authority |
| Migration posture | No AG2 package installed or runtime code changed during research |

## Findings / work done

- AG2 Network is a strong coordination candidate: typed channels, transition graphs, handoffs, WAL/replay, checkpoints, distributed agents, telemetry, MCP, and per-turn model override.
- AG2 should own coordination mechanics only. Evidence, horizon policy, provider policy, approvals, beliefs, tools, idempotency, and durable run reports remain platform-owned.
- The new-major release is too young for immediate wholesale adoption.
- A neutral `OrchestrationPort` and typed `HandoffPacket` are required before the bake-off.

## UNRESOLVED (mandatory)

- Crash-safe HITL continuation parity.
- Redis store versus a future PostgreSQL coordination-store adapter.
- AG-UI translation versus the existing neutral SSE contract.
- Whether legacy agents are wrapped or selectively rewritten after a successful spike.

## Pending owner decisions

- Authorize bounded AG2 spike — WHAT: one non-court-facing workflow behind the neutral port · WHY: measure coordination/recovery/model-switch advantages · APPROACHES: keep Agno, immediate AG2 migration, or strangler spike · SHORTCOMINGS: temporary dual-runtime complexity. Recommendation: strangler spike.

## Next steps (work in order)

1. Freeze neutral orchestration and handoff contracts.
2. Implement triage → specialists → reviewer → human gate → synthesis.
3. Test restart/replay and duplicate side-effect protection.
4. Test platform approval persistence and future-fact exclusion.
5. Test consecutive-turn model switching through Portkey.
6. Compare latency, trace fidelity, context quality, and operational burden with Agno.
7. Record adopt/reject decision in an ADR.

## Owner working-style contract

- No framework lock-in; every workflow has limits and terminal states; protected writes remain disconnected until replay/idempotency gates pass.
