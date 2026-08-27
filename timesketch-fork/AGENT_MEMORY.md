---
scope: timesketch-fork
status: current
verified_at: 2026-08-27
superseded_by: null
authority:
  - AGENTS.md
  - docs/reviews/2026-08-25-schema-audit/TIMESKETCH-FORK-WP-E01-HANDOFF.md
  - docs/reviews/2026-08-25-schema-audit/TIMESKETCH-FORK-CURATION-HANDOFF.md
watches:
  - timesketch-fork/**
contains_secrets: false
---

# Timesketch Fork Memory

> _Byline: Codex · GPT-5 · 2026-08-27._

- PostgreSQL remains canonical. Timesketch is a view, annotation, filtering, and bulk-curation
  surface over governed timeline projections.
- Approved evidence timelines may be visible. User annotations or modifications returning from the
  fork become candidates with provenance and must be reconciled and re-reviewed before canonical use.
- Timeline extraction may originate from any supported context, but each normalized event must retain
  lineage to its raw source and source metadata.
- Preserve useful upstream Timesketch behavior while isolating product-specific changes in the fork.
- A rendered upstream page is not integrated proof. Verify projection import, annotation return,
  candidate creation, and re-review receipts end to end.

<!-- freshness
watches_hash: de82877
last_verified: 2026-08-27
watches:
  - timesketch-fork/**/*.py
  - timesketch-fork/**/*.js
  - timesketch-fork/**/*.ts
  - timesketch-fork/README.md
-->
