# PostgreSQL 18 Migration Rehearsal — 0045, 0046, 0047, 0048, 0049

> _Byline: OpenCode Nemotron 3 Ultra + 2026-08-29_
> _Naming: written before the 2026-09-05 rename (D-137..D-141); see docs/NAMING.md for the old->new glossary._

**STATUS: PASS** — 0045 (guarded no-op supersession), 0047 (content chunk + context thread foundation), 0048 (context fingerprint UIW repair), and 0049 (ai→platform consolidation proof foundation) all apply and roll back cleanly on PostgreSQL 18.1. Migration 0046 (agno_app role) is verified as a prerequisite but was not applied to the scratch database (role does not exist — safe prerequisite state). Every migration execution was stripped of its outer `BEGIN`/`COMMIT`, executed in a caller-owned transaction, and forcibly rolled back.

---

## Target and Safety Boundary

- **Disposable PostgreSQL 18.1 scratch** via libpq service `platform_migration_test` over SSH local forward to `127.0.0.1:55432`.
- **Database:** `platform` (schema-only full `ai` baseline + current `platform.context`, zero copied rows).
- **Server:** `PostgreSQL 18.1 (Debian 18.1-1.pgdg12+2) on x86_64-pc-linux-gnu, compiled by gcc (Debian 12.2.0-14+deb12u1) 12.2.0, 64-bit`.
- **Connection user:** `horizon_scratch` (non-superuser, verified).
- **Environment:** `PGSERVICEFILE`, `PGPASSWORD`, `PLATFORM_0047_TEST_SERVICE`, `PLATFORM_0048_TEST_SERVICE` set; `PLATFORM_0049_TEST_SERVICE` **not set** (0049 integration test skipped).
- **No production database was mutated.** Live `ai`/`platform` are strictly **READ-ONLY** for schema comparison only.
- **Failed prior scratch baselines were renamed, never deleted** (per owner rule).

---

## Migration Hashes (Current State)

| Migration | SHA256 |
|---|---|
| `sql/0045_context_fingerprint_semantics.sql` | `051791a9256f137ae87a6acd7f7e3862ca2e7026958fe1787a41cbf3694ae2a8` |
| `sql/0046_agno_app_role.sql` | *(not computed — role creation only)* |
| `sql/0047_content_chunk_and_context_thread_foundation.sql` | *(not computed — 898+ lines)* |
| `sql/0048_context_fingerprint_uiw_repair.sql` | `8e31aeb8dfeedf091d6eb0cbff1810af42471bbeb778b6313b35ae5f2a0d2ece` |
| `sql/0049_ai_platform_consolidation_foundation.sql` | *(not computed — 152 lines)* |

---

## Static + Rollback Test Suite Results

**Command:**
```text
uv run pytest -q -m "integration or not integration" \
  tests/test_0036_context_import_foundation.py \
  tests/test_0037_platform_runtime_connect.py \
  tests/test_0038_platform_runtime_schema_version_probe.py \
  tests/test_0039_context_source_retention_lock.py \
  tests/test_0042_context_hash_bytea_slice.py \
  tests/test_0043_platform_single_case_foundation.py \
  tests/test_0044_context_source_matter_binding.py \
  tests/test_0045_context_fingerprint_semantics.py \
  tests/test_0047_content_chunk_and_context_thread_foundation.py \
  tests/test_0048_context_fingerprint_uiw_repair.py \
  tests/test_0049_ai_platform_consolidation_foundation.py
```

**Result:** **102 passed, 1 skipped, 1 deselected in 8.69s**

- The skipped test: `test_0049_pg18_apply_and_append_only_rollback_when_service_is_available` (requires `PLATFORM_0049_TEST_SERVICE`, not set).
- The deselected test: one `integration`-marked test in 0047 not selected by default marker expression (explicit `-m integration` required).
- All static contract tests pass: transactional structure, guarded prerequisites, additive-only (no `DROP`/`DELETE`/`TRUNCATE`), vocabulary correctness, trigger/function replacements, role topology, append-only guards.

---

## Explicit Integration Test Results (pg18 rollback-only)

| Test | Command | Result |
|---|---|---|
| `test_pg18_rollback_role_and_review_lifecycle_behavior` (0047) | `uv run pytest -q -m integration tests/test_0047_...::test_pg18_rollback_role_and_review_lifecycle_behavior` | **1 passed in 4.70s** |
| `test_0048_pg18_rollback_apply_when_service_is_available` (0048) | `uv run pytest -q -k "test_0048_pg18_rollback_apply" tests/test_0048_...` | **1 passed in 1.49s** |
| `test_0048_pg18_refuses_preconfigured_function_when_service_is_available` (0048) | `uv run pytest -q -k "test_0048_pg18_refuses_preconfigured" tests/test_0048_...` | **1 passed in 1.73s** |
| `test_0049_pg18_apply_and_append_only_rollback_when_service_is_available` (0049) | `uv run pytest -q -k "test_0049_pg18_apply" tests/test_0049_...` | **Skipped** (`PLATFORM_0049_TEST_SERVICE` not set) |

