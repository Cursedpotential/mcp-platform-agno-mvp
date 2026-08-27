---
scope: contracts
status: proposed
verified_at: 2026-08-27
superseded_by: null
authority:
  - AGENTS.md
  - docs/PROJECT_CANON.md
  - docs/reviews/2026-08-25-schema-audit/CROSS-DOMAIN-CONTRACT-MATRIX.md
watches:
  - "contracts/**/*.json"
  - "contracts/**/*.yaml"
  - "contracts/**/*.yml"
contains_secrets: false
---

# Cross-Language Contract Memory

> _Byline: Codex · GPT-5 · 2026-08-27._

**Freshness hold:** the contract sources in this scope are not tracked yet, so `0000000` is a
visible hold rather than a current-verification claim. Reverify and restamp this memory when the
owning contract implementation commit lands.

- Contracts define the same destination, shape, lineage, accounting, and workflow semantics for all
  parser languages and transports.
- Version public payloads and preserve compatibility deliberately; do not let an adapter framework
  own the contract.
- Workflow payloads carry references, not evidence bodies. Raw and normalized identities remain
  traceable through explicit lineage.
- A parser contract covers parsing only. Hash, storage, normalization, comparison, and governance
  are separate stage contracts.

<!-- freshness
watches_hash: 0000000
last_verified: 2026-08-27
watches:
  - contracts/**/*.json
  - contracts/**/*.yaml
  - contracts/**/*.yml
-->
