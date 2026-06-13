# ADR-0001: Build fresh from the Agno skeleton; abandon the v1 repo
- Status: Accepted
- Date: 2026-06-01

## Context
The original `Agno-MCP-Platform/` repo is a v1-era implementation — exactly the patterns the v8.1
handoff's "Corrections From v1" section exists to replace (manual FastAPI instead of AgentOS, a
hand-rolled approval table + `store_learned_knowledge`, raw MCPTools, stale `gpt-4o` defaults), plus
import-level bugs (`chatminer.core.pipeline` missing, broken root `parsers/`, `EVIDENCE_REFERENCE`
not in enum). A clean, runnable Agno AgentOS template already exists at
`dev-resources/upstream-resources/agno-agent-platform`.

## Decision
Build the MVP fresh in a new sibling project `agno-mvp/`, seeded from that clean skeleton. The v1
repo is **abandoned** — not fixed, not built on. Only genuinely valuable, isolated assets are ported
(the ChatMiner parsers, after review). `dev-resources/` is reference + a parts bin only.

## Consequences
- No time spent untangling v1; we start on the proven template.
- Each ported asset must be reviewed before trust (it carried bugs).
- `dev-resources/` stays read-only reference; never revive an iteration wholesale.

## Alternatives considered
- In-place refactor of the v1 repo — rejected: replacing the core (AgentOS, LearningMachine, providers,
  schema) is a rewrite anyway, with contamination risk.
