---
scope: tests
status: current
verified_at: 2026-08-27
superseded_by: null
authority:
  - AGENTS.md
  - docs/CONVENTIONS.md
watches:
  - "tests/**/*.py"
  - AGENTS.md
contains_secrets: false
---

# Test Memory

> _Byline: Codex · GPT-5 · 2026-08-27._

- Tests describe the load-bearing contract: success shape, failure behavior, ordering, lineage,
  authority boundaries, and fail-closed behavior.
- Use `uv run` for Python checks. A unit test is a fast validation layer, not production proof.
- Live integration tests are required before calling an integrated capability done, but only a
  dated receipt proves the exact environment and interaction that was exercised.
- Root and legacy Workbench test suites may have conflicting `tests.conftest` packages; run them in
  their documented boundaries instead of interpreting import collisions as product failures.
- Test fixtures and design ingests are disposable. Never allow test data to become canonical.

<!-- freshness
watches_hash: fe097f0
last_verified: 2026-08-27
watches:
  - tests/**/*.py
  - AGENTS.md
-->
