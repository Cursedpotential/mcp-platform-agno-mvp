# Complete Codebase Audit — 2026-08-26

## Outcome

The repository does not currently implement the owner-governed controlled-replay product end to
end. The strongest implemented pieces are useful foundations, but the load-bearing authority
transition, cross-store reconciliation, production Surreal aggregation, paired walk execution and
deceit/realization delta remain incomplete or absent.

This audit is a repository-backed evaluation of current code and tracked configuration, plus a
dated read-only live-parity snapshot. It is not an exhaustive file-level or live-production
certification: no mutation, workflow execution, restart, deployment, failover or rollback proof was
authorized, and the discovery limitations below prevent a reproducible completeness claim. The
independent R14 live-verification pass described below remains required.

The owner correction governing this reconciliation is explicit: **Agno is not an owner of truth.**
It is a replaceable runtime/orchestration adapter. PostgreSQL owns canonical custody, normalized
state, governance, lineage, horizon inputs, durable run records and reconciliation receipts;
specialized stores remain governed projections. Any Agno-native database tool, session/memory
feature or workflow shortcut that can create independent authority is drift, not product canon
(`docs/PROJECT_CANON.md:62-68,371-388`; D-078/D-080).

The immediate program gates fail:

- **R00 fails** because current-truth documents and runtime surfaces still teach mutually exclusive
  Graphiti/Surreal and single-case/multi-Matter architectures.
- **R04 fails** because intake creates evidence custody before owner promotion, while promotion does
  not independently verify the governed H1/H2/H3 construction.
- **R09 fails** because no universal PostgreSQL projection-receipt and reconciled aggregation
  manifest exists.
- **R11 fails** because no production paired as-lived/hindsight walk produces the governed delta.
- **R14 fails** because required live integration and direct-store contamination/security proofs
  are absent from CI and were not established in this audit.

## Audit contract and boundaries

This report completes the repository phase requested by
`SESSION-HANDOFF-COMPLETE-CODEBASE-AUDIT.md`. It covers:

1. repository/module/service inventory;
2. static PostgreSQL object and migration inventory;
3. writer/reader/caller censuses for authority-bearing paths;
4. API, agent/tool, Temporal, n8n, Workbench and CLI entrypoints;
5. Weaviate, Semantica/Neo4j, Graphiti, Surreal, PostGIS, pgvector and pg_duckdb paths;
6. D-069 through D-081 decision-to-code traceability;
7. tracked deployment/configuration parity;
8. authority, correctness, security, horizon, retry, performance and maintainability risks;
9. test and live-proof coverage;
10. the deduplicated gap register in [AUDIT-GAP-REGISTER.md](AUDIT-GAP-REGISTER.md); and
11. evidence-backed amendments to the R00–R14 guides.

No production mutation, migration, deployment, cleanup or destructive operation was performed.
No applied migration was edited. Existing dirty-tree changes were preserved.

## Coverage accounting

### Repository freeze

- Branch: `main`, HEAD `4dff58a`, one commit ahead of the recorded `origin/main`.
- Tracked paths: 2,546.
- Major tracked areas: `docs` 1,010; `server` 835; `workbench` 215; `vendored` 130;
  `tests` 101; `scripts` 67; `docker` 48; `sql` 41; `deploy` 25.
- Pre-existing tracked modifications: ten canon/ADR/reference files, 242 insertions and 68
  deletions, none staged.
- Pre-existing untracked state: 2,267 paths, including 2,232 under `_stale` and the schema-audit
  package. Nothing was deleted or moved.

### Discovery index

CCC was repaired during this audit after NVIDIA retired `nvidia/nv-embed-v1` on 2026-08-25. It now
uses `nvidia/nemotron-3-embed-1b`; indexing and query checks both return 2,048-dimensional vectors.
The rebuilt SQLite-backed CCC index (`.cocoindex_code/target_sqlite.db`) contains 37,751 chunks
across 2,229 files. At the audit freeze, the configured walk matched 2,310 files, leaving an 81-file
coverage difference. Forty-nine file-indexing failures were recorded; their common upstream error
said image inputs require a VLM endpoint. A later 2026-08-26 challenge found 2,312 currently eligible
files, 50 component failures in the daemon log, and final audit artifacts newer than the index.
No per-file failure-resolution manifest reconciles those differences. Exact search and direct reads
compensated for individual findings, but the semantic index is neither complete nor freshness proof.

The handoff required an available DuckDB repository catalog for coverage and dependency analysis.
No qualifying repository catalog, schema, query transcript, or result artifact was identified; the
visible DuckDB files were not established as codebase catalogs. Product `pg_duckdb` paths and the
dated live extension-version check were reviewed separately. Consequently, this report does not
claim that the requested DuckDB discovery method was completed.

