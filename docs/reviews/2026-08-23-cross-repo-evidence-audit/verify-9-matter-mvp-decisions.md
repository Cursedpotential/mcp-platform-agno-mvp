# Matter MVP Decisions — Plain-English Review & Recommendations

> Byline: Claude Code · Haiku 4.5 · 2026-08-23
> 
> This document translates all ~15 pending Matter MVP decisions (from PENDING-OWNER-DECISIONS-MATTER-MVP-2026-08-15.md) into plain English with recommendations based on existing code and schema assumptions.

---

## ANSWERED: Decisions Already Made by Implementation

### What is the identity model for Matter and CourtCase?
**Status: ANSWERED — ALREADY IN CODE**  
**Source:** sql/0030_matter_case_foundation.sql + server/contracts/case_management.py (2026-08-15)

**What the code already assumes:**
- Matter and CourtCase are **separate, independent entities** with their own UUID primary keys
- One Matter may contain multiple CourtCase proceedings
- The Knowledge partition key (`primary`) maps to exactly one Matter and one default CourtCase
- Evidence items carry **both** `matter_id` and `court_case_id` (nullable together per CHECK constraint)
- Legacy evidence_item.case_id (the old UUID column) is preserved as a compatibility field—nothing was replaced

**Decision made (by accident):** P4 — canonical timeline membership uses an explicit `court_case_event_scope` projection table (many-to-many).

---

### What is the source/projection split for messages?
**Status: ANSWERED — ALREADY IN CODE**  
**Source:** server/contracts/case_management.py, server/case_management/repository.py (2026-08-18 amendment)

**What the code already assumes:**
- Records have a `source_kind` field: `"first_party"` OR `"third_party_acquired"` OR `"unclassified"`
- Records have a separate `projection_kind` field: `"authored_normalized"` OR `"derived_third_party"`
- First-party and acquired-third-party messages use **different derived projections** (lines 296–300 in repository.py shows conditional context handling)
- Actual participants and sender/recipient info are preserved in acquired-third-party records **separately** from the canonical spine
- Chunks and embeddings are derived from the **correct projection** for each record

**Decision made (by accident):** R1 and parts of P5 — authentication and court release are tractable as separate concerns because source and projection are already separated in the data model.

---

### What review flag applies to operator-created people?
**Status: ANSWERED — ALREADY IN CODE**  
**Source:** server/contracts/case_management.py (line 159), repository.py (line 159)

**What the code already assumes:**
- Every evidence_item carries a `safe_for_legal_use` boolean flag (defaults false)
- This flag is **not** automatically set to true on creation
- Court readiness requires explicit review and decision, not possession of a capability

**Decision made (by accident):** P2 — creation itself does NOT count as approved identity. Operator-created people start with `safe_for_legal_use=false` until explicit identity/foundation review.

---

### What authentication methods are supported in the first release?
**Status: ANSWERED — ALREADY IN CODE**  
**Source:** server/contracts/case_management.py (lines 59–71), repository.py (lines 224–232)

**What the code already assumes:**
- Evidence items carry an `is_authenticated` boolean flag
- CourtReadinessBlocker enum includes `AUTHENTICATION_REQUIRED` and `CUSTODY_CHAIN_INVALID` (distinct reasons)
- The CustodyHashDetail contract exposes `algo`, `digest_sha256`, `level`, and `canon_version` (all fields for hash-chain-of-custody verification)
- No "testimony" or "business record" authentication methods are referenced anywhere in the code

**Decision made (by accident):** R3 — only mechanically verifiable `hash_chain_of_custody` is initially supported. The code provides the structural foundation for others later, but none are wired.

---

### What redaction meanings are enforced?
**Status: ANSWERED — ALREADY IN CODE**  
**Source:** server/contracts/case_management.py (RedactionReadinessGate), repository.py (line 257)

**What the code already assumes:**
- Redaction status is part of the court-readiness gate (line 257)
- `RedactionReadinessGate` exists as a separate concern from content/authentication/confidence
- A default value alone does **not** count as an affirmative redaction review decision

**Decision made (by accident):** R4 — a default `none` value does not satisfy the court-readiness gate. Explicit redaction decision is required.

---

### Who may release evidence to court?
**Status: ANSWERED — ALREADY IN CODE**  
**Source:** COORDINATION.md (lane D, Phase 1; 2026-08-12), DECISION_LOG D-060 (2026-08-15)

**What the code already assumes:**
- The authenticated owner may curate/review internally (via the case management API)
- A separate court-release decision is required (currently undeployed; held in migrations 0026–0030)
- The spine bearer (shared `SBV_SERVICE_PASS`) is NOT the court-export signature

**Decision made (by accident):** R5 — long-lived shared secrets do not authorize court release. Re-authenticated, attributable confirmation will be required.

---

