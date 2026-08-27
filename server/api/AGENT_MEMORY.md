---
scope: server/api
status: current
verified_at: 2026-08-27
superseded_by: null
authority:
  - server/AGENTS.md
  - docs/PROJECT_CANON.md
watches:
  - "server/api/**/*.py"
  - server/AGENTS.md
contains_secrets: false
---

# API Memory

> _Byline: Codex · GPT-5 · 2026-08-27._

- HTTP routes expose platform-owned contracts; the Agno/AgentOS mounting layer is an adapter under
  replacement, not the authority or public vocabulary.
- Route handlers remain thin and call application/domain services. They do not bypass custody,
  approval, lineage, or PostgreSQL receipts.
- All capabilities need complete API coverage before MCP wrapping; a mounted placeholder is not
  coverage.
- Authentication and authorization must be externally rotatable where possible and must not rely on
  UI labels or Tailscale alone for write authority.
- Stream run progress from durable run-event state; do not manufacture progress in the browser.

<!-- freshness
watches_hash: 45dc10e
last_verified: 2026-08-27
watches:
  - server/api/**/*.py
  - server/AGENTS.md
-->
