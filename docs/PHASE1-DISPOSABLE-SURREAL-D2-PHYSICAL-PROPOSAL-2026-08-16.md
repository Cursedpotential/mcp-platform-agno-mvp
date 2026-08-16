# Phase 1 — Disposable Surreal D2 Physical Proposal

> _Byline: Codex · GPT-5 · 2026-08-16 · official-documentation verification refresh 2026-08-16_
>
> **Status:** OWNER REVIEW — D2 proposal only. This document does not create or authorize a
> target, credential, schema, adapter, deployment, corpus copy, migration, service activation,
> production-agent binding, Graphiti replacement, or E1–E5 adoption.
>
> **Companions:** [logical slice design](PHASE1-DISPOSABLE-SURREAL-SLICE-DESIGN-2026-08-16.md),
> [pre-mortem](plans/R12-PHASE1-DISPOSABLE-SLICE-pre-mortem-2026-08-16.md), and
> [R12 handoff](HANDOFF-2026-08-16-R12-surreal-investigation-owner-rulings.md).

## 1. Recommendation

Use one new, synthetic-only SurrealDB 3.2.3 target named
**`data-surreal-phase1-t0-r1`** on `ovh-files`. Give it a new volume, namespace, database,
credentials, and private Docker network; expose no host or public port. Run a separate,
one-shot adapter/evaluation container on that network. The adapter uses the official Python SDK
2.0.0 in its own dependency environment so the platform's pinned `surrealdb==1.0.8` dependency is
not changed.

The physical model is SCHEMAFULL, append-oriented, Matter-scoped, revision-bound, and protected
by short-lived record-access JWTs. Every eligible evidence, claim, fact, graph edge, and walk
object carries the scope and temporal fields needed to reject an unbound read before ranking or
traversal. The Phase-1 primary vector path is an exact, filtered cosine scan over deterministic
8-dimensional T0 embeddings. An HNSW index may be measured as a challenger, but cannot serve the
as-lived path unless `EXPLAIN FULL`, candidate traces, and planted sentinels prove that eligibility
is applied before approximate ranking.

This proposal is ready for review, not execution. D3 must separately authorize creating the named
target and credentials. D4 must separately authorize schema and adapter implementation and live
T0 testing.

## 2. Authority boundary and inherited holds

The governing sources are [PROJECT_CANON.md](PROJECT_CANON.md), D-064,
[ADR-0056](adr/0056-surrealdb-governed-analytical-and-walk-memory-surface.md),
[ADR-0057](adr/0057-claim-centered-evidence-assembly-and-established-facts.md),
[ADR-0058](adr/0058-investigation-search-and-behavioral-analysis-modes.md), the
[Phase-0 contracts](CONTRACTS-2026-08-16-surreal-investigation-phase0.md), the
[evaluation specification](EVALUATION-2026-08-16-surreal-investigation-phase0.md), and R12.

Every R9 hold remains active:

- migrations `0026`–`0030` and any new production migration remain unapplied;
- canonical-image/full-baseline rehearsal remains held;
- no credential is created, read, rotated, or installed by this proposal;
- exact target creation and deployment authority remains D3;
- physical schema, adapter implementation, and live store proof remain D4;
- production Horizon execution, production-agent binding, and corpus copy remain held;
- parked legacy Surreal remains read-only and untouched;
- the permitted corpus remains T0 synthetic only; and
- Graphiti remains the comparison baseline and is not replaced.

## 3. Exact proposed target

| Property | D2 proposal |
|---|---|
| Experiment ID | `phase1-surreal-t0-slice-r1` |
| Coolify/application name | `data-surreal-phase1-t0-r1` |
| Host | `ovh-files` (`100.91.190.107`; owner-designated replacement for retired `ovh-data`) |
| Server image | `surrealdb/surrealdb:v3.2.3`, resolved to and recorded by immutable digest before D3 |
| Storage engine | RocksDB; SurrealKV is excluded because it is beta |
| Internal endpoint | `ws://data-surreal-phase1-t0-r1:8000/rpc` |
| External endpoint | None; no public domain, proxy route, or host-published port |
| Docker network | New internal network `phase1-surreal-t0-r1`; not external and not shared |
| Container identity | Compose-generated; no fixed `container_name` |
| Namespace | `phase1_surreal` |
| Database | `t0_slice_r1` |
| Shared Context record | `context:phase1_surreal_t0_slice_r1` |
| Host data directory | `/data/agno/experiments/phase1-surreal-t0-r1` |
| Corpus class | T0 fabricated content only |
| Resource ceiling | 2 vCPU, 2 GiB RAM, 2 GiB data-volume budget |
| Lifecycle | Create only after D3; stop, revoke, and quarantine after the run; never auto-delete |

