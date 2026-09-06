# BUILD LANE S1 — UIW schema admission unblock

> _Byline: Claude Code · Sonnet 5 · 2026-09-02._
> _Naming: written before the 2026-09-05 rename (D-137..D-141); see docs/NAMING.md for the old->new glossary._

Scope: unblock the universal-import-worker's fail-closed `ProbeUIWSchema` gate
(`modules/engine/postgres/uiw_schema_probe.go`), which crash-loops the worker
with `UIW schema admission: catalog verification unavailable`. Deliverable:
`sql/0066_uiw_runtime_admission_grants.sql`. No Go source touched. No commit
made — the orchestrator applies after review.

## TL;DR

- The crash is a real `permission denied for schema registry` error from the
  probe's own query, reproduced live as `platform_runtime`. `sql/0066` grants
  exactly the three missing schema-USAGE privileges (`registry`, `raw`,
  `evidence`) plus the two table/column grants the runtime pipeline actually
  uses (`raw.raw_csv` SELECT/INSERT, `ops.migration_ledger(migration_id)`
  SELECT). Zero-net-write validated: applying it, in the same uncommitted
  transaction, turns the crash into a clean non-crashing query result, then
  rolled back.
- That non-crashing result is **still a fail-closed rejection**, for reasons
  entirely outside grants: `ledger=0/9`, `constraints=false`,
  `receipt=false`. These are a Go query-target bug and live schema/data drift.
  `sql/0066` does not and should not touch them — see **What remains
  blocking** below.

## 1. Probe requirement matrix — expected vs actual (live, 2026-09-02)

`modules/engine/postgres/uiw_schema_probe.go` runs one query and scans 11
values. Read in full before any of this; line numbers below refer to it.

| # | Check (Go var) | What it requires | Live actual (superuser bypass) | Verdict |
|---|---|---|---|---|
| — | connection itself | query must not error | **errors** for `platform_runtime`: `permission denied for schema registry` (SQLSTATE 42501) on the `'registry.matter'::regclass` / `'registry.court_case'::regclass` casts inside the FK-identity check (lines 83, 86). PostgreSQL gates schema-qualified regclass/type resolution on schema USAGE even when no row is ever selected. | **This is the crash.** Everything below is unreachable until this is fixed. |
| identity | `database`, `current_user`, `databaseOwner` | `platform` / `platform_runtime` / `platform_admin` | exactly that | pass |
| `ledgerCount` | count of 9 migration_ids in `public.schema_version` with `status='active'` | `= 9` | **`0`** — `public.schema_version` has **zero rows total**, for any migration | **fail**, see §3 |
| `tableCount` | 36 required tables exist | `= 36` | `36` | pass |
| `columnCount` | 16 required columns exist | `= 16` | `16` | pass |
| `constraintsExact` | 5 exact-shape FKs (all `convalidated`) + 2 CHECKs + 1 UNIQUE, all validated, on `context.source_version` / `context.uiw_source_context_revision` referencing `registry.matter` / `registry.court_case` | `true` | **`false`** — see §4 | **fail**, out of grants scope |
| `substrateExact` | 4 named CHECK constraints from 0048, all validated | `true` | `true` | pass |
| `roleSafe` | `platform_runtime` is a safe LOGIN role and a member of `context_import_writer` | `true` | `true` | pass |
| `grantsExact` | `analysis` schema USAGE (not CREATE) + SELECT on 4 named tables, no INSERT/UPDATE/DELETE on `registry.matter`/`public.schema_version`, `agno_app` not over-privileged | `true` | `true` (all already granted by 0054) | pass |
| `receiptExact` | exactly 1 row in `analysis.case_registry_import_receipt` matching 11 hardcoded constants | `true` | **`false`** — table has **0 rows** | **fail**, see §2 |

Live privilege gaps found for `platform_runtime` (all fixed by `sql/0066`,
zero-net-write proven in §5):

| Object | Privilege needed | Before | After (in-transaction) |
|---|---|---|---|
| `SCHEMA registry` | USAGE | false | true |
| `SCHEMA raw` | USAGE | false | true |
| `TABLE raw.raw_csv` | SELECT, INSERT | false, false | true, true |
| `SCHEMA evidence` | USAGE | false | true |
| `SCHEMA ops` | USAGE | false | true |
| `TABLE ops.migration_ledger` | SELECT (migration_id) | false | true |