### PostgreSQL static inventory

The repository contains 33 numbered migrations (`0001`–`0033`) with at least 77 direct
`CREATE TABLE`, 27 view, 23 function, 19 trigger and four role statements. These are source
statement counts, not live-object counts: dynamic DDL and the captured bootstrap baseline add
objects. `sql/README.md:61-147` explicitly records that numbered migrations do not bootstrap the
whole historical custody schema and that current-image replay has caveats.

### Runtime entrypoint census

- AgentOS/FastAPI assembly: `server/api/main.py:246-459`.
- Agent/team roster: `server/agents/factory.py:133-535`.
- Workbench API assembly: `workbench/api/main.py:48-149`.
- Temporal worker/workflows/activities: `server/temporal/worker.py:47-74`,
  `server/temporal/workflows.py:132-304`, `server/temporal/classification_workflow.py:47-154`.
- n8n staged workflows: `docs/research/integration-audit-2026-08-24/composed/`; the latest tracked
  handoff says they were not imported (`docs/HANDOFF-2026-08-24-n8n-pipeline-golive.md:36-45`).
- Evidence CLI: `server/evidence/cli.py:24-120`.
- Tracked deploy definitions: 18 primary YAMLs plus the Temporal submanifest; the Temporal worker
  has a Dockerfile but no tracked deployment manifest (`deploy/temporal/compose.temporal.yaml:12-18`,
  `docker/temporal-worker/Dockerfile:1-46`).

## Principal findings

### 1. Context-to-evidence authority is reversed

All inspected active evidence-intake paths call `ingest_artifact()` before parsing/context landing:

- framework-neutral ingest: `server/ingest/service.py:302-320`;
- legacy Agno workflow: `server/evidence/workflows.py:621-676`;
- Temporal custody Activity: `server/temporal/activities.py:149-182`.

`ingest_artifact()` immediately writes `evidence.source` and H1 custody records
(`server/evidence/custody.py:277-328`). Promotion then resolves that pre-existing H1 and inserts an
analysis evidence item (`server/case_management/repository.py:643-659,793-895`). The SQL guard
checks the same existing H1 (`sql/0030_matter_case_foundation.sql:309-332`); it does not independently
rehash original bytes, recompute `h2-canonical-v2`, reconcile ordered generation membership, or
verify `h3-chain-h1genesis-hexconcat-v1`.

This directly contradicts D-069/D-075/D-076. It also means a parse failure can leave custody rows
behind and the current promotion API cannot be the authority transition defined by canon.

### 2. Canon and runtime still disagree about active graph/case architecture

D-070 retires Graphiti and D-073 assigns final temporal aggregation/walks to Surreal. Root and canon
still call Graphiti active (`AGENTS.md:83,96-106`; `docs/PROJECT_CANON.md:95-105,357,427-442,708-716`),
and runtime still offers Graphiti tools/writes (`server/agents/providers.py:194-212`,
`server/analysis/context_chat_ingest.py:320-357,532-562`).

D-072 fixes the product at one owner/one case, yet public APIs still create Matters/CourtCases
(`server/api/case_management_routes.py:62-82`; `server/case_management/repository.py:514-624`).
These conflicts fail R00's zero-contradiction gate and can drive future implementation in the wrong
direction.

### 3. Specialized-store authority is not reconciled

The native Weaviate search path correctly composes case, completeness, active authority,
disclosure and horizon filters before ranking (`server/core/evidence_vector_store.py:344-410`).
That control must be preserved. Its SQL trigger enqueues every normalized chunk. The projector does
deactivate objects whose message route is not approved via `source_available_from()`, but it does
not enforce owner promotion/custody eligibility and otherwise hard-codes
`authority_state='active'` (`sql/0026_realization_event.sql:316-333,519-554`;
`server/evidence/vector_projection.py:150-215`).

Semantica is correctly candidate-only, but only as an isolated library/repository proof
(`server/analysis/semantica_worker.py:1-8,120-159`;
`server/analysis/semantica_wiring.py:26-33,133-160`). No production candidate runner,
candidate-to-governed-fact transition or provenance-anchored Neo4j projector/receipt exists.

No universal PG projection receipt or R09 aggregation manifest exists. Weaviate has local job
markers and filesystem activation reports; Graphiti has timestamps/refs; Semantica/Neo4j has no
production projector; geo is absent; the Surreal proof self-reconciles only inside its fixture.

### 4. Surreal and the paired delta are proof-only/absent