The image tag is a selection, not a mutable deployment reference. Before D3, the packet must add
the registry digest, verify its signature/provenance if available, and recheck current upstream
security advisories. SurrealDB 3.2.3 is chosen because current official Python SDK documentation
lists it as the newest compatible server for SDK 2.0.0, and it includes the fixes disclosed in the
3.1.5 and 3.2.0 security advisories.

### 3.1 Legacy denylist

The proposed target must not use or alias any of these parked legacy identities:

| Parked identity | Forbidden reuse |
|---|---|
| Service/container | `data-surreal`, `surrealdb` |
| Compose authority | `compose.data-surreal.yaml` |
| Endpoint | `ws://100.119.96.29:8000/rpc` or host port `8000` |
| Volume | `/data/agno/volumes/surrealdb` and its RocksDB files |
| Network | external/shared `agno` network or legacy `surreal` network |
| Namespace/database | `agno/platform`, `main/main`, or any discovered legacy namespace/database |
| Credentials | legacy root, namespace, database, or application credentials |

D3 preflight must read-only prove that the proposed application, network, directory, namespace,
database, and credentials do not exist, then separately prove the parked target remains unchanged.
Any ambiguous alias, shared mount, shared secret, or inability to prove negative identity is a
stop condition.

## 4. Runtime and security profile

The target is an isolated single-node experiment, not a production service:

- RocksDB stores only rebuildable T0 projection and walk state in the dedicated host directory.
- The target has no public ingress, host-published port, egress requirement, custom API, guest
  access, JavaScript function, file access, network access, SurrealML import, or package execution.
- The setup boot starts deny-all, permits arbitrary queries for the setup system principal only,
  and permits the minimum functions needed to define and inspect the schema. The runtime boot
  starts deny-all, permits arbitrary queries for record principals only, and allowlists only
  `array::*`, `string::*`, `time::*`, `type::*`, `crypto::sha256`, and
  `vector::similarity::cosine`. Guest, scripting, network, file, custom-function, custom-API,
  SurrealML, and runtime system-query capabilities remain denied. D4 must fail if it needs a
  broader capability.
- The container must run as the image's verified non-root user, with a read-only root filesystem
  where supported, dropped Linux capabilities, `no-new-privileges`, and only its data volume
  writable. The resolved UID/GID is recorded with the image digest before D3.
- Logs contain stable IDs, counts, hashes, and typed failures—not source text, JWTs, credentials,
  prompts, forbidden sentinel text, or embeddings.
- Original binaries remain outside Surreal. `binary_replication` is always `reference_only` in T0.

Because table permissions govern record users rather than privileged system users, no query path
used by projection, investigation, retrieval, walk execution, or evaluation may run as root,
OWNER, EDITOR, or VIEWER. A bootstrap database owner may define schema and access methods during
a future D4 setup, but its secret is then removed from the runner and unavailable to tests.

## 5. Credential and access design

No credential value is selected here. D3 creates unique random material only after approval.

| Principal | Authentication | Allowed actions | Explicit denials |
|---|---|---|---|
| `phase1_bootstrap` | Database-scoped system user, setup-only | Define schema, indexes, access method, and initial principal records | No runtime mount; no corpus; removed from runner after setup |
| `phase1_projector` | Externally signed record-access JWT | Insert T0 projection rows/edges and receipts for one Matter/revision; update its projection guard | No schema, delete, cross-revision read, walk, fact review, or broad query |
| `phase1_investigator` | Externally signed record-access JWT | Read eligible rows; append plans, hits, expectations, dossiers, and candidate relations for one run | No fact establishment, projection mutation, or other walk/run |
| `phase1_reviewer` | Externally signed record-access JWT | Read one frozen dossier; append a synthetic review/fact and exact evidence links | No dossier refresh, corpus mutation, or release authority |
| `phase1_walk` | Externally signed record-access JWT | Read one bound HorizonContext; append steps, beliefs, states, guards, and snapshots for one walk | No unbound read, hindsight widening, other walk, fact review, or fallback |
| `phase1_auditor` | Externally signed record-access JWT | Read manifests, receipts, traces, snapshots, and evaluation objects in one Matter/revision | No write |