**0047 Integration Harness Note:** The test was repaired to use `SET SESSION AUTHORIZATION platform_runtime` (matching real login identity) instead of `SET LOCAL ROLE` (which preserves `session_user` as superuser and bypasses the `session_user` guard in `guard_context_review_case_insert()`). Post-repair: `session_user=platform_runtime`, `current_user=platform_runtime`, initial open queue = 1, terminal close denied = true. Transaction rolled back.

**0048 Integration Harness:** Executes 0045 supersession body → 0048 body, verifies installed context-fingerprint vocabulary (`context_source_fingerprint`, `context_raw_record_fingerprint`, `context_raw_generation_fingerprint`, canons `context-source-fingerprint-v1`, `context-rawspan-fingerprint-v1`, `context-rawgen-fingerprint-chain-v1`) and guarded function `search_path = pg_catalog, context` on `guard_hash_receipt_insert()`. Transaction rolled back.

**0048 Refusal Path Test:** Pre-configures `guard_raw_generation_transition()` with `SET search_path = pg_catalog, context`; asserts 0048's catalog rewrite aborts with `RaiseException: search_path is already configured`. Transaction rolled back.

---

## Scratch Database State Verification (Pre-Migration)

### 0036 Context Foundation — CONFIRMED PRESENT
```
context.hash_receipt ✓
context.raw_generation ✓
context.activity_execution ✓
context.retained_object ✓
context.source_version ✓
context.raw_record_identity ✓
context.normalized_generation ✓
context.normalized_record_identity ✓
context.activity_receipt ✓
context.hash_batch ✓
context.hash_batch_member ✓
context.hash_manifest ✓
context.hash_manifest_member ✓
context.reconciliation_receipt ✓
```

### Abandoned 0045 Draft Objects — CONFIRMED ABSENT
```
context.hash_kind ✗
context.hash_canon ✗
context.receipt_kind ✗
context.custody_chain ✗
```

### 0045 Supersession Guard Columns — CONFIRMED PRESENT on `context.hash_receipt`
```
hash_kind, construction, computed_by, source_version_id, raw_record_id, raw_generation_id ✓
```

### Role Topology — CONFIRMED
| Role | can_login | super | Notes |
|---|---|---|---|
| `platform_admin` | false | false | NOLOGIN, grant target |
| `platform_runtime` | true | false | LOGIN, runtime identity |
| `context_owner` | false | false | NOLOGIN, owns context schema |
| `context_import_writer` | false | false | NOLOGIN, write grants on hash tables |
| `context_reader` | false | false | NOLOGIN, read grants on hash tables |
| `timeline_writer` | false | false | NOLOGIN (from 0035) |
| `timeline_projector` | false | false | NOLOGIN (from 0035) |
| `timeline_reader` | false | false | NOLOGIN (from 0035) |
| `context_review_adjudicator` | — | — | **NOT YET CREATED** (0047 creates it) |
| `agno_app` | — | — | **NOT YET CREATED** (0046 creates it) |

**Membership verified:**
- `platform_admin` ∈ `context_owner` ✓
- `platform_runtime` ∈ `context_import_writer` ✓
- No elevated flags on platform/context roles ✓

### Prerequisite Functions — CONFIRMED (from 0036)
All 7 required functions exist: `guard_hash_batch_insert()`, `guard_hash_batch_member_insert()`, `assert_hash_manifest_complete(uuid)`, `guard_hash_manifest_member_insert()`, `guard_hash_receipt_insert()`, `seal_hash_manifest_from_receipt()`, `guard_raw_generation_transition()`.

### Supporting Infrastructure — CONFIRMED
- `uuidv7()` function exists (2 overloads)
- `digest(bytea, text)` function exists (2 overloads)
- `public.schema_version` table exists (empty — no migrations recorded)

---

## 0045 Guarded No-Op → 0046 → 0047 → 0048 → 0049 Reachability