The Surreal Phase-1 composition is explicitly synthetic and disposable
(`deploy/compose.surreal-phase1.yaml:1-4,48-74`) and the runner hard-codes synthetic identities and
vectors (`docker/surreal-phase1-runner/src/horizon_surreal_phase1/runner.py:37-60`). It demonstrates
valuable prefilters, quarantine, resume/seal/rewalk and parity behavior, but it does not consume an
R09 PG-authorized manifest or return production receipts.

The PG walk deriver creates corpus/checkpoint ledger rows without invoking an agent or recording
beliefs/conclusions (`server/evidence/derivation.py:220-365`). Its inserts omit the `record_id` used
by `vw_walk_delta`, while that view compares a step with a record rather than pairing as-lived and
hindsight runs (`sql/0027_walk_ledger.sql:381-396`). The controlled-replay deliverable is therefore
not implemented.

### 5. Direct datastore access bypasses application authority controls

Both tracked Weaviate manifests publish REST/gRPC and enable anonymous access
(`deploy/data-weaviate-native-v1.yaml:9-16`; `deploy/data-weaviate.yaml:16-30`). The client allows
no API key and plaintext transport by default (`server/core/session.py:115-138`). A reachable peer
can bypass the API's horizon prefilter/audit seam.

Graphiti similarly publishes direct unauthenticated MCP ports despite a stated gateway boundary
(`deploy/data-graphiti.yaml:90-118`; `deploy/data-graphiti-case.yaml:86-97`). Workbench calls the
direct endpoint without authentication (`workbench/api/app/repo/graphiti_client.py:7-27,76-85`),
while that server exposes write/destructive tools. Server-side authentication, network policy and
role separation are required before either store can be treated as an enforcing projection.

### 6. Runtime durability and approval boundaries have bypasses

Agents receive Agno database tools backed by a writable engine in addition to the documented
approval-gated SQL tool (`server/agents/providers.py:147-192`;
`server/agents/factory.py:26,90,165,195`). The installed Agno 2.8.7 provider defaults to
write-enabled tools (`.venv/Lib/site-packages/agno/context/database/provider.py:36-53,109-115,173-181`),
creating an unapproved database mutation surface. This dependency evidence must be rechecked when
the pinned Agno version changes.

Framework-neutral HTTP ingest returns 202 and schedules only an in-process asyncio task
(`server/api/ingest_routes.py:85-159`), with no startup recovery consumer. Temporal store retries
are multiplied by the store layer's internal four-attempt loop
(`server/temporal/workflows.py:111-116,256-267`; `server/evidence/store.py:85-89,206-225`).
The current classification HITL signal accepts any non-`abort` value and then includes every
`needs_review` item (`server/temporal/classification_workflow.py:81-84,131-154`).

### 7. Reproducibility and court-ready transitions are incomplete

The migration chain cannot create the full historical custody schema and the `agno_app` role was
created live out of band (`sql/README.md:61-147`;
`docs/HANDOFF-2026-08-24-ingest-testing.md:14-23`). Immutability was last recorded OFF, and migration
0031 permits evidence/working mutation unless `app.evidence_live=on`
(`sql/0031_dev_mode_immutability_gate.sql:40-113`).

Review approval explicitly leaves `safe_for_legal_use=false` and `is_authenticated=false`, and no
other non-vendored writer was found that transitions them true
(`server/case_management/repository.py:939-989`). The current court-safe view requires those states
(`sql/bootstrap/schema_baseline.sql:3470,4205`).

### 8. Test/live verification is below owner policy

CI runs only `pytest -q` (`.github/workflows/validate.yml:41-48`). The repository contains one marked
integration test, skipped unless `HORIZON_SCRATCH_LIVE=1`
(`tests/integration/test_ingest_scratch_live.py:21-30`). There is no required job proving direct
store denial, horizon canaries, custody promotion/reverification, Temporal crash recovery,
cross-store reconciliation, Surreal projection, paired delta or Workbench legal consumption.

## Read-only live-parity snapshot — 2026-08-26

The accessible live surfaces materially strengthened, but did not close, the repository findings:

- exec uses PostgreSQL superuser `ai`, not the restricted `agno_app` role;
- audited PostgreSQL state had RLS enabled on 0 of 143 inspected evidence/working/analysis base
  tables;
- exec runs with `RUNTIME_ENV=dev`;
- n8n was healthy but its authenticated workflow inventory was empty;
- both legacy and native Weaviate services were ready on v1.38.7, while the configured native flag
  was descriptive text and evaluated false in the application parser;
- Graphiti applications were running and exec still carried `GRAPHITI_MCP_URL` despite the current
  retirement direction;
- several Coolify watch paths referenced old pre-`deploy/` manifest names, application
  `git_commit_sha` values reported `HEAD`, and observed deployments were on older revisions;