The database defines one RECORD access method with an external RS256 public key. The signing
private key remains outside the target and runner. Tokens expire in five minutes, sessions are
limited to fifteen minutes, and every token binds `iss`, `aud`, `jti`, `exp`, `ns`, `db`, `ac`,
`id`, `role`, `matter_id`, `run_id` or `walk_id`, `horizon_id`, `horizon_at`, `mode`,
`projection_revision`, `policy_version`, and `policy_hash`. Missing, malformed, widened, or
mismatched claims fail as `UNAUTHENTICATED`, `FORBIDDEN`, `SCOPE_MISMATCH`, or
`HORIZON_VIOLATION`; they never become an empty success.

The `$auth` record must be an enabled `service_principal` whose allowed role and experiment ID
match the token. Table permissions independently compare token scope with row scope. System JWTs
and experimental bearer grants are excluded because system users bypass row-level permissions
and bearer grants are not an appropriate critical boundary for this slice.

## 6. Physical schema conventions

All tables are SCHEMAFULL. Unknown fields fail. All public IDs are platform-owned strings;
Surreal record IDs are typed projection locators only. Records use UTC datetimes and explicit
`option<datetime>` fields rather than sentinel dates.

Every scoped material table carries this physical envelope unless the catalog narrows it:

```text
platform_id, contract_name, contract_version, matter_id, court_case_id?,
created_at, created_by, revision, supersedes_id?, authority_state,
policy_version, policy_hash, trace_id, projection_revision, canonical_content_hash
```

Every searchable or traversable evidence-bearing row additionally carries:

```text
promotion_state, exposure_scope, visible_from?, disclosure_tier,
source_family_id, sensitivity_tier, projection_guard_id
```

`knowledge_time` and `recorded_time` may be retained for audit but are never indexed or accepted
as horizon predicates. Realization intervals retain `realized_earliest`, `realized_latest`,
`midpoint_proposed`, and `realization_decision_id`; `visible_from` remains absent until an
attributable approval permits it.

### 6.1 Exact table catalog

