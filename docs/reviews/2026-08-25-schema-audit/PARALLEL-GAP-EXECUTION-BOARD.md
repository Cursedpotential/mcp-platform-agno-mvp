# Parallel gap execution board

> Started: 2026-08-26  
> Purpose: convert every audit gap and semantic handoff into collision-safe implementation packets.  
> Rule: a written design is not a repaired gap. A packet is complete only with code, applicable tests,
> deployment, and live proof; partial results and blockers are persisted in packet status documents.

## Shared-checkout collision rules

1. Each agent owns only the files listed for its packet. It must stop and record a dependency before
   crossing another packet's boundary.
2. Implementation agents do not commit, push, merge, renumber migrations, or deploy unless the packet
   explicitly assigns that responsibility. The root integrator stages exact paths after reviewing the
   shared tree.
3. The root allocates every SQL migration number immediately before a SQL packet starts. Parallel agents
   never independently choose the same migration number.
4. Only one deployment writer may act on a given Coolify application at a time. Read-only probes may run
   concurrently. Cross-service cutovers are serialized through the production-integration packet.
5. Files with broad fan-out are integration locks: `server/api/main.py`, `server/agents/providers.py`,
   `server/case_management/repository.py`, `docs/PROJECT_CANON.md`, `docs/DECISION_LOG.md`,
   `docs/INDEX.md`, `.github/workflows/validate.yml`, and shared test fixtures.
6. No agent deletes anything. Retired files move to `to_be_deleted/`; only the owner deletes them.
7. Source is edited in this cwd. Formatting, lint, mypy/typecheck, unit tests, live-service
   integration tests, and application build tests are required here. Agents must not build or run a
   duplicate local container/application/data stack. Coolify owns container builds and deployment;
   final acceptance is proven against the live VPS service.

## Active slots

| Slot | Packet | Exclusive ownership | State |
|---|---|---|---|
| P-09 | GAP-008 retired Graphiti zero-caller path | context-chat sink, agent provider roster, focused tests/status | Claude Sonnet active (`task-mtaovgrc-paypzn`) |
| P-21 | GAP-030 Workbench async repair | `workbench/api/`, focused tests/status | Claude Sonnet active (`task-mtaovmy8-jqadse`) |
| P-18 | GAP-021 mandatory live integration CI | CI workflow, integration-only guard/receipt tests/status | prompt ready; dispatches when the forwarding slot frees |
| TS-08 preview | First live Timesketch-fork preview | new Timesketch image/compose/Coolify application only | root integration priority after fork commit `40ef4b2` |

The root is the integrator and does not consume a file-ownership packet. As soon as a slot finishes, the
next dependency-ready packet below is dispatched.

## Progress receipts — 2026-08-26

- P-01/GAP-032 Workbench surface: commit `1d7a72a`, Coolify deployment
  `spqradjsvl8skt1o9c2w5zqf`, live context-only denial proven with zero evidence/custody rows.
- P-08/GAP-004 ordinary-agent writer fence: commit `a358fd2`, Coolify deployment
  `v7lgr3vk4e9l8piz5ybz4fvv`, live Agno 2.8.7 provider exposes `query_database` and no
  `update_database`.
- P-02/GAP-031 strict item adjudication: workflow commit `afc3ab7` deployed to temporal-worker;
  persistence follow-through commit `6c96d1e`; live migration 0034 applied and verified (six
  columns, two constraints, two indexes). Revised n8n workflow import and supervised live proof
  remain.
- P-17/GAP-019 checker: commit `128927c`; 27-app live receipt persisted. This packet detects
  drift only; the serialized Coolify corrections remain.
- P-25/WP-D01/D02/E02: commit `40ef4b2`; pinned 1,010-file Timesketch snapshot, canonical PG
  timeline schema/projector, 90 combined targeted tests, and four live rollback integration tests
  passed. Migration 0035 and live Timesketch deployment/read-back remain production activation
  work.
