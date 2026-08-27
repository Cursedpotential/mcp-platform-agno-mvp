---
scope: server/analysis
status: current
verified_at: 2026-08-27
superseded_by: null
authority:
  - docs/PROJECT_CANON.md
  - docs/design/0062-satemporal-semantica-ab/
watches:
  - "server/analysis/**/*.py"
  - docs/design/0062-satemporal-semantica-ab/**
contains_secrets: false
---

# Analysis Memory

> _Byline: Codex · GPT-5 · 2026-08-27._

- Analysis output is derived and governed; it never rewrites raw or canonical evidence.
- Run SAT temporal GraphRAG and Semantica side by side with versioned manifests and comparable
  evaluation receipts. Neither silently replaces the other.
- SurrealDB remains the final reconciled temporal-graph/walk analysis target; Neo4j and Weaviate
  serve their governed roles and remain rebuildable from canonical PostgreSQL state.
- Claims, events, legal artifacts, strategies, concerns, and observations extracted from AI chats
  remain candidates until reviewed and independently supported.
- Model confidence or semantic similarity is not court-safe verification.

<!-- freshness
watches_hash: 2332a4d
last_verified: 2026-08-27
watches:
  - server/analysis/**/*.py
  - docs/design/0062-satemporal-semantica-ab/**
-->