| Table | Key fields beyond the envelope | Mutation rule |
|---|---|---|
| `context` | `environment`, `corpus_tier`, `experiment_id` | Create once; never edit/delete |
| `matter_scope` | `context_id`, `allowed_subject_ids`, `scope_hash` | Append revisions only |
| `service_principal` | `experiment_id`, `allowed_roles`, `enabled` | Bootstrap/revocation control only |
| `projection_revision` | `context_id`, `membership_hash`, `content_hash`, `adapter_version`, `source_manifest_hash` | Append revisions only |
| `projection_guard` | `revision_id`, `status`, `reconciled_hash`, `quarantine_reason?`, `checked_at` | Projector may transition `building` → `active` → `quarantined`; never back to active |
| `projection_receipt` | `target_id`, `native_locator`, `canonical_input_ids`, `object_counts`, `checkpoint`, `status` | Append only |
| `source_manifest` | `source_id`, `h1_sha256`, `byte_size`, `media_type`, `custody_version`, `normalization_revision`, `content_exposure`, `binary_replication` | Append revisions only |
| `promoted_span` | `span_id`, `source_revision_id`, `typed_locator`, `normalized_text`, `content_binding_hash`, temporal fields, `promotion_decision_id` | Append only |
| `normalized_representation` | `source_revision_id`, `normalizer_version`, `normalized_text`, `structure_hash` | Full-text exposure only; append only |
| `structural_atom` | `atom_id`, `source_revision_id`, `parser_version`, `typed_locator`, `atom_text`, `atom_hash` | Append only |
| `retrieval_chunk` | `chunk_id`, `generation`, `atom_ids`, `chunk_text`, `chunk_hash`, `chunk_policy_version` | Append generations only |
| `embedding_t0_v1` | `embedding_id`, `chunk_id`, `profile_id`, `provider`, `model`, `dimensions=8`, `numeric_type=f32`, `normalization`, `input_hash`, `vector` | Append only; T0 profile only |
| `claim_candidate` | proposition structure/text, subjects/predicate/objects, qualifiers, origin IDs, confidence, candidate state | Append only; never fact |
| `analysis_scope` | subjects/roles, date ranges, selected IDs, exclusions, revisions, mode, expansion budgets, `scope_hash` | Append revisions only |
| `investigation_plan` | questions, aliases, requirements, independence rules, ordered stages, budgets, stop conditions, expected gaps, `plan_hash` | Freeze before execution |
| `claim_investigation` | candidate IDs, scope/plan IDs, authority floor, horizon mode, versions, termination | Append run revisions only |
| `evidence_hit` | investigation/step IDs, exact source/span/chunk IDs, surface, eligibility proof/hash, profile score/rank, class, reason, family ID | Append only |
| `evidence_expectation` | expected kind/source/time/actor, search coverage, absence confidence | Append only; never fabricates a span |
| `fact_dossier` | claim/plan IDs, selected/rejected hit IDs, contradictions, alternatives, gaps, budgets, limitations, family analysis, `dossier_hash`, frozen time | Immutable after freeze |
| `established_fact` | atomic assertion, dossier ID/hash, review decision ID, reviewer, decision time | Append/supersede only; never court-release state |
| `horizon_context` | walk/run/role/mode, subject, horizon instant/policy, floors, version map, manifest/activation hashes, allowed/excluded IDs | Immutable |
| `walk` | run/role/mode, schedule hash, initial horizon, projection/policy bindings, `rewalk_of?` | Identity record; append only |
| `walk_step` | walk ID, sequence, horizon ID, observed time, eligible manifest/hash, input/output state hashes | Append-only monotonic sequence |
| `walk_guard` | walk ID, current step, status, projection guard, pause/failure reason | Coordinator transitions only; sealed is terminal |
| `belief_event` | walk/run/role/horizon IDs, event kind, proposition, upstream IDs, decision/observation times, uncertainty, versions, prior/event hash | Append-only hash chain |
| `walk_snapshot` | walk/step/horizon IDs, projection/eligible/state hashes, belief IDs, context/trace hashes, versions, failure reason, sealed time | Immutable, non-resumable, excluded from recall |
| `memory_state` | walk/event sequence/horizon, replay manifest, state hash | Append-only derived projection |
| `memory_diff` | left/right state IDs, classified additions/removals/contradictions/supersessions/confidence/realization changes | Append-only report |

### 6.2 Relation tables

| Relation | From → to | Required edge fields |
|---|---|---|
| `fact_evidence` | `established_fact` → `promoted_span` | role, weight/quality, independence group, review rationale, exact hashes |
| `claim_evidence` | `claim_candidate` → `evidence_hit` | classification, investigation ID, reason, trace step |
| `derived_from` | representation/atom/chunk/embedding → upstream object | generation/profile, locator/hash binding |
| `supports` / `contradicts` / `qualifies` | fact/claim → fact/claim | authority class, decision ID, rationale |
| `supersedes` | immutable revision → prior revision | revision decision, reason, decision time |
| `rewalk_of` | new `walk` → sealed `walk` | reconciliation ID, classified change manifest/hash |
| `belief_basis` | `belief_event` → eligible evidence/fact/belief | horizon ID, eligible-manifest hash, basis role |

Every edge repeats `matter_id`, `projection_revision`, `policy_version`, visibility/authority
fields, and the relevant walk ID. Vertex permissions do not substitute for edge permissions;
both endpoints and every traversed edge must pass the bound predicate. The relation tables should
use `TYPE RELATION ... ENFORCED` so writes cannot point at missing records, while the adapter still
validates endpoint type, Matter, revision, policy, visibility, and walk scope. D4 must also prove
exact edge counts and hashes after export/import. `ENFORCED` protects write-time endpoint
existence; it does not by itself prove backup/restore completeness.

### 6.3 Index catalog

