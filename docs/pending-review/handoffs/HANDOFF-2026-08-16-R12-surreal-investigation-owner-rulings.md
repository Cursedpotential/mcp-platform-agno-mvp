# HANDOFF — R12 Surreal Investigation Owner Rulings (2026-08-16)

> _Byline: Codex · GPT-5 · 2026-08-16_

STATUS: OWNER RULINGS ACCEPTED; DOCUMENTATION SYNCHRONIZED
BUILD_STATUS: FRAMEWORK-NEUTRAL CONTRACT TESTS PASS; LIVE ADAPTER/DEPLOYMENT PROOF UNKNOWN

## Owner decisions

- **S1 A:** after parity, the as-lived walk retrieves evidence/memory only through reconciled
  Surreal; PostgreSQL remains canonical control/approval authority and there is no broad fallback.
- **S2 B:** one shared Surreal Context per product/environment, with Matter scopes, first-class
  walk/step records, and walk-bound experiential state; promoted knowledge is not copied per walk.
- **S3 A amended:** failure pauses and seals an immutable historical snapshot; reconciliation
  creates a new linked rewalk and preserves the experiential before/after delta.
- **S4 A:** walk-generated candidate beliefs are permitted only from horizon-eligible inputs and
  remain explicitly uncertain.
- **S5 C amended:** preserve the uncertainty interval, propose its midpoint, require HITL
  clarification, and withhold the estimate from as-lived retrieval until approval.
- **S6 A:** derivative copies count as one source family unless provenance review establishes
  independent observation or creation; report raw hits separately.

D-064 records the combined ruling. ADR-0056 and ADR-0057 carry the refinements; ADR-0058 remains
unchanged.

## Validation evidence

- Focused framework-neutral contract suite: **18 passed**.
- Focused Ruff and format gates: **PASS**.
- Full repository unit suite: **768 passed / 24 skipped**.
- Full Ruff, format, and mypy gates: **PASS**.
- Markdown links, JSON parse, decision/status drift, activation-hold anchors, and task diff check:
  **PASS**.
- No live service, database, corpus, migration, deployment, or production agent was contacted or
  changed.

## Authorization boundary

Disposable Phase-1 design may now be refined. This ruling does **not** authorize target creation,
physical/production schema implementation, Surreal activation, corpus copy, migration application,
service deployment, production-agent binding, Graphiti replacement, or E1–E5 adoption.

Every R9 hold remains active: migrations `0026`–`0030`, canonical-image rehearsal, credentials,
exact target/deployment authority, live store proof, and Horizon execution.

## Workspace custody note

During final validation, an unrelated concurrent change appeared in `workbench/api/main.py` that
comments out API authentication for local development. It was not present at task start, is not
part of D-064, and is intentionally excluded from this documentation/contract-test commit. Do not
discard or commit it without determining its owner and security intent.

## Next task

Prepare the isolated disposable Phase-1 slice design and its pre-mortem. Before any physical work,
name the disposable target, prove it is not the parked legacy deployment, and obtain the separately
required target/credential/implementation authority.
