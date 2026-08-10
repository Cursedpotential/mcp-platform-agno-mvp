# Owner Rulings Sheet — 2026-08-09 — ALL RESOLVED
> Answered via structured Q&A same day; recorded as D-042 in docs/DECISION_LOG.md.

| # | Item | Ruling |
|---|------|--------|
| 1 | ADR-0045 (horizon clocks + derivation) | **SIGNED — Option A + A.4 amendment** (realization_event table; contradiction events = lie register; algorithm proposes, owner batch-approves). S6 UNBLOCKED. |
| 2 | ADR-0046 (MCP exposure contract) | **SIGNED** |
| 3 | ADR-0047 (audit-everything ledger) | **SIGNED** |
| 4 | D-008 (RESTART-0001 evidence schema) | **SIGNED as drafted** — S9 population unblocked. |
| 5 | OQ-8 (who emits hindsight/discovered) | **HITL-only + one exception**: AI-chat context lane auto-asserts `hindsight` at write. |
| 6 | OQ-10 (Milvus cutover) | **Verified** → pymilvus dropped from Dockerfile (D-042). |
| 7 | OQ-9 (Phase 5a) | Checked: **SHIPPED** — fork main == v0.2.4-forensic tag, image pinned in docker/tools/Dockerfile. Residual: confirm heic tag state in v0.2.4. |
| 8 | OQ-7 (surql file) | Checked: design already absorbed by ADR-0045/S6 → **archived to _stale/**, database/ dir retired. |
| 9 | OQ-2 (extracted-code location) | **RESOLVED**: found at `Projects\the-platform-workspace\extracted-code\` (repo sibling, one level up), `extracted-code.zip` backup beside it. Canon §9 + REPO_STRUCTURE repointed; all TODO markers cleared. |
