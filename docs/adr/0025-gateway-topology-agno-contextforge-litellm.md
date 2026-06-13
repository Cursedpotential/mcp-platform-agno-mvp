# ADR-0025: Platform topology — Agno core, IBM ContextForge tool gateway, LiteLLM model gateway
- Status: Accepted
- Date: 2026-06-13
- _Byline: Claude Code · Opus 4.8 · 2026-06-13_

## Context
Earlier framing had an "Agno-native gateway, IBM ContextForge as fallback." Owner refined this (2026-06-13):
switch the **tool gateway to IBM ContextForge** off-the-shelf and **minimize custom code** (custom only for
situation-specific logic). The prior AI-DIAL attempt (`dev-resources/Archives/dial-stack`) is a parts/pattern
donor only — its DIAL runtime is dropped.

## Decision
- **Agno = orchestration core** (agents/teams/workflows runtime + native control-plane/chat UIs + multi-surface
  interfaces AG-UI/A2A/REST). Not DIAL. We do NOT rebuild what Agno provides.
- **IBM ContextForge (`IBM/mcp-context-forge`) = the MCP TOOL gateway** — serves/federates MCP tools (and
  REST APIs wrapped as MCP, ADR-0023) to any consumer: Agno agents, remote LLMs, in-stack local-model runners.
- **LiteLLM = the MODEL gateway** (`gateway` container) — routes all models, remote + in-stack (Ollama Cloud
  primary). **Distinct layer from the tool gateway** — do not conflate (clarifies ADR-0015).
- **Minimize custom code:** off-the-shelf open-source by default; custom only for evidence custody/bitemporal
  logic, MCL/legal analysis, the owner's parsers/taxonomy.
- **VIPs (never overwrite, integrate around):** Agno (+ native UIs), custom Graphiti, Semantica, IBM
  ContextForge, forked SBV, CopilotKit. **Keep:** LiteLLM, OpenCode, agent-sandbox, persistent Kasm.

## Consequences
- Supersedes-in-part the prior gateway framing; reinforces ADR-0017 (polyglot mesh) and pairs with ADR-0023
  (universal API+MCP exposure).
- ContextForge becomes a stack dependency (stand up in Phase C); a raw local model consumes tools only via an
  MCP-capable harness (Agno/OpenCode/MCP client), never directly.

## Alternatives considered
- Custom Agno-native tool gateway — rejected (against minimize-custom; ContextForge is off-the-shelf).
- DIAL — dropped (abandoned attempt; donor only).