`registry.matter` / `registry.court_case` SELECT and all of 0054's
`analysis`-schema grants were **already correct** live — only schema-level
USAGE was missing on `registry`. `raw` and `evidence` USAGE were missing for
a second, independent reason (see §5, "why `raw`/`evidence` are in scope").

## 2. Receipt provenance verdict

Task: determine the authoritative source of the `case_registry_import_receipt`
row and check the probe's 8 hardcoded provenance constants against it.

**Verdict: the manifest is authoritative and internally verified — no
mismatch.** `sql/validation/0054_platform_case_registry_adoption.json` is
that manifest (it is the exact `--registry-import` payload
`scripts/apply_0054_live.py` / `scripts/validate_0054_live.py` expect, per
`load_registry_manifest()`), and every provenance field in it is byte-for-byte
what `uiw_schema_probe.go` hardcodes:

```
$ sha256sum sql/0030_matter_case_foundation.sql
b19959119c0f040adcdc442aa7772503fd2d1439a90b1565eaa6c17e0883eb70   (16219 bytes)
```

matches `registrySourceMigrationSHA256` in the probe exactly, and the
manifest's `source_git_commit`, `payload_schema_version`,
`payload_byte_length` (1075), `canonical_payload_sha256`, and
`api_payload_sha256` are the literal source of the probe's other 5 constants
(they were clearly copied from this file when the probe was written). This
manifest is ready to use — the blocker is not its content.

**The blocker is that the row was never (re-)inserted, and the identity it
names no longer matches live data:**

- `analysis.case_registry_import_receipt`: **0 rows**, live-confirmed.
- `analysis.matter` / `analysis.court_case` (0054's original DDL target
  tables) **no longer exist** (`to_regclass` returns `NULL` for both) — they
  were consolidated into `registry.matter` / `registry.court_case` by an
  undocumented reconciliation sometime after 0054 was first applied (not by
  migration 0058, which is scoped to `working`/`evidence`/`raw`, not to
  `analysis`/`registry`).
- `registry.matter` currently holds **exactly one row** — "Primary matter",
  `status='active'` — but its `id` is `01a055b0-c172-7d66-87e6-0d3be2bdfb35`,
  **not** the authoritative `01a03136-c5cc-71c7-ac77-5c00a29a2ea8` the probe
  and the manifest both name. `registry.court_case` has the matching
  single-row problem (`01a055b0-c173-...` vs. authoritative
  `01a03136-c5cc-76f9-98df-702058d423d9`). These look like fresh
  `uuidv7()`-default rows created by whatever process rebuilt the schema
  (matching timestamp: `ops.migration_ledger` shows 0054 "applied"
  2026-08-31T03:27:03Z by `claude-opus-5 rebuild 2026-08-30`), not a replay of
  the original adoption.
- `analysis.matter_knowledge_partition`: **0 rows** (0054 requires exactly 1,
  `partition_key='primary'`).
- The live `case_registry_import_receipt` table's own FKs already point at
  `registry.matter` / `registry.court_case` (not `analysis.matter` /
  `analysis.court_case` as the git-committed `sql/0054_platform_case_registry.sql`
  still declares) — the checked-in 0054 file is stale relative to the live
  schema shape.

**Per the task instruction, the receipt seed is left OUT of `sql/0066`.**
Seeding it correctly requires either (a) replacing the live
`registry.matter`/`registry.court_case` rows with the authoritative
`01a03136-...` identities the manifest and probe name, or (b) treating the
current `01a055b0-...` rows as the new authority and updating the probe's
Go constants and the manifest to match. Both are identity-authority decisions
on canonical case-registry data — squarely an owner call, not something a
grants migration should paper over.

## 3. `ledgerCount=0` — a Go query-target bug, not a grants gap

`uiw_schema_probe.go` queries `public.schema_version`. Live-verified: that
table has the right columns (`migration_id`, `status`, ...) but **zero rows,
period** — not just for our 9 migrations, for anything.

Migration `sql/0055_graph_lane_provenance_and_graphrag_recovery.sql` (Part 5,
its own comment, verbatim) explains why:

> "`public.schema_version` is NOT a migration ledger and never was... That
> resemblance has now cost real time twice. On 2026-08-29 a `CREATE DATABASE
> platform TEMPLATE ai` inherited `schema_version` from the source database...
> roughly seven hours went into reconstructing it by hand."

