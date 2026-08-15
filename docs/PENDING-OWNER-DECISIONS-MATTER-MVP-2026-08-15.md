# Pending Owner Decisions — Matter MVP (2026-08-15)

> _Byline: Codex · GPT-5 · 2026-08-15_

STATUS: PENDING OWNER RULING — review packet only; not an ADR and not implementation authority

These decisions are the remaining boundary between the verified local
Knowledge-to-case workflow and the next schema/release mutations. Reply with
the compact choices (for example, `P1 recommended; P2 recommended; …`). After
approval, the accepted choices must be recorded in an ADR/decision log before
their schema or mutation is built.

## A. Matter People and canonical Timeline

### P1 — People authority

**Recommended:** `analysis.matter_person` is an operator-authored, Matter-local
case profile. `working.person` remains rebuildable extraction output; a later
derived resolver may point from `working.*` to the authored profile.

**Alternative:** require every Matter person to reference `working.person`.

**Consequence:** the alternative makes human-curated case identity depend on a
row that extraction may rebuild, merge, or delete. The recommendation preserves
operator corrections and allows People to exist before extraction resolves them.

### P2 — Review meaning for an operator-created person

**Recommended:** usable for internal organization immediately, but
`safe_for_legal_use=false` until explicit identity/foundation review.

**Alternative:** creation itself counts as approved identity.

**Consequence:** automatic approval is faster but can turn an uncorroborated
name/role into court-facing identity without a separate foundation decision.

### P3 — Role cardinality

**Recommended:** one optional `primary_role` and `relationship_label` as open
text for the MVP; add normalized multiple-role rows only after real use proves
the need.

**Alternative:** create a many-role table now.

**Consequence:** the normalized alternative is flexible but freezes speculative
vocabulary and expands the first migration/API/UI slice.

### P4 — Court-specific timeline membership

**Recommended:** canonical facts remain in the one authored
`analysis.timeline_event`; an explicit many-to-many
`analysis.court_case_event_scope` projects an event into one or more proceedings.

**Alternative:** every Matter event automatically appears in every CourtCase.

**Consequence:** automatic inclusion is simpler but cannot express relevance or
an attributable inclusion decision. A single `court_case_id` on the event is
not offered because it contradicts ADR-0055 and prevents multi-proceeding use.

### P5 — Same-human identity across Matters

**Recommended:** allow separate Matter-local profiles and never deduplicate by
name; defer a global canonical-person authority.

**Alternative:** introduce a global authored person registry now.

**Consequence:** the global registry may eventually help cross-Matter identity,
but it creates a new identity-resolution system before the single-Matter MVP
needs one.

## B. Evidence authentication and court release

### R1 — Combined or separate decisions

**Recommended:** authentication and court release are distinct decisions. One
future endpoint may coordinate them atomically only if both decisions and their
evidence are explicit.

**Alternative:** one “make court ready” action sets both.

**Consequence:** a combined action is convenient but hides whether the operator
authenticated the source, approved the content, or merely authorized export.

### R2 — Confidence policy

**Recommended:** never auto-upgrade a promoted item's default-low confidence.
Require an explicit attributable confidence decision, and make numeric/tier
consistency a database invariant before release.

**Alternative:** derive medium/high automatically from parser or model scores.

**Consequence:** automatic promotion lets model/extraction confidence become a
legal-release decision without human foundation review.

### R3 — Authentication methods in the first mutation

**Recommended:** support only mechanically verifiable
`hash_chain_of_custody` initially. Add testimony/business-record/other methods
only when their foundation records and tests exist.

**Alternative:** expose every existing authentication label immediately.

**Consequence:** broad labels without corresponding foundation data create
status theater rather than defensible authentication.

### R4 — Redaction meaning

**Recommended:** item and source privacy both `none` may satisfy the diagnostic
readiness gate, but a release decision must explicitly affirm that no redaction
is required. `redaction_status=none` alone is not evidence that someone reviewed
the issue.

**Alternative:** treat the default `none` value as an affirmative review.

**Consequence:** the alternative silently converts a default into a human
privacy/redaction decision.

### R5 — Who may release

**Recommended:** the single authenticated owner may curate/review internally,
but court release requires re-authenticated, attributable confirmation (and
eventually a signing context), not possession of the shared spine bearer alone.

**Alternative:** any valid Workbench owner session may release immediately.

**Consequence:** the alternative is simpler but gives a long-lived shared secret
the meaning of a court-export signature.

### R6 — Custody `released` versus legal release

**Recommended:** keep source custody status/events independent from evidence
court release. Marking an evidence item court-releasable must not automatically
append a source `released` custody event or change the source custody status.

**Alternative:** couple both transitions.

**Consequence:** coupling confuses movement/control of source material with the
legal decision to include one derived evidence item in an export.

## C. Activation authority

The following are operational approvals, not architecture decisions:

1. **A1 — Disposable canonical-image rehearsal:** approve running baseline plus
   migrations 0026–0030 inside a new disposable instance of the tracked custom
   PostgreSQL 18 image. No shared database.
2. **A2 — Target apply:** after A1 passes, name and approve the exact database
   target for the reviewed 0026–0030 apply. Until then every migration remains
   held.
3. **A3 — Credentials:** provision distinct `WORKBENCH_API_KEY` and
   `AGENTOS_API_TOKEN` values in the deployment environment; never place them in
   git or the preflight command line.
4. **A4 — Deploy/live proof:** approve the exact Workbench deployment and the
   read-only activation preflight against Matter, case-prefiltered Knowledge,
   Graphiti namespace, spine, and Weaviate endpoints.

## Recommended compact ruling

`P1–P5 recommended; R1–R6 recommended; A1 approved; A2–A4 remain held until the A1 report.`