- GAP-029 nonce experiment was rejected as unnecessary complexity and preserved under
  `to_be_deleted/`; the remaining packet is lifecycle invalidation proof using existing walk
  identities and rows.

## Collision-safe implementation packets

| ID | Gaps / WPs | Exclusive implementation ownership | Can run beside | Must not overlap / dependency |
|---|---|---|---|---|
| P-04 | GAP-003, GAP-022; C02 | promotion rehash/authentication logic in `server/case_management/`, dedicated tests, one root-allocated migration | agent, vector, Workbench, geo lanes | serialize with P-05 one-case because both touch repository/routes; requires custody contract decision |
| P-05 | GAP-013 | one-owner/one-case API and repository fences, compatibility tests | vector, Temporal, Timesketch, CI lanes | after P-04; locks `server/case_management/repository.py` and case routes |
| P-06 | GAP-002, GAP-023; context/evidence boundary | `server/ingest/`, evidence/context intake endpoints and tests, excluding hashing/promotion internals | agent authority, tokens, UI-only work | coordinate choke-point edits with P-04 and P-07; no Workbench edits until P-01 lands |
| P-07 | GAP-016, GAP-017, GAP-025 | Temporal evidence workflows/activities/worker, crash recovery and retry-budget tests | vector, agents, Timesketch | after P-02 because Temporal files/tests may share fixtures; consumes P-06/P-04 contracts |
| P-08 | GAP-004 | `server/agents/factory.py`, `server/agents/providers.py`, governed-writer tests | custody, vector, Timesketch | before P-09; providers file is locked against Graphiti retirement |
| P-09 | GAP-008 | Graphiti caller/sink retirement in context ingestion, agent roster cleanup, Graphiti deploy manifest and zero-caller proof | custody, Timesketch, CI | after P-08; shares `server/agents/providers.py` |
| P-10 | GAP-005 | canonical projection-eligibility predicate, `server/evidence/vector_projection.py`, focused tests, dedicated migration | agents, Workbench, Temporal | root-allocated migration; coordinate schema contract with P-12 |
| P-11 | GAP-006 | Weaviate authentication/TLS/service-role config and direct-store denial tests | custody, Temporal, Timesketch | owns Weaviate deploy manifests and `server/core/session.py`; no live restart with P-13/P-17 |
| P-12 | GAP-009, H01 | universal PG projection receipt/manifest and independent reconciliation runtime/tests | Workbench, agents, UI | foundational SQL/API contract; precedes P-14/P-15/P-25; root-allocated migration |
| P-13 | GAP-020, GAP-024 | native-evidence flag contract and reconnect/readiness recovery in runtime/main, boot-down tests | custody, Timesketch, docs | after P-11; locks `server/api/main.py`, native runtime and vector deployment state |
| P-14 | GAP-010 | PG-authorized Surreal projector/schema/receipts and rebuild/revocation tests | UI, geo, created works | after P-12; no separate canonical state; serialize production data-service changes |
| P-15 | GAP-011; R11 | paired as-lived/hindsight execution, canonical PG walk/belief/checkpoint/delta receipts | UI, geo, created works | after P-12/P-14 and token P-03; locks walk derivation modules and walk migrations |
| P-16 | GAP-012, GAP-014, GAP-015, GAP-027 | bootstrap, runtime roles, grants/RLS, immutability boot gate, cross-walk denial tests | Workbench UI, docs, analyzer-only work | owns role/grant/bootstrap SQL and exec DB identity; serialize migration allocation and exec deploy |
| P-17 | GAP-019 | deployment drift checker, immutable SHA/rendered-config/watch-path receipts | code-only packets | owns deployment tooling/metadata; does not change application code; serialize any Coolify writes |
| P-18 | GAP-021 | mandatory integration CI job, no-all-skipped guard, receipt publication | narrowly owned code packets | owns CI workflow and shared integration harness; best after first contract wave to reduce churn |
| P-19 | GAP-026 | governed PostGIS source/generation/outbox/receipt path and geo tests | Workbench, agents, Temporal | root-allocated geo migration; consumes P-12 receipt interface |
| P-20 | GAP-028 | production environment/dependency fail-fast/auth cold-start proof | case, Temporal, Timesketch | after P-13 because both touch `server/api/main.py` and `deploy/exec.yaml` |
| P-21 | GAP-030 | async Workbench HTTP/storage and concurrency tests | backend, vector, agents | after P-01; locks `workbench/api/` only |
| P-22 | GAP-007, B01/B02 | Semantica temporal candidate runner, governed claim review, Neo4j anchors/receipts | Workbench UI, Temporal, platform ops | coordinate with P-23 typed output schema and consume P-12 receipt contract |
| P-23 | GAP-033, B01/B02/G01/G02 | typed claim/event/legal-issue/observation/strategy/created-work physical contracts and adoption path | vector security, deploy drift, UI | root-allocated migration; must freeze contract before P-22 runtime writers and P-24 UI |
| P-24 | F03 | Timesketch bulk-curation UI, authority badges, preview/conflict/reversal/source-open | backend-only packets | after P-26/P-27 APIs; owns `timesketch-fork` UI subtree only |
| P-25 | D01/D02/E02 | canonical PG timeline generations/memberships plus PG-to-Timesketch projector/read-back | agents, Workbench, Temporal | consumes P-12; root-allocated migration; owns projector/backend, not UI |
| P-26 | F01 | context curation batch/item/preview/conflict/partial/atomic/reversal ledger and API | UI, agents, vector | after timeline contract P-25; dedicated migration and API namespace |
| P-27 | F02 | approved-entry amendment candidate and immutable-successor re-review | UI, vector, deploy drift | after P-04/P-26; shares promotion/review contracts, so no overlap with those packets |
| P-28 | H02 | production integration, least privilege, representative corpus, rollback and signed manifest | none of the same deployment targets | final serial cutover after H01 and domain acceptance; owns deployment execution and attestation |