0055 created `ops.migration_ledger` specifically as "THE migration ledger."
Live-verified: `ops.migration_ledger` has **61 rows**, including all 9 of the
probe's required migration_ids (`0036`, `0037`, `0038`, `0039`, `0042`,
`0050`, `0051`, `0053`, `0054`, each `applied_by='claude-opus-5 rebuild
2026-08-30'`).

**This directly corroborates the orchestrator's brief** ("the probe reads
`ops.migration_ledger`") as the *intended* architecture — but the code at
`uiw_schema_probe.go` predates or was never updated to match 0055's ruling,
and still points at the wrong table. Per this task's instructions, Go source
is untouched; `sql/0066` grants `USAGE ON SCHEMA ops` and `SELECT
(migration_id) ON ops.migration_ledger` to `platform_runtime` as
forward-provisioning only, so a corrected probe query is not blocked by a
second missing grant the moment someone fixes the Go.

## 4. `constraintsExact=false` — live DDL drift from the committed 0054

The probe requires 5 FKs (all `convalidated`), 2 CHECK constraints, and 1
UNIQUE constraint, all exact-shape. Live state (superuser query,
`pg_constraint`):

| Constraint | Exists live? | Validated? |
|---|---|---|
| `source_version_matter_case_pair_check` (CHECK) | yes | yes |
| `source_version_court_case_scope_fk` (FK → `registry.court_case`) | yes | yes |
| `uiw_source_context_scope_key` (UNIQUE) | yes | yes |
| `source_version_source_context_scope_fk` (FK) | yes | **no** |
| `uiw_source_context_matter_fk` (FK → `registry.matter`) | yes | **no** |
| `uiw_source_context_court_case_scope_fk` (FK → `registry.court_case`) | yes | **no** |
| `source_version_matter_fk` (FK → `registry.matter`) | **missing entirely** | — |
| `source_version_source_context_scope_check` (CHECK) | **missing entirely** | — |

Two of 0054's eight constraints do not exist at all; three more exist but
were never `VALIDATE CONSTRAINT`-ed (they were added `NOT VALID` by 0054's
DDL, and `scripts/validate_0054_live.py`'s `validate_scope_constraints()`
step — which runs `ALTER TABLE ... VALIDATE CONSTRAINT` — evidently never ran
against the live tree in its current shape). All the surviving FKs already
target `registry.matter`/`registry.court_case`, consistent with §2's finding
that `analysis.matter`/`analysis.court_case` were retired and consolidated
into `registry.*` after 0054 was first written. This is DDL/data repair
work, not a grants gap — out of `sql/0066`'s scope.

## 5. `sql/0066` — what it grants and why

Full file: `sql/0066_uiw_runtime_admission_grants.sql`. Summary:

| Grant | Reason |
|---|---|
| `GRANT USAGE ON SCHEMA registry TO platform_runtime` | Fixes the crash. Live-reproduced error: `permission denied for schema registry` on the FK-identity regclass casts. Table-level SELECT on `registry.matter`/`registry.court_case` was already correct. |
| `GRANT USAGE ON SCHEMA raw TO platform_runtime` | The DuckDB structured-ELT lane (`activities.ExecuteStructuredELT`, `modules/engine/postgres/elt_structured_repository.go`) is `platform_runtime`'s only writer into `raw`, and it is `platform_runtime` at runtime (not a separate role) — confirmed by grep: no other file in `modules/engine` references a bare `raw.*` schema table. |
| `GRANT SELECT, INSERT ON raw.raw_csv TO platform_runtime` | Exactly the two verbs `elt_structured_repository.go` issues: `SELECT count(*) FROM raw.raw_csv` (idempotency guard, line 141) and `INSERT INTO raw.raw_csv (...)` (landing write, line 175). No other table in schema `raw` (of the other 12: `file_node`, `gps_point`, `raw_activity`, `raw_ai_chat`, `raw_facebook`, `raw_imessage`, `raw_path`, `raw_phone`, `raw_rejected`, `raw_sms`, `raw_trip`, `raw_visit`) has a live writer anywhere in `modules/engine` — granting them now would be privilege creep ahead of code that uses them, so 0066 grants `raw_csv` only. |
| `GRANT USAGE ON SCHEMA evidence TO platform_runtime` | The same ELT insert casts its `medium` argument to `evidence.record_medium` (line 183). Live-reproduced: `SELECT 'export'::evidence.record_medium` as `platform_runtime` fails with `permission denied for schema evidence` even though the TYPE privilege itself was already granted (`has_type_privilege` was already `true`) — PostgreSQL gates the schema-qualified name resolution the same way it gates `registry`. No `evidence` table is touched. |
| `GRANT USAGE ON SCHEMA ops` + `SELECT (migration_id) ON ops.migration_ledger` | Forward-provisioning for §3's Go fix, not required by the current (buggy) probe query. Narrow column grant mirrors 0038's precedent (`GRANT SELECT (migration_id, status) ON public.schema_version`); `ops.migration_ledger` has no `status` column, so only `migration_id` is granted. |

