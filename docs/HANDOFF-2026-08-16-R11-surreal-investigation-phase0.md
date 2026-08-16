# HANDOFF — R11 Surreal Investigation Phase 0 (2026-08-16)

> _Byline: Codex · GPT-5 · 2026-08-16_

STATUS: COMPLETE FOR OWNER REVIEW — contracts/evaluation/test design only
BUILD_STATUS: PASS (synthetic contract suite only; live adapter/deployment proof UNKNOWN)

## Verified starting state

- After `git fetch origin`, `main` equaled `origin/main` at
  `721cbd081ae2d44a65533b14322be4ef3281aaeb`; the worktree was clean.
- All R9 holds were preserved: migrations `0026`–`0030`, canonical-image rehearsal,
  credentials, exact target/deploy authority, live service proof, and Horizon execution.
- The parked legacy Surreal deployment was not contacted or changed.

## Phase-0 artifacts

- `CONTRACTS-2026-08-16-surreal-investigation-phase0.md`
- `UNRESOLVED-QUESTIONS-2026-08-16-surreal-investigation-phase0.md`
- `EVALUATION-2026-08-16-surreal-investigation-phase0.md`
- `PHASE0-PLANTED-FUTURE-FACT-THREAT-TESTS-2026-08-16.md`
- `PENDING-OWNER-DECISIONS-SURREAL-INVESTIGATION-2026-08-16.md`
- `tests/fixtures/surreal_investigation_phase0_horizon.json`
- `tests/test_surreal_investigation_phase0_contract.py`
- Five task-specific pre-mortems under `docs/plans/R10-PHASE0-P0.*`.

## What the contract freezes

- PostgreSQL remains canonical authority; projections are rebuildable and never author truth.
- Extraction, candidate claims, investigations, established facts, agent beliefs, work products,
  and court-safe exports have separate authority and transitions.
- Source/span/chunk/vector/claim/fact identities stay distinct.
- As-lived reads bind one immutable HorizonContext and require pre-ranking/traversal eligibility.
- Partial promotion exposes only approved spans; exact source/custody resolution is mandatory.
- Closed behavioral scope and outward discovery remain separate revisions.

## Validation evidence

- Synthetic future-fact contract suite: 14 passed.
- New test Ruff check and format check: PASS.
- Full repository unit suite after integration: 764 passed / 24 skipped.
- Local Markdown links, JSON parsing, and `git diff --check`: PASS.
- Test explicitly includes future-occurring and old-source/late-realization canaries, top-k
  shrinkage detection, cross-Matter/revoked/candidate denial, and all agent-visible surfaces.
- This is not a live PostgreSQL/Weaviate/Neo4j/Graphiti/Surreal proof.

## Owner gate

Review the compact packet and reply, for example:

`S1–S6 recommended. Keep every R9 activation hold. Defer E1–E5 to measured gates.`

After a ruling, record accepted choices in the decision log/ADRs before any disposable physical
schema or adapter work. Phase 1 remains held until then.

## Prohibited next actions

Do not activate SurrealDB, copy the real corpus, apply migrations, deploy services, replace
Graphiti, bind a production agent, or start production schema implementation. A later isolated
spike must use a new disposable target and separately prove live prefilters/reconciliation.

## Custody

- No files were deleted. Seven overlapping untracked drafts were preserved by moving them to
  `to_be_deleted/phase0-overlapping-drafts-2026-08-16/`; only the owner may delete them.
- No application, database, infrastructure, corpus, or external service changed.
- New artifacts are reviewable documentation plus a synthetic test-only fixture/harness.