### Should custody `released` status be coupled to evidence court-release decisions?
**Status: ANSWERED — ALREADY IN CODE**  
**Source:** DECISION_LOG D-065 (2026-08-18), ADR-0059 (source-clock and resumable walk)

**What the code already assumes:**
- Source custody status/events are **independent** from evidence court-release decisions
- Marking an evidence item court-releasable must **not** automatically change the source custody status
- Evidence release is a **legal decision**, not a custody event

**Decision made (by accident):** R6 — custody and court release remain decoupled. Movement of source material is distinct from the legal decision to include a derived item in an export.

---

## OPEN: Decisions Requiring Owner Ruling

### Should operator-authored people live in a separate `analysis.matter_person` table or depend on extraction-generated `working.person` rows?

**Plain-English question:** Can the operator create and maintain case-specific people (e.g., the plaintiff, the defendant, key witnesses) independent of what the extraction system discovers, or must every person ultimately reference an extraction result?

**Option A (RECOMMENDED — matches ADR-0055):**  
Operator-authored people live in their own `analysis.matter_person` table. They are independent from extraction output. A future resolver may **optionally** point from `working.person` to the authored profile, but it's not required.

- **Consequence:** operator corrections and case profiles survive extraction re-runs and re-merges. People can exist in the case *before* the extraction system resolves them. Cleaner separation of concerns.

**Option B:**  
Every Matter person must reference a `working.person` row from the extraction layer.

- **Consequence:** human-curated case identity depends on a row that extraction may rebuild, merge, or delete. Custody of identity becomes indirect and fragile.

**(P1)**

---

### Should multi-role cardinality be supported now with normalized role tables, or simplified to one primary role + open text for MVP?

