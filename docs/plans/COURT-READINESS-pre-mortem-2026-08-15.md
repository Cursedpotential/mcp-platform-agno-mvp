# Matter Evidence Court-Readiness — Pre-Mortem (2026-08-15)

> _Byline: Codex · GPT-5 · 2026-08-15_

STATUS: COMPLETE LOCALLY — read-only slice; no schema, mutation, deployment, or legal-release action

## Intended outcome

The Matter workspace reports two separate facts for one promoted evidence item:
actual membership in the database's canonical `analysis.vw_court_export`
projection, and whether stricter supplemental readiness checks pass. It reports
content review, exact provenance, H1/custody-event-chain integrity, source
verification, authentication, confidence, hypothesis, redaction, sensitivity,
and release gates without changing any of those states.

## Pre-mortem failures and controls

| Failure | Consequence | Planned control | Residual risk |
|---|---|---|---|
| Supplemental checks are confused with export-view membership | The UI falsely says an item is outside the view | `gates.court_export.view_member` reports actual membership; `readiness_passed` reports the stricter aggregate | A later view change must update the typed explanation contract |
| A valid H1 masks a broken custody-event chain | Evidence appears trustworthy despite chain tampering | Recompute every stored custody-event digest and predecessor link for the exact source; bind verification events to source-wide or exact selected-member scope | The legacy unversioned writer still requires compatibility reconstruction |
| Mutable `review_status` is treated as the reviewer-of-record | Approval appears without append-only human evidence | Require the latest resolved promotion review decision to be `approved` | Reconsideration needs an explicit new-task workflow |
| Low-confidence promotion is silently upgraded | Material enters export without a confidence decision | Report `CONFIDENCE_NOT_EXPORTABLE`; this read side never changes confidence or tier | Confidence policy remains an owner decision |
| Authentication, redaction, or release is inferred | A read endpoint becomes an accidental legal gate | Stable blockers only; no writes; label database readiness as distinct from admissibility/legal advice | Later mutation needs a separate approved state machine |
| Cross-Matter request reveals gate details | Scope leakage confirms another Matter's evidence exists | Reuse exact Matter/provenance joins; missing or mismatched rows return 404 | Deployed authorization still needs live proof |
| Storage paths/private metadata leak | Operator API exposes infrastructure details | Explicit response fields only; never return path, object-store key, or raw metadata | Source display fields remain visible to the authenticated owner |
| Source-level and member-level hashes are conflated | Valid member evidence returns a false failure | Preserve independent source SHA and selected H1; bind by IDs/file-node/source, not digest equality | Mixed legacy canon versions remain visible, not normalized |
| Legacy digest verification amplifies CPU | Repeated readiness reads become slow on large source chains | Search the complete modern civil-offset grid (105 offsets, not every minute), only on explicit per-item readiness reads | Replace the unversioned trigger with a canonical versioned writer/verifier before high-volume use |

## Held decisions

- Authentication and court release as one action or separate decisions.
- Confidence score/tier policy.
- Which authentication methods the MVP may record.
- What proves redaction review.
- Which authenticated principal may authorize court release.

## Validation evidence

- Adversarial review found and closed three correctness defects: export-view/readiness
  conflation, sibling-member verification leakage, and session-timezone-dependent
  digest recomputation.
- Root Ruff lint/format and mypy: **PASS**; root pytest: **743 passed / 24 skipped**.
- Workbench API Ruff lint/format: **PASS**; pytest: **92 passed**.
- Frontend ESLint, TypeScript, and production build: **PASS** with 15 static routes;
  Matter operator browser smoke: **1 passed**.
- PostgreSQL 18.4 disposable rollback proof: **PASS**. It proves sibling-member
  isolation, actual view member/nonmember states, and identical results when the
  reader session switches between UTC and America/New_York. The first execution
  exposed a harness bind-literal defect; that defect was corrected and the proof
  rerun successfully with zero net writes. The server was stopped and port 55439
  is closed.
- Honest limit: the legacy custody digest construction remains unversioned. The
  bounded compatibility verifier is suitable for this explicit operator read,
  not a substitute for a future canonical versioned writer or a high-volume API.