**Why raw/evidence/ops don't use `SET LOCAL ROLE platform_admin`:** live
ownership check (superuser query):

```
analysis  -> ai            (0054's DDL comment says platform_admin — drift)
context   -> platform_admin
evidence  -> ai
ops       -> ai
raw       -> platform_admin
registry  -> platform_admin
raw.raw_csv (table) -> ai
```

`registry` and `raw` (the schema) are owned by `platform_admin`, matching
every prior grants migration's `SET LOCAL ROLE platform_admin` convention, so
0066 uses that for those two GRANTs. `evidence`, `ops`, and the `raw.raw_csv`
table itself are live-owned by the bootstrap superuser, not `platform_admin`
— `SET LOCAL ROLE platform_admin` would fail closed on exactly the objects
that need it, since `platform_admin` has no grant authority over an object it
does not own. Those three GRANTs run without a role switch. **This ownership
split (`analysis`/`evidence`/`ops` owned by the superuser instead of
`platform_admin`, contradicting `0054`'s own `AUTHORIZATION platform_admin`
DDL comment) is reported here as found, not corrected** — an ownership
reconciliation is separate scope from a runtime-grants migration.

## 6. Zero-net-write validation (rollback-proven, nothing committed)

Applied `sql/0066` inside one open transaction against live `platform` as the
superuser, with the exact `ProbeUIWSchema` query re-run as `platform_runtime`
(`SET LOCAL ROLE`) both before and after, then `ROLLBACK`.

**Before** (reproduces the live crash exactly):
```
SET LOCAL ROLE platform_runtime;
<the verbatim ProbeUIWSchema query>
--> InsufficientPrivilege: permission denied for schema registry   (SQLSTATE 42501)
```

**Applying 0066** (in the same open transaction): no errors, including its
own internal `DO $verify$` guard block.

**Privilege deltas** (`platform_runtime`, all seven flip false → true, nothing
else touched):
```
registry_usage        false -> true
raw_usage              false -> true
raw_csv_select         false -> true
raw_csv_insert         false -> true
evidence_usage         false -> true
ops_usage              false -> true
ledger_migid_select    false -> true
```

**After** (same exact query, same role, still inside the open transaction —
now runs to completion instead of erroring):
```
database=platform current_user=platform_runtime database_owner=platform_admin
ledger_count=0 table_count=36 column_count=16
constraints_exact=false substrate_exact=true role_safe=true
grants_exact=true receipt_exact=false
```
i.e. the worker's crash-loop failure mode (`catalog verification unavailable`)
is fully resolved by this migration; what remains is a clean,
structured `UIW schema admission failed: ledger=0/9 tables=36/36
columns=16/16 constraints=false substrate=true role=true grants=true
receipt=false` rejection — exactly the two issues in §3 and §4/§2, which are
explicitly out of this migration's scope.

