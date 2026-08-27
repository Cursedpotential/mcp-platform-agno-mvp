---
scope: server/evidence
status: current
verified_at: 2026-08-27
superseded_by: null
authority:
  - server/evidence/AGENTS.md
  - docs/reference/CUSTODY-HASH-CANON.md
  - docs/adr/0044-evidence-context-boundary-and-transcript-model.md
watches:
  - server/evidence/**
  - docs/reference/CUSTODY-HASH-CANON.md
contains_secrets: false
---

# Evidence Spine Memory

> _Byline: Codex · GPT-5 · 2026-08-27._

- AI chat is context, never evidence. Events and claims extracted from chats are candidates that
  drive searches for independent evidence; they do not inherit evidentiary status from the chat.
- Raw extraction preserves every available byte and extractable source metadata, including file
  timestamps and media metadata. Normalized records link back to the raw records used.
- Legal-document, filing, brief, strategy, concern, and observation candidates extracted from chats
  remain governed candidates until reviewed.
- Redaction is on-demand during court-document preparation, not a default ingestion transform.
- `custody.py` remains the sole evidence-schema writer. Exact-file memory:
  `.agent-memory/custody.py.md`.

<!-- freshness
watches_hash: f8f8e5b
last_verified: 2026-08-27
watches:
  - server/evidence/**/*.py
  - server/evidence/AGENTS.md
  - docs/reference/CUSTODY-HASH-CANON.md
-->
