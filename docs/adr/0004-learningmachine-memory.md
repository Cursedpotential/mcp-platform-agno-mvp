# ADR-0004: Memory = native LearningMachine; no hand-rolled learned_knowledge table
- Status: Accepted
- Date: 2026-06-01

## Context
The v1 repo hand-rolled a `learned_knowledge` SQL table + `store_learned_knowledge()`. Agno provides a
native `LearningMachine` with managed stores and capture modes, verified to exist in the current version.

## Decision
Use the native **LearningMachine** on the existing Postgres (no extra container). Stores: User Profile,
User Memory, Session Context, Entity Memory, Learned Knowledge, **Decision Log**. Modes: `ALWAYS`/
`AGENTIC` for profile/session; **`PROPOSE`** (agent proposes, human confirms) for the durable, high-stakes
stores (Entity Memory, Learned Knowledge). `enable_clear_memories=False`. The **Decision Log** store is
used for the approval/decision audit trail. **No custom `learned_knowledge` table.**

## Consequences
- Memory is a managed feature; the HITL philosophy extends to memory capture via PROPOSE.
- Exact import path (`agno.learn` vs `agno.learning`) must be confirmed against the pinned image.
- Graphiti temporal graph is a platform-stage addition, not an MVP mirror.

## Alternatives considered
- Custom SQL memory table (v1) — rejected: reinvents a native, managed capability.
