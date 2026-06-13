# ADR-0017: Evidence processing = polyglot orchestration mesh (custody → workflows → atomic tools)
- Status: Accepted
- Date: 2026-06-11

## Context
Evidence comes in many formats, sizes, and streaming shapes; different languages/libraries are
ideal for different ones. The owner deliberately did not pick one language. We need a *completed
system* that parsers/tools plug into — not one-off ports — with graceful recovery when a tool fails.

## Decision
The evidence layer is a **polyglot orchestration mesh** (Python core in `evidence/`, tools any
language):
1. **Universal custody gate** (`evidence/custody.py`) — every artifact enters via sha256 →
   `evidence.evidence_hash` (BYTEA) + raw blob to R2 (write-once). The immutable root.
2. **Named workflows A/B/C per evidence type** (`evidence/workflows.py`) — the ideal happy path
   per type, an ordered list of capability-steps resolved to best-fit tools.
3. **Atomic tools** (`evidence/registry.py`) — each wraps one library in one language with a clean
   contract (`id`, `capability`, `accepts(type,size)`, `run`), registered and discoverable
   (via MCP / HTTP / CLI manifest).
4. **Agent re-composition on failure** — when a workflow step fails, the agent queries the registry
   for same-capability alternatives and reassembles; ad-hoc assembly runs in the sandbox (ADR-0016).
All writes pass the HITL gate (ADR-0002/0019).

## Consequences
- Adding a parser/tool = implementing the `ToolPlugin` contract + registering, not rewiring.
- Existing TS/Py/JS MCP servers (`dev-resources/.../mcp-servers`) attach as atomic-tool sources.
- The `tools-facade` is populated from the registry (no more empty `PORTED={}`).
- SBV is the first real plug-in (Workflow A = SMS-XML), proving the vertical.

## Alternatives considered
- Single-language spine — rejected: no one language is best across all evidence types/sizes/streaming.
- One-off parser ports — rejected: doesn't compose, no recovery path, doesn't scale to many sources.