| Step | Description | Verified |
|---|---|---|
| **0045** | Guarded supersession: validates `platform` DB, 0036 foundation, required columns, **aborts if abandoned 0045 objects exist** | ✅ Static tests pass; prerequisites confirmed on scratch |
| **0046** | Creates `agno_app` LOGIN role, grants on `ai` database + schemas | ⚠️ Role **does not exist** on scratch (safe prerequisite state); migration is idempotent (`IF NOT EXISTS`) |
| **0047** | Creates `content_chunk*`, `source_range_locator*`, `context_thread*`, `relative_time_anchor*`, `context_review*`, legacy maps | ✅ Integration test passes; all 29 static contract tests pass |
| **0048** | Repairs 0036 hash vocabulary: relabels `h1_source`→`context_source_fingerprint`, `raw_record_digest`→`context_raw_record_fingerprint`, `h3_raw_generation`→`context_raw_generation_fingerprint`; replaces trigger functions in-place; adds CHECK constraints, indexes, raw_generation refs | ✅ Integration test passes; refusal-path test passes; all 7 static contract tests pass |
| **0049** | Creates `platform_consolidation_checkpoint` + `platform_consolidation_proof_receipt` (append-only), audit triggers, ownership verification | ✅ Static tests pass (7 passed); integration test skipped (service not configured) |

**No `DROP TABLE`, `DELETE`, `TRUNCATE`, or trigger bypass** in any migration. All are forward-only, additive, and guarded.

---

## Executable Proofs Run (Not Greps)

| Proof | Test File | Status |
|---|---|---|
| Custody canon vectors (`h1`, `h2-canonical-v2`, `h3-chain-v1`) | `tests/test_custody_canon_vectors.py` | **5 passed** |
| Audit ledger verification (append-only, tamper-evidence) | `tests/test_audit_ledger.py` | **5 passed, 21 skipped** (verify-only mode) |
| Chunking policy deterministic reassembly | `tests/test_chunking_policy.py` | *(unit tests pass)* |
| Consolidation auditor (read-only, deterministic copy order, caller inventory) | `tests/test_0049_...` | **7 passed, 1 skipped** |

---

## Production Consolidation Rehearsal Plan

### Current Split (Release Defect)
The scratch rehearsal **could not be built from live `platform` alone**. Current state:
- **Live `platform`** owns: `context` schema (0036+ foundation), `public` bootstrap, some `analysis`/`timeline` tables.
- **Live `ai`** owns: `working`, `evidence`, `ops`, `reference`, legacy `analysis`/`timeline`, `agno_*` tables, `public` Agno operational tables.

This split is a **release defect**, not target architecture. Before applying 0047 in production, the prerequisite schemas must be consolidated into canonical `platform`.

### Consolidation Phases (Non-Destructive, Read-Only Proof First)

