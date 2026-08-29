# Unified operator surface implementation specification

> _Byline: Codex · GPT-5 · 2026-08-27._

**ADR**: [Unified operator shell ADR](/docs/adr/0061-unified-operator-surface.md)

- Phase: `preflight`
- Status: **Proposed; implementation blocked pending owner acceptance and preflight verification**
- Scope: Workbench, SBV, Timesketch fork, Temporal, n8n, Semantica, Legal-Workspace, object acquisition

## Outcome

Deliver one owner-facing product shell that preserves the same selected matter/case, source/run context,
authorization, status language, and source-opening behavior across the evidence and legal lifecycle.
The shell composes independently deployable applications and headless runtimes; it does not combine
their databases, source trees, or authority.

## Current verified boundary

- Workbench exists but its deployed manual ingest path is older than the new Universal Import Workflow.
- SBV currently combines parsing/runtime, SQLite storage/auth, and visual-preview foundations. The
  accepted target separates those concerns: SMS decoding joins the common Go-selected parser contract,
  custody remains its own upstream activity, and the storage-free SBV client becomes the embedded
  pipeline preview inside the Workbench shell.
- Timesketch has an accepted maintained-fork direction and PostgreSQL-authoritative projection contract;
  integrated live smoke remains unverified.
- Temporal Web and n8n exist as operational consoles. Product status must be summarized in Workbench;
  their editors remain admin-only deep links.
- Semantica produces governed extraction/candidate material and has no required production web surface.
- Legal-Workspace is a separately deployable post-evidence application. Its current shared-secret/browser
  token pattern is not acceptable as unified SSO, and its deployment is not live-proven.
- R2, B2, and the Windows desktop are not yet connected to the new UIW acquisition boundary. The target
  is upload-to-object-store followed by an opaque object reference, sealing copy, and the same workflow.

## Graph-thinking analysis

### Node map

| Cluster | Nodes | Centrality | Boundary |
|---|---|---|---|
| Product control | Owner, Workbench shell/BFF, OperatorContext, launch exchange | high | navigation, scoped authorization, status |
| Evidence authority | Platform API, PostgreSQL, review gates, ledgers | highest integrity | canonical custody/context/evidence/governance |
| Ingest runtime | acquisition adapter, common Go parser coordinator, custody activity, Temporal, n8n | high | headless deterministic execution and receipts |
| Candidate analysis | Semantica, candidate queues, investigation register | medium | proposals only, never facts/evidence |
| Timeline | projection generation, Timesketch/OpenSearch, curation batch | high | rebuildable display and governed reverse commands |
| Legal | LegalSourcePackage, Legal-Workspace, review/release, evidence request | high | legal work product, never evidence authority |
| Engineering/admin | Temporal Web, n8n editor, Coolify consoles | low product / high operations | diagnostics and configuration only |

### Relationship matrix

| From | To | Relationship | Strength |
|---|---|---|---:|
| Workbench | Platform API | matter-scoped reads and typed product commands | 5 |
| Workbench | bounded apps | audience-bound one-time launch context | 5 |
| Workbench | Temporal/n8n | summarized status and admin deep links | 3 |
| acquisition adapter | UIW | immutable source reference and provenance | 5 |
| SBV preview client | UIW/platform APIs | confirmed source/parser/config/preview hash plus read-only custody/run/message projections | 5 |
| Temporal | n8n | bounded activity-body invocation | 3 |
| Temporal | Semantica | immutable normalized batch | 3 |
| Semantica | PostgreSQL | provenance-rich candidates only | 5 |
| PostgreSQL | Timesketch | immutable projection generation/hash | 5 |
| Timesketch | PostgreSQL | typed curation/amendment commands | 5 |
| PostgreSQL | Legal-Workspace | signed immutable LegalSourcePackage and stale events | 5 |
| Legal-Workspace | Platform API | governed investigation request | 4 |

### Clusters, paths, bottlenecks, opportunities

- **Clusters:** product control; evidence/runtime; timeline projection; legal work; engineering/admin.
- **Critical paths:** acquire→preview→confirm→Temporal; PG generation→Timesketch→typed command→successor
  generation; approved selection→LegalSourcePackage→draft→review→release; revocation→legal stale state.
- **Bottlenecks:** launch/scope contract, preview hash binding, typed reverse-command API, and package issuer
  validation. These are foundation work, not integration polish.
- **Opportunity:** the same correlation ID can connect intake, workflow, curation, legal package, review,
  and release without giving any surface authority over the others.

## Contract set

### `OperatorContextV1`

Required fields:

- `context_id`, `matter_id`, optional `court_case_id`;
- `actor_id`, `capability`, `audience`, `issued_at`, `expires_at`, `nonce`;
- `correlation_id` and optional `workflow_id`, `run_id`, `source_id`;
- optional custody/hash references, timeline generation, legal package/version;
- schema version and issuer.

The browser may carry a signed one-time ticket, not a reusable platform credential. The target exchanges
the ticket server-side, consumes the nonce atomically, revalidates the referenced scope, and issues its
own HttpOnly, Secure, SameSite-scoped session. Query-string IDs never grant access.

### `SourceObjectRefV1`

Provider-neutral fields: provider (`r2`, `b2`, or approved upload ingress), opaque bucket/key/version,
declared size/MIME, source filename, acquisition actor/time, expected source hash when known, and
correlation ID. The acquisition activity copies the bytes into immutable `source-objects`, records
provider/version and filesystem/media metadata, computes custody hashes, and never lets a downstream
parser fetch arbitrary network locations.

Windows ingestion uses Workbench upload or an authenticated watched-uploader to R2/B2. The VPS does not
mount or treat the desktop filesystem as production storage.

### Reverse-command contracts

- `PreviewDecisionV1`: exact source, parser/version, configuration, preview hash, decision, actor,
  rationale, idempotency key.
- `TimelineCurationBatchV1`: expected generation, target versions, before/proposed hashes, typed
  operation, rationale, atomicity mode, per-item receipts.
- `LegalSourcePackageV1`: platform issuer, matter/case, manifest/package hashes, approved assertion and
  span/custody references, versions, egress policy.
- `InvestigationRequestV1`: matter, legal issue/element, missing-proof statement, rationale, originating
  work-product/version, correlation ID; never evidence or a fact.

## Route and surface ownership

| Workbench route | Owning capability | Presentation |
|---|---|---|
| `/matter` | Workbench | native cross-domain status and selected context |
| `/intake`, `/runs/:id` | Workbench + platform runtime API | native acquisition, preview decision, receipts, source opening |
| `/evidence/preview` | SBV client inside the Workbench shell | same-origin bounded pipeline preview; no SQLite, local auth, ingest, or canonical writes |
| `/timeline` | Timesketch fork | proxied bounded app with Workbench context/return controls |
| `/candidates` | Workbench | native Semantica/extractor candidate queues and review |
| `/legal` | Legal-Workspace | proxied bounded app; optional full-page route for dense work |
| `/admin/temporal`, `/admin/n8n` | external admin consoles | status plus deep link; never product embeds |

Module federation is not part of the design. Composition uses stable HTTP/API contracts, same-origin
gateway routing, and local sessions.

## Runtime boundary

1. Workbench or an API client submits an opaque source reference.
2. Temporal owns durable orchestration, retries, timers, approval state, and receipts.
3. n8n mini-workflows may implement bounded activity bodies and generic extraction/integration steps.
4. Parsers only parse. Hashing, metadata extraction, normalization, validation, persistence, projection,
   and review are separate atomic activities under the common contract.
5. The surface may be offline or unfinished; the same runtime remains callable through its authenticated
   API.
6. The preview client reads message projections, custody receipts, and run events from platform APIs.
   It never computes custody, selects parsers, or owns workflow state.

## Second-order analysis

```text
decision: Use Workbench as the unified shell/BFF while preserving independent bounded applications.
first_order: One login and operating context makes the evidence-to-legal lifecycle visible and usable.
chain:
  - order: 2
    effect: Downstream apps may begin trusting convenient browser-carried matter/package identifiers.
    actors: Workbench and bounded-app maintainers
    p: medium-high
    when: immediate
    feedback: reinforce
  - order: 3
    effect: Stale or compromised surface context submits commands against the wrong governed version.
    actors: owner, platform API, bounded applications
    p: medium without mandatory ticket validation
    when: next_cycle
    feedback: reinforce
  - order: 2
    effect: Teams may embed every engineering console and couple all delivery to the shell.
    actors: product and operations maintainers
    p: medium
    when: next_cycle
    feedback: reinforce
  - order: 3
    effect: Shell outages and cross-app upgrades block otherwise independent operations.
    actors: owner and platform operations
    p: medium
    when: at_scale
    feedback: reinforce
  - order: 2
    effect: Governed pending states add visible friction to timeline and legal edits.
    actors: owner
    p: high
    when: immediate
    feedback: balance
  - order: 3
    effect: Read-back receipts and immutable successors make errors recoverable and authority legible.
    actors: owner and reviewers
    p: high
    when: next_cycle
    feedback: balance
scale_if_universal: At 10x sources and edits, shared credentials and synchronous coupling fail; opaque
  references, local sessions, async receipts, and rebuildable projections remain bounded.
revised_decision: Proceed only with signed scope, one-time exchange, typed command gates, direct fallback
  routes, and successor read-back in the foundation package.
mitigations: Negative scope/replay tests, CSP/cookie tests, no admin-console embeds, pending-state UI,
  per-item receipts, graceful shell degradation, and correlation IDs end to end.
```

