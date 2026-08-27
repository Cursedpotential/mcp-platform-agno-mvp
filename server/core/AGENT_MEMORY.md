---
scope: server/core
status: current
verified_at: 2026-08-27
superseded_by: null
authority:
  - server/AGENTS.md
  - AGENTS.md
watches:
  - "server/core/**/*.py"
  - server/AGENTS.md
contains_secrets: false
---

# Core Runtime Memory

> _Byline: Codex · GPT-5 · 2026-08-27._

- Core owns configuration, database/session construction, provider selection, embedding, reranking,
  and neutral runtime helpers. It must not import outward domain layers.
- PostgreSQL is canonical. Use the configured application role for runtime and reserve superuser
  access for the owner/developer operations path.
- Remote model and retrieval providers only on this machine; do not restore ONNX or local model
  inference.
- Never print or persist secrets. Resolve settings through the configured secret/runtime layer.
- Current database targets and role cutovers are deployment facts that require live verification,
  not assumptions from default settings.

<!-- freshness
watches_hash: fbb7446
last_verified: 2026-08-27
watches:
  - server/core/**/*.py
  - server/AGENTS.md
-->