**Plain-English question:** In the first release, can a person have many roles (e.g., plaintiff in Case A, defendant's brother-in-law in the timeline, witness in Court Case B)? Or should you start simple with one `primary_role` field and a text `relationship_label` field, then add many-role tables later if real use proves the need?

**Option A (RECOMMENDED):**  
One optional `primary_role` and `relationship_label` as open text. Add normalized multiple-role rows only **after** real use proves the need.

- **Consequence:** simpler first schema, faster iteration. Avoids freezing speculative vocabulary. Easy to re-normalize later.

**Option B:**  
Create a normalized many-to-many role table now (e.g., `matter_person_role`).

- **Consequence:** flexible from day one but commits the MVP to a larger schema and API surface. Vocabulary decisions are locked in.

**(P3)**

---

### Should same-human identity across Matters be deduplicated by a global person registry, or stay Matter-local?

**Plain-English question:** If the same person (e.g., a lawyer who works on multiple cases) appears in two different Matters, should the system maintain a single canonical global record for that person, or allow separate Matter-local profiles?

**Option A (RECOMMENDED):**  
Allow separate Matter-local profiles and **never** deduplicate by name. Defer a global canonical-person authority to a future release.

- **Consequence:** simpler MVP. Single-Matter platform doesn't need cross-Matter identity yet. A global registry can be added later without migration pain.

**Option B:**  
Introduce a global authored person registry now.

- **Consequence:** creates a new identity-resolution system before the single-Matter MVP needs one. Risk of over-engineering.

**(P5)**

---

### Should evidence authentication and court release be one combined action or two separate decisions?

**Plain-English question:** When an operator decides "this evidence is ready for court," should that be one "make court ready" button that checks both "is this source authentic?" and "do I approve this content for export?", or should these be two separate decisions with separate audit trails?

**Option A (RECOMMENDED):**  
Keep them **separate**. Authentication and court release are distinct decisions. One future endpoint may coordinate them atomically, but only if both decisions and their evidence are explicit.

- **Consequence:** clearer audit trail. Operator decision is transparent: "I authenticated the source," "I approved the content," or both. Model/extraction confidence cannot silently become a legal-release decision.

**Option B:**  
One "make court ready" action sets both at once.

- **Consequence:** convenient but hides the decision boundary. Harder to audit what the operator actually approved.

**(R1)**

---

### Should confidence levels auto-upgrade on promotion, or require explicit human review?

**Plain-English question:** When you promote a piece of evidence from Knowledge to the case file, should the system automatically bump its confidence from "low" (default) to "medium" or "high" based on the parser or model scores? Or should the operator always make an explicit confidence decision?

**Option A (RECOMMENDED):**  
**Never** auto-upgrade confidence. Require an explicit, attributable confidence decision. Make numeric/tier consistency a database invariant before court release.

- **Consequence:** confidence becomes a genuine human foundation review, not a side effect of extraction scores. Court-facing claims rest on deliberate decisions, not model outputs.

**Option B:**  
Derive medium/high automatically from parser or model scores.

- **Consequence:** faster workflow, but model/extraction confidence silently becomes a legal-release decision without human review.

**(R2)**

---

### What does it mean to "redact nothing"? Is that an affirmative review, or just a default?

**Plain-English question:** If an evidence item has `redaction_status=none` and no privacy concerns flagged, is that enough to pass the court-readiness gate, or must the operator explicitly confirm "I reviewed this and no redaction is needed"?

**Option A (RECOMMENDED):**  
A default `redaction_status=none` is **not** evidence of review. A release decision must **explicitly affirm** that no redaction is required (e.g., operator checks "Reviewed for redaction: none required").

- **Consequence:** court record is unambiguous: someone looked at the redaction question and answered it. Defaults don't become hidden decisions.

**Option B:**  
Treat the default `none` value as an affirmative review.

- **Consequence:** faster path to court readiness, but silently converts a default into a human decision.

**(R4)**

---

### Should source custody transitions be independent from evidence court-release decisions?

**Plain-English question:** When you mark an evidence item as "court ready," should the source (the original file or message) automatically get marked as "released" in the custody log, or should custody status and evidence release be completely separate operations?

**Option A (RECOMMENDED — matches ADR-0059 D-065):**  
Keep them **independent**. Marking an evidence item court-releasable must **not** automatically append a source `released` custody event or change the source custody status.

- **Consequence:** custody events track movement/control of physical evidence. Legal release decisions track content inclusion. These are different domains and should have different audit trails.

**Option B:**  
Couple both transitions. When evidence is released, update source custody status too.

- **Consequence:** simpler workflow but confuses movement/control of source material with the legal decision to include a derived item.

**(R6)**

---

## Operational Approvals (Not Architecture Decisions)

These are **not** pending owner architecture decisions—they are **operational gates** on activation. The owner will approve or block each step based on readiness evidence.

### A1: Disposable canonical-image rehearsal
**Current Status:** HELD

Baseline PostgreSQL 18 image + migrations 0026–0030 to be run inside a **new, disposable** test instance. No shared database touched. Gate: owner approval after rehearsal report.

### A2: Target apply database
**Current Status:** HELD (depends on A1)**

Once A1 passes, owner names and approves the exact production database for migrations 0026–0030. Until then, all migrations remain held.

### A3: Credentials provisioning
**Current Status:** HELD

Provision distinct `WORKBENCH_API_KEY` and `AGENTOS_API_TOKEN` in the deployment environment. Never in git or command line. Gate: credentials securely stored before deploy.

### A4: Deploy and live proof
**Current Status:** HELD (depends on A2, A3)**

Workbench deployment approved and read-only activation (Matter, case-prefiltered Knowledge, Graphiti, spine, Weaviate) verified live. Gate: successful drill-through against production endpoints.

---

## Summary Table: ANSWERED vs. OPEN

| Decision | Question | Recommended Answer | Code Status | Label |
|---|---|---|---|---|
| People authority | Operator-authored vs. extraction-dependent? | Separate `analysis.matter_person` table | Assumed (no table yet) | P1 |
| Review flag | Auto-approve on creation? | No, `safe_for_legal_use=false` until explicit review | **LIVE IN CODE** | P2 |
| Role cardinality | Many roles now or simplified MVP? | One `primary_role` + open text `relationship_label` | Assumed (no role table yet) | P3 |
| Timeline scope | Automatic event inclusion in all cases? | Explicit many-to-many `court_case_event_scope` | **LIVE IN SCHEMA** | P4 |
| Cross-Matter identity | Global person registry now? | Matter-local only; defer global authority | Assumed (no global registry) | P5 |
| Auth + release coupling | One button or two decisions? | Two separate decisions | **LIVE IN CONTRACTS** | R1 |
| Confidence auto-upgrade | Promote parser scores to court confidence? | No; explicit human review required | **LIVE IN CODE** | R2 |
| Auth methods (MVP) | Which authentication types? | Hash-chain-of-custody only | **LIVE IN SCHEMA** | R3 |
| Redaction affirmation | Is default `none` enough? | No; explicit review required | **LIVE IN CODE** | R4 |
| Court release re-auth | Long-lived secret enough? | No; re-authenticated confirmation required | **LIVE IN SCHEMA** | R5 |
| Custody coupling | Release → custody transition? | No; keep independent | **LIVE IN SCHEMA (D-065)** | R6 |

---

## Conclusion

**Nine decisions are already baked into the code and schema** (P2, P4, R1–R6). The implementation made conservative, court-defensible choices: separate concerns, explicit review gates, no auto-escalation of model confidence, no implicit decisions.

**Three decisions remain open** (P1, P3, P5) and require owner ruling before detailed schema extension for people/roles. The existing implementation can proceed to testing and deployment without blocking on these—they govern optional future tables, not the current evidence flow.

**Operational approvals (A1–A4) are not architecture calls.** They are activation gates. Gates remain held until rehearsal (A1), database selection (A2), credential provisioning (A3), and live verification (A4) complete in sequence.
