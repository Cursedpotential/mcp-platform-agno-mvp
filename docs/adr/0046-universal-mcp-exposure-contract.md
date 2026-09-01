# ADR-0046 — Universal MCP exposure contract (progressive disclosure + horizon binding)

> _Byline: Claude (Cowork) · Fable 5 · 2026-08-09_

- **Status:** **Accepted** (owner signed 2026-08-09; recorded as D-042)
- **Context sources:** PROJECT_CANON §5 item "Universal exposure … needs ADR" (locked 2026-06-13,
  never ratified); ADR-0016 (consolidated tool containers), ADR-0023 (universal API/MCP
  exposure), ADR-0035 (tools subnamespacing); 2026-08-09 audit finding M-1 (MCP doors are an
  unbound read lane); ADR-0045 (HorizonContext).

## Context

The platform exposes everything API-first and MCP-wrapped: the AgentOS MCP door
(`server/api/mcp_main.py`), ContextForge as the tool gateway (14 SBV facade tools, Graphiti
virtual server per ADR-0037), and the progressive-disclosure quad in `server/tools/gateway/`.
Canon locked the pattern in 2026-06 but flagged it "needs ADR." Meanwhile the horizon work
(ADR-0045) makes every MCP door a fifth read lane: any evidence-reading tool invocable by an MCP
client with no horizon binding is a bypass of the platform's core invariant.

## Decision

1. **Progressive disclosure is the contract:** `search_tools → describe_tool → invoke_tool →
   get_ref`. Everything atomically addressable; no client needs the full catalog up front.
2. **Naming:** subnamespaced, action-oriented ids per ADR-0035 (`messages.sms-xml-sbv`,
   `graphiti.search-facts`). Consistent prefixes per service.
3. **Annotations are mandatory** on every exposed tool: `readOnlyHint`, `destructiveHint`,
   `idempotentHint`. HITL-first (ADR-0002) requires destructive tools to be VISIBLY destructive
   to every client.
4. **Pagination is mandatory** on any tool that can return evidence rows; unbounded evidence
   reads are both a context hazard and an audit hazard.
5. **Errors are actionable:** every error names the failing precondition and the next step
   (the `SBVError` style is the house standard).
6. **Horizon binding (the load-bearing rule):** evidence-reading MCP tools resolve their
   HorizonContext SERVER-SIDE from a `pass_id`/context registry. They NEVER accept a raw
   client-supplied horizon timestamp — an agent that can pass its own horizon has no horizon.
   Hindsight access is an explicit server-side grant bound to the credential, never a parameter.
   Fail-closed: unresolvable context → zero rows + an explicit error, and the attempt is written
   to `ops.audit_ledger` (ADR-0047).
7. **Every MCP invocation is audited** (tool id, argument hash, context ref) per ADR-0047.

## Consequences

- S6 task 8 implements rule 6 on `mcp_main.py` + gateway `invoke_tool`; S7 task 6 grooms the
  existing facade tools to rules 3–5.
- New tools are born compliant: the contract is part of tool review, checked alongside the
  registry metadata (priority/quality_tier — S7).
- GUI/desktop clients (LibreChat, OpenCode, Kasm) keep full capability through ContextForge;
  they simply cannot read evidence outside a server-resolved horizon.

## Alternatives considered

- **Client-supplied horizon parameters** — rejected: indistinguishable from agentic horizon
  selection; defeats the invariant.
- **A separate "trusted" MCP door without binding** — rejected: contamination is silent; a
  trusted unbound door is just a leak with a nicer name. Hindsight-by-credential-grant covers
  the legitimate need.
- **Workflow-tools-only surface (no atomic coverage)** — rejected: canon locked universal
  atomic addressability (ADR-0023); workflow tools compose on top, they don't replace coverage.