## Dispatch waves

The table lists concurrency, not priority alone. A later wave begins immediately when its prerequisites
are met and a slot is free.

1. **Wave 1 — active:** P-00, P-01, P-02, P-03.
2. **Wave 2 — independent authority boundaries:** P-04, P-08, P-10, P-17. These own disjoint
   case-management, agent, vector-projection, and deployment-audit surfaces.
3. **Wave 3 — durable execution and infrastructure:** P-06, P-09, P-11, P-16. These own disjoint
   intake, Graphiti, Weaviate, and PostgreSQL-role surfaces after prior locks clear.
4. **Wave 4 — orchestration and contracts:** P-07, P-12, P-18, P-23. Temporal, reconciliation,
   CI, and typed-domain contracts are separate; SQL numbers are allocated by root.
5. **Wave 5 — projections and product APIs:** P-13, P-19, P-22, P-25. Runtime recovery, geo,
   governed extraction, and timeline projection remain file-disjoint while consuming frozen contracts.
6. **Wave 6 — governed user workflows:** P-05, P-21, P-26, P-14. One-case, Workbench async,
   curation API, and Surreal execution are disjoint after their respective dependencies.
7. **Wave 7 — amendment/delta/UI:** P-15, P-20, P-24, P-27. Walks, production runtime guard,
   Timesketch UI, and amendment re-review are disjoint once their foundations land.
8. **Wave 8 — production acceptance:** P-28 alone controls cross-service cutover, rollback and the
   signed R14 manifest. Independent read-only reviewers may run in parallel, but no other deploy writer may.

## Integration queue

For every completed packet the root performs: exact diff review; overlapping-dirty-file check; targeted
tests; mandatory applicable live integration test; packet-specific commit; branch synchronization where
required; deployment only to the assigned application; live acceptance probe; and status updates in this
board, the gap register, semantic work-package board, and packet receipt.
