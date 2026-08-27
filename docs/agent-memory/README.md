---
scope: repository
status: current
verified_at: 2026-08-27
superseded_by: null
authority:
  - AGENTS.md
  - docs/MEMORY_ARCHITECTURE.md
  - docs/CONVENTIONS.md
watches:
  - "**/AGENTS.md"
  - "**/AGENT_MEMORY.md"
  - "**/.agent-memory/*.md"
contains_secrets: false
---

# Progressive Agent Memory Contract

> _Byline: Codex · GPT-5 · 2026-08-27._

## Purpose

Give agents only the durable local context needed for the path they are touching. This is a
progressively disclosed view of existing project truth, not another independent memory system.

## Load order

1. Read `AGENTS.md` from repository root to the closest applicable directory.
2. Read `AGENT_MEMORY.md` from repository root to that same directory when present.
3. For an exact target file, read the adjacent `.agent-memory/<filename>.md` when present.
4. Follow linked canon, ADRs, decisions, handoffs, or verification receipts before relying on a
   claim that affects architecture, data, security, deployment, or completion status.

## Authority order

1. Newest explicit owner ruling.
2. Current canon, signed ADRs, and `docs/DECISION_LOG.md`.
3. Current indexed handoff or live verification receipt within its stated validation boundary.
4. Applicable `AGENTS.md` rules.
5. `AGENT_MEMORY.md` and exact-file memory.

More-specific memory narrows context; it never overrules higher authority. When a memory becomes
a governed decision, promote it to the decision log, ADR, canon, or handoff and replace local prose
with a pointer.

## Names and placement

```text
AGENTS.md                         enforceable path rules and navigation
AGENT_MEMORY.md                   directory-scoped sourced memory and child router
.agent-memory/<filename>.md       exact-file memory, loaded only for that file
README.md                         directory contents and ordinary human navigation
<source-file> docstring           authoritative behavior of that source file
```

The `AGENT_MEMORY.md` name is deliberate. Plain `MEMORY.md` is already used by external
auto-memory indexes; `.remember/` and `.claude/memories/` are generated runtime lanes.

## Required metadata

Every memory file starts with:

```yaml
---
scope: exact/repository/path
status: current # current | proposed | historical | superseded
verified_at: YYYY-MM-DD
superseded_by: null
authority:
  - docs/path-to-current-source.md
watches:
  - exact/path/**
contains_secrets: false
---
```

Every material claim must be labeled or written clearly as one of:

- `Owner directive` — explicit owner preference or ruling.
- `Verified` — confirmed against current files, tests, or live state with a linked receipt.
- `Inferred` — useful interpretation that is not yet governed truth.
- `Historical` — context retained only to explain why the current rule exists.

## Store here

- Durable directory conventions and owner preferences.
- Local failure modes that repeatedly cause incorrect edits.
- Precise pointers to current authority and verification.
- File-specific rationale that does not belong in the source docstring.
- Supersession history needed to prevent a known stale instruction from returning.

## Never store here

- Passwords, tokens, credentials, PII, evidence bodies, or raw conversations.
- Ephemeral task progress, agent status, temporary branch state, or unsourced completion claims.
- Copies of full ADRs, canon sections, schemas, handoffs, or test output.
- A proposed architecture presented as current.

Temporary work belongs in a TODO or handoff. Material verification belongs in a dated receipt.
Historical or superseded memory remains visible with status metadata; it is not deleted.

## Maintenance

- Add a memory file only when durable local context exists; never blanket-create empty files.
- Update `verified_at` only after re-reading every listed authority and watched path in scope.
- If sources conflict, mark the memory `proposed` or `historical`, link both sources, and escalate.
- Preserve history through `superseded_by`; never hard-delete memory.

<!-- freshness
watches_hash: 0e911a3
last_verified: 2026-08-27
watches:
  - AGENTS.md
  - docs/MEMORY_ARCHITECTURE.md
  - docs/CONVENTIONS.md
-->
