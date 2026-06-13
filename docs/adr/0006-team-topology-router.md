# ADR-0006: Two-layer team topology — root Router (route) over coordinate families
- Status: Accepted
- Date: 2026-06-01

## Context
The platform has two duty families (platform-operation vs platform-development) plus a standalone cloud
cleanup agent. v8 described a single `coordinate` "routing agent"; v8.1 corrected this, and the
reference `agents_factory.py` implements the corrected shape.

## Decision
Top-level **Router uses `mode="route"`** (dispatch a request to exactly one of: Platform Ops team,
Builder team, Cloud Drive Cleanup agent — and return that member's answer). Each **family Team uses
`mode="coordinate"`** (leader delegates + synthesizes). The reference `agents_factory.py` /
`agents_instructions.py` are the **canonical** agent-layer implementation; the skeleton's flat per-agent
modules are superseded. `transcript_miner` is re-added as a standalone agent (serves `/v1/transcripts/mine`).
`agents["router"]` is the AgentOS entry point.

## Consequences
- Stable agent keys preserved (UI/tests depend on them).
- Cross-family requests pick one family (tie-break: prefer Builder); revisit only if common.
- A routing eval (ReliabilityEval) guards against misroute regressions.

## Alternatives considered
- Single coordinate "router" (v8) — rejected: routing is a route-mode decision, not supervision.
