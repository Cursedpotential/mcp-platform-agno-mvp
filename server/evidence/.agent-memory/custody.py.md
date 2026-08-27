---
scope: server/evidence/custody.py
status: current
verified_at: 2026-08-27
superseded_by: null
authority:
  - server/evidence/AGENTS.md
  - docs/reference/CUSTODY-HASH-CANON.md
  - docs/adr/0034-multilevel-custody-hashing.md
watches:
  - server/evidence/custody.py
  - docs/reference/CUSTODY-HASH-CANON.md
contains_secrets: false
---

# `custody.py` Memory

> _Byline: Codex · GPT-5 · 2026-08-27._

- This file is the single evidence-schema write gate: hash, deduplicate, write the immutable source,
  and append custody state before normalization.
- Do not collapse the SBV chain and Case Bible chain into one recipe. They are both valid but use
  different constructions and require distinct canon tags; follow `CUSTODY-HASH-CANON.md` exactly.
- Hashing, parsing, normalization, and verification remain distinct Activity responsibilities even
  when this module composes their results at the evidence boundary.
- Never infer a completed custody guarantee from a parser success alone.

<!-- freshness
watches_hash: 9764925
last_verified: 2026-08-27
watches:
  - server/evidence/custody.py
  - docs/reference/CUSTODY-HASH-CANON.md
  - docs/adr/0034-multilevel-custody-hashing.md
-->