| Table | Index |
|---|---|
| Every scoped table | composite lookup on `(matter_id, projection_revision, authority_state)` |
| Evidence-bearing tables/edges | composite eligibility lookup on `(matter_id, projection_revision, promotion_state, disclosure_tier, visible_from)` |
| `projection_guard` | unique `revision_id`; lookup on `(status, checked_at)` |
| `source_manifest` | unique `(source_id, revision)`; lookup on `h1_sha256` |
| `promoted_span` | unique `(span_id, revision)`; lookup on `(source_revision_id, content_binding_hash)` |
| `retrieval_chunk` | unique `(chunk_id, generation)`; lookup on `atom_ids` |
| `embedding_t0_v1` | unique `(chunk_id, profile_id)`; HNSW challenger on 8D F32 cosine |
| `claim_candidate` | unique `(platform_id, revision)`; lookup on origin IDs |
| `evidence_hit` | lookup on `(investigation_id, trace_step, classification)` |
| `walk_step` | unique `(walk_id, sequence)`; lookup on `(walk_id, horizon_id)` |
| `belief_event` | unique `(walk_id, event_hash)`; lookup on `(walk_id, sequence)` |
| Text-bearing promoted rows | one pinned FULLTEXT analyzer/index profile for T0 lexical tests |

The full-text definition uses SurrealQL 3.x `FULLTEXT ANALYZER` syntax, not the pre-3.x `SEARCH
ANALYZER` syntax. Index names, analyzer/tokenizer choices, and generated DDL become frozen D4
artifacts and are hash-attested in the run manifest.

## 7. Permission policy

Every table declares explicit `NONE` by default, then narrowly grants operations to the matching
record principal. There is no table with `FULL` permissions.

For evidence-bearing SELECTs, both row permissions and the submitted query require:

```text
row.matter_id = token.matter_id
AND row.projection_revision = token.projection_revision
AND row.policy_version = token.policy_version
AND row.policy_hash = token.policy_hash
AND row.projection_guard.status = active
AND row.authority_state is permitted
AND row.promotion_state is active
AND row.exposure_scope is permitted
AND disclosure policy permits the row
AND (
  token.mode = hindsight
  OR (token.mode = as_lived_so_far AND row.visible_from exists
      AND row.visible_from <= token.horizon_at)
)
AND, for experiential state, row.walk_id = token.walk_id
```

Projection INSERT permissions require every row field to equal the projector token's Matter,
revision, policy, and experiment scope. Investigation and walk INSERT permissions additionally
require the bound run/walk/horizon and an upstream eligible-manifest hash. Evidence, decisions,
beliefs, dossiers, facts, snapshots, and relation edges deny UPDATE and DELETE. Guard records have
the only narrow state transitions; terminal `quarantined` and `sealed` states cannot transition
back.

No permission expression may perform a write. This avoids a class of permission-side-effect
failures and keeps authorization deterministic. D4 includes direct negative tests for each role,
table, edge, operation, Matter, walk, horizon, and revision boundary.

## 8. Adapter and SDK boundary

The planned adapter is a one-shot evaluation runner, not an AgentOS service and not an Agno
Surreal adapter.

| Property | Proposal |
|---|---|
| Future code home | `docker/surreal-phase1-runner/` with its own `pyproject.toml` and `uv.lock` |
| SDK | Official `surrealdb==2.0.0`, Python 3.12, isolated from the root environment |
| Server connection | Async WebSocket context manager to the internal target endpoint only |
| Query method | Parameterized `query_raw` for multi-statement results; no string interpolation |
| Platform boundary | Implements the Phase-0 framework-neutral ports; returns platform result envelopes and typed failures |
| Endpoint guard | Exact scheme/host/port/namespace/database/context allowlist; deny IP aliases and all production/legacy identities |
| Lifecycle | Connect per bounded run, close deterministically, no background subscriptions after exit |
| Output | Hash-attested JSON reports/receipts with IDs/counts; no secrets or raw sentinel text |

The root `requirements.txt`, `pyproject.toml`, `uv.lock`, `server/core/session.py`, and legacy
`get_surrealdb_legacy` path remain unchanged. The runner receives only a short-lived record JWT
and target identity document. Bootstrap credentials are supplied to a separate setup command and
never enter the runtime/evaluation image.

## 9. Retrieval and prefilter proof

The adapter first compiles the common eligibility predicate into typed parameters. It then asks
the store to produce candidates only inside that set. Post-filtering a global top-k is forbidden.

For the small T0 slice, the authoritative vector test path is:

1. select rows satisfying Matter, projection guard, authority, promotion, exposure, disclosure,
   horizon, and optional walk predicates;