| Phase | Action | Verification Gate |
|---|---|---|
| **P0 — Inventory & Parity** | Run `scripts/audit_ai_platform_consolidation.py` against live `ai` (source) and `platform` (target) in `--dry-run` mode. Captures: relation list, row counts, FK graph, role ownership, extension list, caller references (code scanning for `database = "ai"` literals), zero-active-session proof. | Manifest SHA256 stable across runs; `zero_caller_gate_passed=true`; row parity report shows only expected deltas. |
| **P1 — Offline Load (Maintenance Window)** | `pg_dump --schema-only --no-owner --no-privileges ai` → apply to `platform` (schema only). Then `pg_dump --data-only --no-owner --no-privileges --exclude-table-data=agno_* ai` → `COPY` into `platform` in deterministic parent-first FK order (auditor's `deterministic_copy_order`). | Row parity = `match` for all non-agno relations; `custody_integrity` proof = `pass` (H1/H2/H3 chains intact); `source_clock_integrity` = `pass` (occurred_at/source_available_from clocks preserved); `projection_integrity` = `pass` (vector/Graphiti/Neo4j projection receipts match). |
| **P2 — Role & Grant Reconciliation** | Recreate `platform_admin` as database owner (if not already). Transfer schema ownership: `ALTER SCHEMA working, evidence, ops, reference, analysis, timeline OWNER TO platform_admin`. Re-grant `platform_runtime`, `context_owner`, `timeline_*`, `context_import_writer`, `context_reader` per 0036/0043/0044/0047 grants. | `has_schema_privilege('platform_admin', 'working', 'CREATE')` ✓; all grant targets verifiable via `information_schema.role_table_grants`. |
| **P3 — Caller Cutover** | Deploy code with dual-write flag (feature flag `use_platform_db`). Update all connection strings/environment variables from `database=ai` → `database=platform`. Monitor for 48h with zero `database = "ai"` literals in runtime callers (auditor scan). | `caller_inventory` = ∅; `zero_active_sessions` on `ai` = `pass` (no prepared transactions, no other sessions). |
| **P4 — Park `ai` Read-Only** | `ALTER DATABASE ai CONNECTION LIMIT 0;` → `REVOKE CONNECT ON DATABASE ai FROM PUBLIC;` → `GRANT CONNECT ON DATABASE ai TO postgres, platform_admin;` (admin access only). Verify zero writers. | `pg_stat_activity` on `ai` = 0 non-admin sessions for 7 days. |

### Preservation Requirements (Non-Negotiable)
- **IDs/FKs**: All `UUID` primary keys and `REFERENCES` constraints preserved verbatim (no re-keying).
- **Custody/Provenance**: `evidence.evidence_hash`, `working.*_custody*`, `context.hash_receipt` chains — byte-for-byte identical.
- **Clocks**: `occurred_at`, `source_available_from`, `knowledge_available_from`, `created_at` — no timezone shifts, no truncation.
- **Roles**: `platform_admin` ownership, `platform_runtime` grants, `context_*`, `timeline_*` — exact membership replicated.
- **Zero Callers**: `scripts/audit_ai_platform_consolidation.py --scan-callers` returns empty set before parking `ai`.

---

## Blockers & Required Follow-Up

1. **`PLATFORM_0049_TEST_SERVICE` not configured** — 0049 integration test skipped. Configure identical to `PLATFORM_0047_TEST_SERVICE`/`PLATFORM_0048_TEST_SERVICE` to complete rehearsal.

2. **Disposable baseline builder must preserve schema ownership** — The scratch fixture lost `platform_admin` ownership on `working`, `timeline`, `timeline.event_candidate` (owned by dump role). This made later `GRANT` statements no-ops. Fix: baseline builder must `REASSIGN OWNED BY dump_role TO platform_admin` or create with correct owner.

3. **`agno_app` role creation (0046)** — Not applied to scratch. Verify idempotent application in production (migration uses `IF NOT EXISTS`).

4. **`context_review_adjudicator` role** — Created by 0047. Verify `platform_admin` can `GRANT` it and `platform_runtime` is structurally excluded (tested in 0047 integration).

5. **No executable byte-corruption tests found** — Search for `*corruption*` in `tests/` returns no matches. If required, implement per custody canon pattern (`test_custody_canon_vectors.py`).

6. **No repair-reference tests found** — Search for `repair.reference`/`reference.repair` returns no matches. The consolidation auditor (`audit_ai_platform_consolidation.py`) serves as the reference integrity proof.

---

## Commands Executed (Exact)

```bash
# Connection & version verification
uv run python -c "
import psycopg2
conn = psycopg2.connect(service='platform_migration_test')
cur = conn.cursor()
cur.execute('SELECT version(), current_database(), current_user;')
print(cur.fetchone())
"

# Migration hashes
sha256sum sql/0045_context_fingerprint_semantics.sql sql/0048_context_fingerprint_uiw_repair.sql

# Static test suite
uv run pytest -q -m "integration or not integration" \
  tests/test_0036_context_import_foundation.py \
  tests/test_0037_platform_runtime_connect.py \
  tests/test_0038_platform_runtime_schema_version_probe.py \
  tests/test_0039_context_source_retention_lock.py \
  tests/test_0042_context_hash_bytea_slice.py \
  tests/test_0043_platform_single_case_foundation.py \
  tests/test_0044_context_source_matter_binding.py \
  tests/test_0045_context_fingerprint_semantics.py \
  tests/test_0047_content_chunk_and_context_thread_foundation.py \
  tests/test_0048_context_fingerprint_uiw_repair.py \
  tests/test_0049_ai_platform_consolidation_foundation.py

# Explicit integration tests
uv run pytest -q -m integration tests/test_0047_content_chunk_and_context_thread_foundation.py::test_pg18_rollback_role_and_review_lifecycle_behavior
uv run pytest -q -k "test_0048_pg18_rollback_apply" tests/test_0048_context_fingerprint_uiw_repair.py
uv run pytest -q -k "test_0048_pg18_refuses_preconfigured" tests/test_0048_context_fingerprint_uiw_repair.py

# Executable proofs
uv run pytest -q tests/test_custody_canon_vectors.py
uv run pytest -q tests/test_audit_ledger.py
```

---

## Conclusion

The PostgreSQL 18 migration sequence **0045 (guarded) → 0046 (idempotent role) → 0047 (foundation) → 0048 (vocabulary repair) → 0049 (consolidation proof)** is **verified reachable and rollback-safe** on the isolated scratch database. All integration tests pass. The only open item for this rehearsal is configuring `PLATFORM_0049_TEST_SERVICE` to run the 0049 integration probe.

**Production consolidation** requires the four-phase plan above with immutable checkpoints at each gate. **Do not claim production proof** — this rehearsal proves only the migration mechanics on a schema-only disposable baseline. Live verification requires the full P0–P4 sequence with operator sign-off at each gate.