- PostgreSQL reported 18.1 with pg_duckdb 1.1.0, PostGIS 3.6.4 and vector 0.8.6; extension presence
  did not prove the governed workloads or R09 receipts;
- Temporal UI/worker health did not establish a registered production workflow execution; and
- the legacy Surreal URL timed out while the Phase-1 synthetic proof remained reachable.

These observations were read-only. They establish drift and missing proof, not permission to alter
credentials, flags, roles, workflows, deployments or data.

## D-069 through D-081 traceability result

| Decision | Repository status | Summary |
|---|---|---|
| D-069 | Contradicted | Intake creates custody; promotion expects an evidence lane. |
| D-070 | Contradicted | Graphiti remains in canon, agent tools, drains and direct Workbench access. |
| D-071 | Partial | Contracts retain participants, but persisted third-party shape externalizes some participant data. |
| D-072 | Contradicted | Matter/CourtCase creation APIs and writers remain active. |
| D-073 | Proof-only | Synthetic Surreal proof exists; production PG-authorized aggregation does not. |
| D-074 | Partial | Candidate isolation exists; production Semantica/Neo4j/governance lifecycle does not. |
| D-075 | Not implemented | Promotion does not recompute/verify normalized H2. |
| D-076 | Held/design | Precise H3 tag has no production writer; vectors exist in tests/canon only. |
| D-077 | Partial/wrong boundary | Temporal exists but combines custody-first stages and lacks required hashing Activities. |
| D-078 | Partial | Per-slice outboxes exist; universal PG receipt/control plane and R09 do not. |
| D-079 | Stack-only | PostGIS extension is declared; governed geo lifecycle is absent. |
| D-080 | Partial | Extensions are provisioned; governed workloads/reconciliation are incomplete. |
| D-081 | Design-only | R00–R14 package exists; no lane has passed final integration. |

Only about 13 genuine D-IDs and 40 ADR IDs are cited in implementation scope across 141 files;
D-072 through D-081 have no implementation citations. `docs/CONVENTIONS.md:96-109` correctly says
this is not a mandate to annotate every file, but load-bearing implementations still need
decision-traceable contracts and tests.

## Controls to preserve

- Native Weaviate schema/alias validation fails closed (`server/core/evidence_vector_store.py:190-266`).
- Native Weaviate applies source availability before ranking (`server/core/evidence_vector_store.py:344-410`).
- Semantica extraction forms candidates, not facts/beliefs (`server/analysis/semantica_worker.py:1-8`).
- The Surreal proof exercises exact horizon filtering, quarantine, deterministic reprojection,
  resumable healthy pauses and terminal seal/rewalk behavior.
- Weaviate activation independently compares PG and store count/hash manifests, even though those
  receipts must move into PG for R09 (`server/evidence/native_activation.py:182-219`).

## Required dependency order

1. **R00** freezes one contradiction-free canon and successor ADR set.
2. **R01** adds reproducible roles, universal outbox/job/receipt primitives and enforcing flags.
3. **R02/R03/R04** establish context-first ingest, one normalized contract and atomic
   promotion-to-custody with H1/H2/H3 verification.
4. **R07** establishes the governed candidate-to-fact and legal-eligibility authority transitions.
5. **R05/R06/R08** project only eligible material into Weaviate, Neo4j and geo-native surfaces,
   returning exact PG receipts.
6. **R09** independently reconciles every sister-store receipt and issues one fail-closed manifest.
7. **R10/R11** build production Surreal aggregation and paired walks/delta from that manifest.
8. **R13** binds each independently tracked operation into Temporal and keeps n8n at visual
   coordination boundaries.
9. **R12/R14** prove legal/Workbench consumption, live security, horizon isolation, completeness,
   retry/replay and rollback before cutover.

## Live-verification requirements

R14 must independently capture and attest:

- deployed SHA/branch/watch paths and manifest parity for every load-bearing Coolify app;
- current PG relations/functions/triggers/roles/grants/RLS plus `app.evidence_live`;
- direct unauthenticated Weaviate/Graphiti denial and role-separated service identities;
- native Weaviate alias/schema/object counts, exact source anchors and future-fact canaries;
- n8n imported workflow IDs, credentials, activation and webhook authentication;
- Temporal worker image/version/manifest, registered workflows/activities and restart/retry proofs;
- Semantica/Neo4j, geo and R09 receipt/manifests once implemented;
- production Surreal rebuild/revoke/resume/seal/rewalk and paired-delta evidence;
- mandatory integration test execution with a failure if all tests are skipped.

Until those proofs exist, repository comments and dated handoffs are evidence for their dates only,
not claims about current live state.