2. compute exact cosine similarity over only those eligible 8D embeddings;
3. order and return the requested eligible `k`; and
4. record the compiled predicate, `EXPLAIN FULL` plan, eligible count, ranked candidate IDs, and
   returned count before any reranker or prompt.

The HNSW challenger uses identical bindings. It is rejected for as-lived use if the plan or
sentinel trace cannot prove eligibility before approximate candidate selection, even when final
results look clean. Lexical and graph paths follow the same rule: candidate/edge expansion traces
must show zero forbidden IDs and must return the later/hindsight positive controls. A result that
returns nothing is not proof of safety.

No cache, profile, summarizer, subscription, consolidation job, custom API, or server-side
function participates in the as-lived path. If later introduced, it requires its own bound scope
fields, negative tests, and D2 revision.

## 10. Projection, walk, and failure sequence

1. The fixture-backed canonical port freezes T0 decisions, membership, hashes, and expected
   eligibility without contacting production PostgreSQL.
2. The projector writes a new `projection_revision` in `building` state, projects only the
   permitted manifest/text/spans/relations, reconciles membership/content/edge hashes, appends a
   receipt, and transitions the guard once to `active`.
3. Every investigation and walk token names that active guard and immutable HorizonContext.
4. Investigation freezes its plan, records all retrieval stages and rejected hits, freezes the
   dossier, and requires the synthetic reviewer principal to establish a fact.
5. Walk steps append eligible manifests, retrieval traces, belief-event hashes, and memory states.
6. Revocation, stale hash, missing/extra membership, invalid edge, scope mismatch, or target outage
   stops reads, transitions the projection guard to `quarantined`, pauses the walk, and seals an
   immutable snapshot.
7. Reconciliation builds a new projection revision. It never repairs the old projection in place.
   A new walk links through `rewalk_of`; the old snapshot stays excluded from active recall.
8. No Surreal failure triggers evidence retrieval from PostgreSQL, Weaviate, Neo4j, Graphiti, or
   another walk. Graphiti is exercised only as the separately isolated comparison baseline.

## 11. Stop and quarantine plan

At the first kill-gate failure or at experiment completion:

1. stop new tokens and revoke the signing key/JWT audience for this experiment;
2. stop the runner and database application without deleting the application, volume, or files;
3. preserve logs, manifests, receipts, hashes, first-failing traces, and resource measurements;
4. mark the target `QUARANTINED — NOT FOR REUSE` in the handoff and Coolify metadata;
5. leave `/data/agno/experiments/phase1-surreal-t0-r1` intact and inaccessible;
6. prove the parked target and unrelated services remain unchanged; and
7. request owner direction for any later movement into `to_be_deleted` or disposal.

There is no automated `DROP`, volume removal, recursive deletion, or destructive cleanup. A
failed target is never renamed and reused as the next revision.

## 12. D3 and D4 proof packets

### D3 — target and credential creation authority

D3 must provide, before any creation:

- read-only absent/new proof for every proposed identity plus unchanged proof for the legacy
  denylist;
- immutable server image digest, verified non-root UID/GID, current advisory review, and storage
  capacity check;
- exact Coolify/Compose diff, internal-network proof, zero-ingress proof, and resource limits;
- credential names, generation/rotation/revocation procedure, public-key fingerprint, and secret
  mount map without secret values; and
- explicit owner authorization to create only this target and its synthetic-only credentials.

### D4 — schema, adapter, and live T0 authority

D4 must provide, before implementation or execution:

- reviewed SurrealQL schema/access/index files and generated schema hash;
- a failing-first test map covering E0–E9, HF-01–HF-12, every role/operation, positive controls,
  `EXPLAIN FULL`, export/restore edge counts, and the pre-mortem faults;
- the isolated runner dependency lock and endpoint guard tests;
- a frozen T0 manifest with no real source identifiers or text;
- exact run budgets and report locations; and
- explicit owner authorization to implement and run only the approved T0 slice.

No D3 or D4 approval implies production adoption, migrations, corpus copy, Horizon activation,
agent binding, Graphiti replacement, or any owner-packet E1–E5 choice.

## 13. Physical pre-mortem additions

The companion pre-mortem remains normative. D2 adds these physical failure modes:

| Failure | Earliest warning | Kill gate |
|---|---|---|
| SDK 2.0 contaminates the platform dependency graph | Root lockfile or imports change | Stop; keep runner lock isolated |
| Record query accidentally uses a system user | `$auth` absent or system role appears in trace | Stop before first corpus write/read |
| ANN ranks globally then filters | `EXPLAIN FULL` or candidate trace includes forbidden IDs | Reject ANN path and quarantine result |
| Permission protects vertices but not edges | Cross-scope edge appears during traversal | Stop; require edge and endpoint checks |
| Projection quarantine races a live token | Read succeeds after guard becomes quarantined | Seal walk; fail D4 concurrency gate |
| Export/import omits or changes relation edges | Edge count/hash differs after import | Fail reproducibility; no success claim |
| “Internal” target becomes externally reachable | Published port, proxy label, or shared network appears | Stop deployment and quarantine target |
| Bootstrap secret remains in runtime | Secret inventory shows it in runner/app | Stop; revoke/rotate before testing |
| Disposable volume is auto-removed | Teardown contains delete/drop/volume removal | Stop; replace with stop-and-quarantine |

## 14. External technical basis

### 14.1 Verification refresh — 2026-08-16

The following time-sensitive assumptions were rechecked against current official documentation
without contacting or creating any Surreal target:

- SurrealDB `3.2.3` remains the latest stable server release.
- Python SDK `2.0.0` remains the latest documented SDK and declares compatibility with server
  versions `2.0.0` through `3.2.3`.
- RocksDB remains the recommended storage engine for single-node server workloads; SurrealKV
  remains beta.
- table/field permissions apply to RECORD users and not privileged system users; externally
  issued JWTs can enter the RECORD permission boundary through `TYPE RECORD WITH JWT`.
- filtered HNSW/DISKANN queries can push predicates into `KnnScan` on supported 3.1.5+ servers;
  the required proof is the predicate in `EXPLAIN` plus planted-candidate traces, not clean final
  results alone.
- `TYPE RELATION ... ENFORCED` is documented in 3.2 as rejecting relations whose endpoints do not
  exist. No official source was found for the prior draft's claim that pre-3.3 export/restore
  silently drops enforced edges, so that claim has been removed. Export/import parity remains a
  mandatory independent gate.

Image digest, signature/provenance, current advisory disposition, and effective runtime
capabilities remain D3 preflight evidence because they depend on the exact artifact selected at
that later time.

- [Official Python SDK reference](https://surrealdb.com/docs/reference/python) — SDK 2.0.0,
  supported Python versions, and server compatibility.
- [Python connection guidance](https://surrealdb.com/docs/languages/python/concepts/connecting-to-surrealdb)
  and [query execution guidance](https://surrealdb.com/docs/languages/python/concepts/executing-queries)
  — async lifecycle and parameterized queries.
- [Python `query` method](https://surrealdb.com/docs/sdk/python/methods/query) — `query_raw` for
  complete multi-statement results.
- [Deployment guidance](https://surrealdb.com/docs/build/deployment) — RocksDB for a single-node
  server workload and SurrealKV beta status.
- [Table definitions](https://surrealdb.com/docs/learn/schema-management/tables-and-fields/tables)
  and [index definitions](https://surrealdb.com/docs/reference/query-language/statements/define/indexes)
  — SCHEMAFULL behavior, `TYPE RELATION ... ENFORCED`, current full-text/vector syntax, and
  `EXPLAIN` planning evidence.
- [Record access](https://surrealdb.com/docs/reference/query-language/statements/define/access/record),
  [JWT access](https://surrealdb.com/docs/reference/query-language/statements/define/access/jwt), and
  [row-level permissions](https://surrealdb.com/docs/learn/security/authorization/permissions-and-row-level-security)
  — record identities, JWT claims, and the system-user/RLS boundary.
- [Capabilities](https://surrealdb.com/docs/learn/security/authorization/capabilities) and
  [security best practices](https://surrealdb.com/docs/surrealdb/reference-guide/security-best-practices)
  — deny-all, least privilege, and restricted runtime capabilities.
- [Official security advisories](https://github.com/surrealdb/surrealdb/security/advisories) —
  recheck immediately before resolving the D3 image digest.

## 15. Owner decision requested

Approve, revise, or reject this D2 proposal as a design packet. Approval of D2 means only that
this is the physical plan to carry into D3/D4 review. It does not authorize creating the named
target or credentials, implementing the schema/adapter, contacting a live Surreal service, or
running the T0 slice.