Also directly confirmed inside the same transaction, as `platform_runtime`:
`SELECT count(*) FROM raw.raw_csv` → `0` (succeeds), `SELECT
'export'::evidence.record_medium` → `'export'` (succeeds), `SELECT count(*)
FROM ops.migration_ledger WHERE migration_id = ANY(<our 9>)` → `9` (all
present, confirming §3's claim about the real ledger).

Transaction then `ROLLBACK`ed. **Nothing was committed to live** by this
build lane.

**Apply command** (orchestrator, when ready — not run here):
```
psql "service=platform-migration dbname=platform" -v ON_ERROR_STOP=1 \
     -f sql/0066_uiw_runtime_admission_grants.sql
```
or the repo's usual `SET LOCAL ROLE platform_admin`-aware apply harness,
consistent with how 0037/0038/0054 were applied. This migration is
plain, idempotent DDL+DCL (no data touched, no ledger insert of its own) —
whatever mechanism inserted the other 61 rows into `ops.migration_ledger`
should record this one too, once applied, per §3.

## 7. Exactly what remains blocking (not in scope here)

1. **Go bug** — `modules/engine/postgres/uiw_schema_probe.go`'s ledger check
   queries `public.schema_version` (0 rows, obsolete per 0055's own ruling)
   instead of `ops.migration_ledger` (61 rows, all 9 required migrations
   present). Fixing this requires editing Go, explicitly out of this lane's
   scope. `sql/0066` already grants what a corrected query would need.
2. **DDL drift** — `context.source_version` / `context.uiw_source_context_revision`
   are missing 2 of 0054's 8 constraints entirely and have 3 more sitting
   `NOT VALID` (never validated). The git-committed `sql/0054_platform_case_registry.sql`
   itself is stale (still targets `analysis.matter`/`analysis.court_case`,
   which no longer exist live; the live FKs target `registry.matter`/
   `registry.court_case`). Needs a DDL-repair migration reconciling the
   committed file with the live registry-schema shape and running the
   missing `VALIDATE CONSTRAINT`s.
3. **Identity/data drift, owner decision required** — `registry.matter` /
   `registry.court_case` hold exactly one row each, but with regenerated
   `uuidv7()` ids (`01a055b0-...`) that do **not** match the authoritative
   `01a03136-...` ids hardcoded in the Go probe and in
   `sql/validation/0054_platform_case_registry_adoption.json`. Until the
   owner picks (a) restore the `01a03136-...` identities as canonical, or (b)
   re-point the probe/manifest at the live `01a055b0-...` rows, no receipt
   row can be correctly seeded — seeding one now would either contradict live
   data or contradict the probe's hardcoded constants. `sql/0066`
   deliberately does not attempt this.
4. Once 1–3 are resolved and a receipt row exists, `ProbeUIWSchema` should
   pass cleanly with `sql/0066`'s grants already in place — no further
   grants migration should be needed for the currently-known code paths.

---

## 8. BUILD LANE S2 — items 1 and 2 fixed (2026-09-02)

> _Byline: Claude Code · Sonnet 5 · 2026-09-02._

Scope: fix the two remaining-blocking items §7 called out as unambiguous
(the Go ledger-query bug, and the 0054 constraint drift), leaving only
§7 item 3 (receipt identity — an owner decision) blocking. Touched only
`modules/engine/postgres/uiw_schema_probe.go` (+its test) and
`sql/0067_uiw_admission_constraint_repair.sql`, plus this section. No git
commit made.

### 8.1 Go fix — `uiw_schema_probe.go`

Two changes, both scoped to the ledger check:

1. **`ledgerCount` subquery** retargeted from `public.schema_version` (0 rows,
   not a ledger — D-109) to `ops.migration_ledger` (61 rows live, the real
   ledger per D-109/sql/0055 PART 5). `ops.migration_ledger` has no `status`
   column, so the `AND status='active'` predicate is dropped — presence of a
   `migration_id` row in that table means applied, full stop.
2. **Write-safety guard** (`grantsExact` clause) retargeted from
   `NOT has_table_privilege('platform_runtime','public.schema_version','INSERT')`
   to the same check against `ops.migration_ledger`. Reasoning (also inlined
   as a code comment at the call site): the guard's intent is "platform_runtime
   must never be able to forge ledger history" — that intent has to track
   whichever table is *actually* the ledger. Denying INSERT on the old
   data-contract-version table no longer protects anything now that writing
   rows there can't masquerade as applied-migration state; the guard was
   retargeted rather than duplicated, so there is exactly one ledger-integrity
   assertion and it points at the table that matters. Live-verified before
   writing the guard: `platform_runtime` already lacks INSERT on
   `ops.migration_ledger` (0066 granted `SELECT (migration_id)` only), so the
   retargeted guard passes today without any further grant.

No other line in the probe query changed — `requiredUIWMigrations`,
`requiredUIWTables`, `requiredUIWColumns`, the FK/CHECK/UNIQUE shape checks,
the substrate/role/receipt checks, and all Go control flow after `.Scan(...)`
are untouched.

**Test coverage added:** `TestProbeUIWSchemaLedgerQueriesTheRealLedger` in
`uiw_schema_probe_test.go`, using the existing `capturingProbeDB` harness. It
strips `--` SQL line-comments (so the D-109 explanatory comments, which
legitimately name `public.schema_version` for context, don't trip the
assertion) and then asserts the *executable* SQL (a) queries
`FROM ops.migration_ledger`, (b) contains no reference to
`public.schema_version`, and (c) asserts
`has_table_privilege('platform_runtime','ops.migration_ledger','INSERT')` is
false. All prior tests (`AdmitsExactPlatformContract`,
`CastsCatalogNamesBeforeTextArrayComparison`, `RejectsLegacy0043Substitution`,
`RejectsWrongIdentityOrScope`, `HidesCatalogError`) pass unmodified.

**Build/test (from `modules/engine`, `-mod=vendor -tags fts5`):**

```
go build -mod=vendor -tags fts5 ./...        # clean, no output
go vet   -mod=vendor -tags fts5 ./...        # clean, no output
go test  -mod=vendor -tags fts5 ./postgres/... -run TestProbeUIWSchema -v
  --- PASS: TestProbeUIWSchemaAdmitsExactPlatformContract (0.00s)
  --- PASS: TestProbeUIWSchemaCastsCatalogNamesBeforeTextArrayComparison (0.00s)
  --- PASS: TestProbeUIWSchemaRejectsLegacy0043Substitution (0.00s)
  --- PASS: TestProbeUIWSchemaLedgerQueriesTheRealLedger (0.00s)
  --- PASS: TestProbeUIWSchemaRejectsWrongIdentityOrScope (+7 subtests) (0.00s)
  --- PASS: TestProbeUIWSchemaHidesCatalogError (0.00s)
  ok  	.../engine/postgres	4.126s
go test  -mod=vendor -tags fts5 ./...        # all packages ok (postgres 8.623s; rest cached/ok)
```

### 8.2 SQL fix — `sql/0067_uiw_admission_constraint_repair.sql`

Constraint inventory (live-verified via `pg_constraint` against `platform`,
2026-09-02, matching §4's table exactly):

| # | Constraint | Relation | Type | Live before 0067 | Action in 0067 |
|---|---|---|---|---|---|
| 1 | `source_version_matter_case_pair_check` | `context.source_version` | CHECK | exists, validated | untouched |
| 2 | `source_version_court_case_scope_fk` | `context.source_version` | FK → `registry.court_case` | exists, validated | untouched |
| 3 | `uiw_source_context_scope_key` | `context.uiw_source_context_revision` | UNIQUE | exists, validated | untouched |
| 4 | `source_version_source_context_scope_fk` | `context.source_version` | FK → `context.uiw_source_context_revision` | exists, **not valid** | `VALIDATE CONSTRAINT` |
| 5 | `uiw_source_context_matter_fk` | `context.uiw_source_context_revision` | FK → `registry.matter` | exists, **not valid** | `VALIDATE CONSTRAINT` |
| 6 | `uiw_source_context_court_case_scope_fk` | `context.uiw_source_context_revision` | FK → `registry.court_case` | exists, **not valid** | `VALIDATE CONSTRAINT` |
| 7 | `source_version_matter_fk` | `context.source_version` | FK → `registry.matter` | **missing entirely** | `ADD CONSTRAINT ... NOT VALID` (retargeted from 0054's `analysis.matter` to live `registry.matter`), then `VALIDATE CONSTRAINT` |
| 8 | `source_version_source_context_scope_check` | `context.source_version` | CHECK | **missing entirely** | `ADD CONSTRAINT ... NOT VALID` (text unchanged from 0054 — unqualified), then `VALIDATE CONSTRAINT` |

Both target tables are empty live (`context.source_version` and
`context.uiw_source_context_revision`: 0 rows each, confirmed), so every
`VALIDATE` is instantaneous and no data-compliance risk exists. Confirmed by
direct read-only query before writing the migration: 0 orphan `matter_id`
values against `registry.matter`, 0 rows violating the new CHECK's shape, 0
orphan rows in either direction across all three retargeted FKs.

`sql/0054_platform_case_registry.sql` was **not edited** (applied migrations
are immutable per repo rule); 0067 is a forward-only repair that targets the
live `registry.*` names directly, following 0062's registry split rather
than 0054's now-stale `analysis.matter`/`analysis.court_case` references.
Ownership: both tables are live-owned by the bootstrap superuser (not
`platform_admin`, despite the `context` schema itself being
`platform_admin`-owned — the same drift 0066 found for `analysis`/`evidence`/
`ops`), so 0067's DDL runs without `SET LOCAL ROLE platform_admin`, and its
preflight `DO` block asserts the applying session actually owns (or is
superuser over) both tables before touching them, per 0066's
ownership-aware convention.

**Idempotence:** the two `ADD CONSTRAINT` statements are each guarded by an
`IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname=... )` check inside
a `DO` block (Postgres has no `ADD CONSTRAINT IF NOT EXISTS`); the five
`VALIDATE CONSTRAINT` statements are unconditional because `VALIDATE
CONSTRAINT` on an already-valid constraint is a documented Postgres no-op.
Verified live: applying the full migration body twice in succession inside
one open (later rolled-back) transaction produced no error on either run.

**Verify block:** re-derives `uiw_schema_probe.go`'s own `constraintsExact`
boolean expression line-for-line (same `VALUES` list, same
`pg_constraint`/`pg_attribute` joins) and raises an exception if it does not
evaluate `true` — so the migration cannot silently commit a shape the probe
would still reject.

### 8.3 Live validation (rollback-proven, nothing committed)

Applied `sql/0067` inside one open transaction against live `platform` as the
superuser (`ai`), re-running the corrected `ProbeUIWSchema` query (with §8.1's
`ops.migration_ledger` retarget already reflected) as `platform_runtime`
(`SET LOCAL ROLE`, via a savepoint) both before and after, then `ROLLBACK`.
Connection: tailnet `100.91.190.107:5432`, credentials from this repo's
`.env` (`DB_USER`/`DB_PASS`), parsed with a tolerant regex per the no-`source`
rule — values never printed.

**Before** (0066's grants already reflected; 0067 not yet applied):
```
database=platform current_user=platform_runtime database_owner=platform_admin
ledger_count=9 table_count=36 column_count=16
constraints_exact=False substrate_exact=True role_safe=True
grants_exact=True receipt_exact=False
```

**Applying 0067** (same open transaction): no errors, including its own
`$verify$` guard block.

**After** (same query, same role, still inside the open transaction):
```
database=platform current_user=platform_runtime database_owner=platform_admin
ledger_count=9 table_count=36 column_count=16
constraints_exact=True substrate_exact=True role_safe=True
grants_exact=True receipt_exact=False
```

Only `constraints_exact` changed, `False → True`, exactly the boolean this
migration targets. Post-apply `pg_constraint` dump (still inside the
transaction) confirmed all 8 constraints present, correctly typed, and
`convalidated=true`. Transaction then `ROLLBACK`ed — **nothing was committed
to live** by this build lane.

### 8.4 What remains blocking

With both S1 (`sql/0066`, grants) and S2 (Go retarget + `sql/0067`,
constraints) accounted for, re-running the full corrected probe query as
`platform_runtime` leaves exactly **one** false: `receipt_exact`. That is
§7 item 3 from the original review — the `registry.matter`/`registry.court_case`
identity mismatch between the live `01a055b0-...` rows and the
`01a03136-...` ids the probe and manifest both hardcode. It is an owner
identity decision on canonical case-registry data, explicitly out of scope
for both build lanes, and is the only thing left before `ProbeUIWSchema`
admits the worker.

**Apply commands** (orchestrator, when ready — not run here; this build lane
only proved 0067 inside a rolled-back transaction):
```
# Go: land the uiw_schema_probe.go + test changes in the next deploy build.
# SQL: apply 0067 the same way 0066 was applied —
psql "service=platform-migration dbname=platform" -v ON_ERROR_STOP=1 \
     -f sql/0067_uiw_admission_constraint_repair.sql
```
Whatever mechanism records the other 62 rows in `ops.migration_ledger`
(61 as of §3, +1 once 0066 is actually committed) should record 0067 too,
once applied — this migration does not insert its own ledger row, matching
0066's convention.