## Implementation packages and collision boundaries

| Package | Owner/files | Depends on | Live exit |
|---|---|---|---|
| U0 contract foundation | new import-light contracts and compatibility tests | ADR acceptance | ticket, context, source-ref schemas pass cross-repo vectors |
| U1 gateway/session | Workbench BFF auth/proxy only | U0 | wrong audience/scope/replay denied live; direct fallback remains |
| U2 shell/navigation | Workbench web shell/routes/status | U0 | context persists across every product route |
| U3 acquisition/manual intake | Workbench intake + runtime acquisition adapter | U0, live UIW | R2 and B2 objects seal into same workflow; Windows upload proven |
| U4 SBV preview | storage-free SBV client, platform read APIs, launch adapter, preview gate | U0, U1, UIW | messages/custody/run events render from platform state; reject writes no import; approve binds exact preview and runs |
| U5 Timesketch bridge | projector/curation APIs and fork adapter | U0, ADR-0060 | bulk round trip, stale conflict, amendment-only evidence edit proven |
| U6 Legal contracts | package issuer/import verifier and stale events | U0 | issuer/hash/scope negatives and revocation loop proven |
| U7 Legal launch/shell | Legal local session + Workbench `/legal` | U1, U6 | no browser shared secret; draft/review/release flow proven |
| U8 candidate/run summaries | Workbench native Semantica and Temporal/n8n views | U0 | candidate cannot promote itself; admin credentials never exposed |
| U9 production acceptance | Coolify routing, CSP, observability, rollback receipts | U1-U8 | live current-revision receipt for each shipped package |

U4 also owns the SBV retirement gate. Retained source XML is the migration authority for SMS/MMS,
because legacy SQLite `media_data` contains only the first MMS attachment. Re-ingest must prove complete
attachment coverage and the live preview must read the platform projection before any SQLite path is
moved to `to_be_deleted`; SQLite row parity is insufficient.

Reserve shared contract names, gateway routes, and cross-repo manifest versions to one integrator. SBV,
Timesketch, Legal-Workspace, and Workbench implementation packages otherwise have separate file ownership
and may proceed in parallel after U0.

## Verification matrix

| Concern | Static/unit | Integration | Required live proof |
|---|---|---|---|
| context ticket | schema/signature/expiry vectors | exchange and nonce store | replay, wrong audience, wrong scope denied across replicas |
| acquisition | provider-ref and hash vectors | R2/B2 fixtures to seal | real R2 and B2 objects plus Windows upload reach UIW |
| preview | deterministic hash and decision vectors | API→Temporal start | live reject/approve and idempotent retry |
| timeline | generation/batch compatibility | PG↔fork round trip | bulk partial/atomic, stale conflict, rebuild, amendment re-review |
| legal | package/citation/revocation vectors | platform↔Legal API | import, draft, review, release, revoke/stale, rollback |
| shell | route/context/component tests | gateway/session/CSP | browser preview of all product routes and direct fallback |

No package is complete on local tests alone. Completion requires its applicable Coolify deployment,
current-revision check, negative authorization tests, rollback test, and a durable receipt.

## Rollout and rollback

- Ship routes behind capability flags and retain the existing direct URLs.
- Deploy the contract and gateway foundation before exposing product navigation.
- Add one bounded surface at a time: intake/SBV, Timesketch, candidate/run status, then Legal-Workspace.
- Rollback removes the shell route/capability flag and revokes outstanding launch tickets; it does not
  delete canonical data, projections, or legal history.
- Quarantine replaced files under `to_be_deleted`; only the owner deletes them.

## Preflight checkpoint

- [x] ADR exists with YAML frontmatter.
- [x] ADR links this design spec.
- [x] ADR Context includes the Before/After diagram.
- [x] ADR Architecture includes the architecture diagram.
- [x] ADR contains exactly two diagrams.
- [x] This design spec links the ADR.
- [x] Graph node/edge/cluster/path analysis is recorded.
- [x] Second- and third-order consequences include actors, probability, timing, feedback, scale, revised
  decision, and mitigations.
- [ ] Owner accepts ADR-0061.
- [ ] ADR status and repository index are updated to Accepted in the same change.

Implementation remains blocked at the unchecked owner-acceptance gate.
