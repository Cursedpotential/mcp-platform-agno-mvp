# Runbook: case-registry go-live cutover (D-126)

> _Byline: Claude Code · Sonnet 5 · 2026-09-02 (BUILD LANE S3)._

Governing ruling: `docs/DECISION_LOG.md` D-126 (rel: D-115, D-117, D-118, D-125,
sql/0054, sql/0066, sql/0067). Read that entry before running any step here.

## What this runbook is for

Pre-launch, the platform's case-registry identity (`registry.matter` /
`registry.court_case`) is forced to a fixed, obviously-synthetic **DEV
sentinel** so the whole ingest/reset/re-ingest cycle has something stable and
disposable to reference. This runbook is the **one-time cutover** from that
DEV sentinel to the **real** Matter/CourtCase identity, run exactly once, at
go-live.

Do **not** run these steps casually. Step 4 permanently retires the DEV
sentinel and step 6 mints identity that becomes real, referenced, custody
data the moment anything writes against it.

## Background: what sql/0069 built and why

`sql/0069_dev_case_registry_identity.sql` forces:

| What | Value |
|---|---|
| DEV matter id | `deadbeef-dead-beef-dead-beefdeadbeef` |
| DEV court_case id | `cafebabe-cafe-babe-cafe-babecafebabe` |
| matter title | `DEV — placeholder matter (pre-launch, disposable)` |
| court_case caption | `DEV — placeholder proceeding (pre-launch, disposable)` |
| `verification_state` | `proposed` (never auto-`confirmed` — D-117) |
| `analysis.matter_knowledge_partition('primary')` | points at both sentinels |
| `analysis.case_registry_import_receipt.approved_by` | `dev-mode-placeholder` — **never `'owner'`** (D-126 forbids a fabricated owner-approval row) |

Both ids are UUID-*shaped* (Postgres `registry.matter.id`/`registry.court_case.id`
are `uuid`-typed columns with ~8 live FK referrers — retyping them was out of
scope and unjustified for a placeholder) but built entirely from classic
"obviously fake" hex magic numbers (every character is valid hex, 0-9/a-f):
`DEADBEEF` for the matter, `CAFEBABE` for the court case. Neither `uuidv7()`
nor any real UUID generator ever emits either pattern, and both are visually
unmistakable next to a real time-ordered `uuidv7` id (which always starts
with a timestamp prefix, e.g. `01a0...`).

`modules/engine/postgres/uiw_schema_probe.go` mirrors these exact literals as
`devMatterID`/`devCourtCaseID`/`devReceipt*` constants. **The two files must
always be changed together** — if you ever need to touch the sentinel
values, edit both in the same change.

The DEV identity **self-heals** across every `ops.reset_test_data('RESET')`
call (D-118): 0069 also redefined `ops.reset_test_data` to call
`registry.reseed_dev_case_identity()` at the end of every reset. That
reseed function refuses (logs a `WARNING`, does nothing) the instant it
finds a `registry.matter`/`registry.court_case` row it did not itself write
(tracked by `created_by IN ('migration-0030', 'migration-0069-dev-seed')`) —
this is the safety backstop that makes step 5 below harmless.

`PLATFORM_DEV_AUTH_BYPASS` (D-125) is the flag. When set on a process that
calls `ProbeUIWSchema`, the admission probe checks the DEV sentinel identity
and the honest dev receipt **instead of skipping the check** — identity and
receipt verification stay fully enforced in both modes (owner ruling,
2026-09-02: *"everything else is still going to look for it, still going to
reference it... it's going to be referencing a fake one that's not an actual
UUID"*). When unset (the default, fail-closed), the probe checks the real
authoritative identity — which is why admission is intentionally **unmet**
until this runbook's steps are complete.

## Coolify apps that carry the flag

Per D-125, exactly these three apps read `PLATFORM_DEV_AUTH_BYPASS`:

1. `universal-import-starter` (`deploy/universal-import-starter.yaml`) — reads
   the flag in **two** independent places (BUILD LANE N2, 2026-09-02 added
   the second):
   - `ProbeUIWSchema` (`modules/engine/postgres/uiw_schema_probe.go`), called
     once at boot from `modules/engine/temporal/cmd/starter/main.go` — the
     case-registry identity/receipt admission this runbook is otherwise
     about.
   - `withAuth` (`modules/engine/temporal/httpapi.go`) — D-125's literal ask
     on the starter's own HTTP surface (`POST /reference-import/start`,
     `POST /reference-import/{workflow_id}/decision`,
     `GET /reference-import/{workflow_id}/preview`). Flag unset (default) is
     the unchanged strict tailnet-only check
     (`authorizedTailnetPeer`/`100.64.0.0/10`); flag set admits a
     non-tailnet-ranged peer (e.g. n8n running off-tailnet on ion-control)
     but never removes the tailnet check itself, and logs one `WARN` line
     per admitted-but-would-have-been-rejected request naming the flag, the
     rejected `RemoteAddr`, and the route (D-127 Rule 5) — plus a one-time
     `WARN` at `NewStarterHTTPHandler` construction when the flag is set,
     matching `ProbeUIWSchema`'s startup-warning wording style. Both flag
     states are covered by `modules/engine/temporal/httpapi_test.go`
     (`TestWithAuthFlag*`, `TestNewStarterHTTPHandler*Startup*`).
2. `universal-import-worker` (`deploy/universal-import-worker.yaml`) — calls
   `ProbeUIWSchema` from `modules/engine/uiwworker/worker.go`.
3. `knowledge-workbench` (`deploy/workbench.yaml`) — the Workbench BFF (D-125's
   second named surface).

## Pre-flight: prove the STRICT path actually works, before you trust it

Before touching any live data, prove that the STRICT (flag-off) admission
path is not merely *unmet* but *unbroken* — i.e. that if the real identity
and receipt existed with the right values, the probe would actually admit
them. This build lane proved it once (2026-09-02, live, fully rolled back);
**re-run the same proof** here before the real cutover, and after any future
change to `uiw_schema_probe.go`'s STRICT constants or query text.

### How to re-run the STRICT-path proof (safe — everything rolls back)

Connect as a superuser to the `platform` database. In one transaction:

```sql
BEGIN;
-- (Assumes sql/0069 is already applied, so a DEV sentinel + dev receipt exist.)

SAVEPOINT sp_strict;

-- 1. temporarily install a REAL-SHAPED matter/court_case at the exact
--    authoritative ids the Go STRICT constants expect
INSERT INTO registry.matter (id, title, status, created_by, verification_state)
VALUES ('<authoritativeMatterID>'::uuid, 'TEMP STRICT PROOF - not real', 'active', 'validation-proof', 'proposed');
INSERT INTO registry.court_case (id, matter_id, caption, status, is_primary, created_by, verification_state)
VALUES ('<authoritativeCourtCaseID>'::uuid, '<authoritativeMatterID>'::uuid, 'TEMP STRICT PROOF', 'pre_filing', false, 'validation-proof', 'proposed');

-- 2. the dev receipt still holds partition_key='primary' via a RESTRICT FK;
--    remove it temporarily so the partition row can be repointed (restored
--    automatically by the ROLLBACK TO SAVEPOINT below)
DELETE FROM analysis.case_registry_import_receipt WHERE approved_by = 'dev-mode-placeholder';
UPDATE analysis.matter_knowledge_partition
   SET matter_id = '<authoritativeMatterID>'::uuid, default_court_case_id = '<authoritativeCourtCaseID>'::uuid
 WHERE partition_key = 'primary';

-- 3. insert a receipt matching every STRICT predicate in uiw_schema_probe.go
--    exactly (registrySourceMigrationURI/SHA256/GitCommit/PayloadSchemaVersion/
--    CanonicalPayloadSHA256/APIPayloadSHA256/registryReceiptPayloadByteLength/
--    registryReceiptApprovedBy='owner'/registryReceiptApprovedOn='2026-08-23')
INSERT INTO analysis.case_registry_import_receipt (
    manifest_sha256, source_migration_uri, source_migration_sha256, source_git_commit,
    payload_schema_version, payload_byte_length, canonical_payload_sha256, api_payload_sha256,
    source_observed_at, matter_id, court_case_id, partition_key, approved_by, approved_on, imported_by
) VALUES (
    decode(repeat('11', 32), 'hex'),  -- any distinct valid 32-byte value; not probe-checked
    'sql/0030_matter_case_foundation.sql',
    decode('b19959119c0f040adcdc442aa7772503fd2d1439a90b1565eaa6c17e0883eb70', 'hex'),
    '97f48b172b1d31aa5a0005b45170d72af1299773',
    '0030-platform-registry-handoff-v1', 1075,
    decode('8e0a8e2d86027add31f9470976d1378e039d6efb5312ecae4cfec0ebd10690e6', 'hex'),
    decode('cd370f6c9c00e620f39f283e2d0d7d1a83a463b14097b99537b886d438618a6d', 'hex'),
    TIMESTAMPTZ '2026-08-23 00:00:00+00',
    '<authoritativeMatterID>'::uuid, '<authoritativeCourtCaseID>'::uuid, 'primary', 'owner', DATE '2026-08-23', 'validation-proof'
);

-- 4. run the probe's EXACT query text (copy from uiw_schema_probe.go) as
--    platform_runtime, bound to the STRICT constants
SET LOCAL ROLE platform_runtime;
-- ... run the probe SELECT here, bind $4/$5 = authoritativeMatterID/authoritativeCourtCaseID,
--     $6..$11 = registrySourceMigrationURI/SHA256/GitCommit/PayloadSchemaVersion/
--     CanonicalPayloadSHA256/APIPayloadSHA256, $12/$13/$14 = 1075/'owner'/'2026-08-23' ...
RESET ROLE;
-- expect every returned boolean = true (this build lane confirmed this live, 2026-09-02)

ROLLBACK TO SAVEPOINT sp_strict;  -- undoes steps 1-3, restores the DEV sentinel + dev receipt
ROLLBACK;  -- or COMMIT nothing -- this is a proof run, never a seed (D-126)
```

This is exactly the sequence this build lane's validation ran (superuser,
live `platform`, fully rolled back — no receipt with `approved_by='owner'`
was ever committed). If any boolean comes back `false`, do **not** proceed
with cutover — the STRICT query itself has drifted from the live schema and
needs a repair migration (in the style of sql/0066/0067) before go-live, not
a workaround at go-live time.

## Cutover procedure

Perform this in one maintenance window. Steps 4-6 should happen back to
back — do not leave the database in the "just reset" state (step 3) for any
length of time, since the automatic self-heal will have just re-seeded the
DEV sentinel and something else attempting to write case-scoped data in that
window would bind to the DEV identity.

1. **Decide the real identity values.** Generate the real Matter/CourtCase
   ids (e.g. `SELECT uuidv7();` twice, or let the inserts in step 6 default
   and read them back — but note the Go STRICT constants are compile-time
   literals, so the ids must be decided *before* step 2, not read back
   after). Assemble the real approval receipt's provenance fields the same
   way `registrySourceMigrationURI`/`SHA256`/`GitCommit`/
   `PayloadSchemaVersion`/`CanonicalPayloadSHA256`/`APIPayloadSHA256` were
   assembled for the original (never-applied) 2026-08-23 identity — this is
   process, not code; there is no tool in this repo yet that manufactures a
   real receipt automatically, by design (D-126: no fabricated approval).

2. **Update `modules/engine/postgres/uiw_schema_probe.go`'s STRICT
   constants** (`authoritativeMatterID`, `authoritativeCourtCaseID`,
   `registrySourceMigrationURI`, `registrySourceMigrationSHA256`,
   `registrySourceGitCommit`, `registryPayloadSchemaVersion`,
   `registryCanonicalPayloadSHA256`, `registryAPIPayloadSHA256`,
   `registryReceiptPayloadByteLength`, `registryReceiptApprovedBy`,
   `registryReceiptApprovedOn`) to the values decided in step 1. Re-run the
   STRICT-path proof above against a staging/scratch copy if one is
   available. Commit, deploy the new binary to all three apps (still with
   `PLATFORM_DEV_AUTH_BYPASS` set — do not remove the flag yet, or every
   ingest surface admission-fails the instant the old STRICT constants no
   longer match anything and the new real rows don't exist yet either).

3. **Run `ops.reset_test_data('RESET')`** (D-118) against `platform` as
   `platform_admin` (or superuser). This purges test data in
   raw/evidence/working/context/timeline/analysis. **Expected and harmless:**
   the self-heal wired into `ops.reset_test_data` by sql/0069 will
   immediately re-seed the DEV sentinel identity, partition, and dev
   receipt one more time — `registry.matter`/`registry.court_case`
   themselves were never touched by the reset (they live outside its
   truncation loop; D-115/D-117). Do not treat this re-seed as a reason to
   skip step 4, and never run `ops.reset_test_data` again after step 4
   completes without first re-reading `registry.reseed_dev_case_identity()`'s
   safety-guard comment in sql/0069.

4. **Retire the DEV sentinel and mint the real identity**, in one
   transaction:

   ```sql
   BEGIN;
   DELETE FROM analysis.case_registry_import_receipt WHERE approved_by = 'dev-mode-placeholder';
   -- (matter_knowledge_partition PK is partition_key alone; UPDATE it below,
   -- not delete+reinsert, since it is referenced by the FK above.)
   -- court_case before matter (child before parent, RESTRICT FK):
   DELETE FROM registry.court_case WHERE id = 'cafebabe-cafe-babe-cafe-babecafebabe'::uuid;
   DELETE FROM registry.matter WHERE id = 'deadbeef-dead-beef-dead-beefdeadbeef'::uuid;

   INSERT INTO registry.matter (id, title, status, created_by, verification_state)
   VALUES ('<REAL matter id>'::uuid, '<real matter title>', 'active', 'owner', 'confirmed');
   INSERT INTO registry.court_case (id, matter_id, caption, status, is_primary, created_by, verification_state)
   VALUES ('<REAL court_case id>'::uuid, '<REAL matter id>'::uuid, '<real caption>', 'active', true, 'owner', 'confirmed');

   UPDATE analysis.matter_knowledge_partition
      SET matter_id = '<REAL matter id>'::uuid, default_court_case_id = '<REAL court_case id>'::uuid,
          created_by = 'owner'
    WHERE partition_key = 'primary';

   INSERT INTO analysis.case_registry_import_receipt (
       manifest_sha256, source_migration_uri, source_migration_sha256, source_git_commit,
       payload_schema_version, payload_byte_length, canonical_payload_sha256, api_payload_sha256,
       source_observed_at, matter_id, court_case_id, partition_key, approved_by, approved_on, imported_by
   ) VALUES (
       -- real manifest hash of whatever approval payload the owner actually reviewed
       decode('<real manifest sha256 hex>', 'hex'),
       '<real source_migration_uri>',
       decode('<real source_migration_sha256 hex>', 'hex'),
       '<real 40-hex git commit>',
       '<real payload_schema_version>', <real payload_byte_length>,
       decode('<real canonical_payload_sha256 hex>', 'hex'),
       decode('<real api_payload_sha256 hex>', 'hex'),
       now(), '<REAL matter id>'::uuid, '<REAL court_case id>'::uuid, 'primary',
       'owner', CURRENT_DATE, 'owner'
   );
   COMMIT;
   ```

   `verification_state='confirmed'` here is deliberate and is the ONE place
   this ever happens automatically-by-script for identity rows — because
   this whole runbook step *is* the owner ruling D-117 requires (a human is
   running this transaction as the act of approval). Do not script this
   step to run unattended.

5. **Remove `PLATFORM_DEV_AUTH_BYPASS` from all three Coolify apps**
   (`universal-import-starter`, `universal-import-worker`,
   `knowledge-workbench`) — remove the env var entirely, not just unset its
   value (D-125). Redeploy all three (Coolify renders env values into the
   compose file at deploy time; removing the var alone does not reach
   running containers until a redeploy).

6. **Verify strict admission for real.** Re-run the probe (or just start
   one of the three apps and watch its boot logs) and confirm
   `ProbeUIWSchema` returns `nil` with `PLATFORM_DEV_AUTH_BYPASS` genuinely
   absent from the process environment. There is no `WARNING` log line in
   this state — if you see the `PLATFORM_DEV_AUTH_BYPASS is set` warning
   after this step, the flag was not actually removed from that app's
   environment; check Coolify's rendered compose, not just the dashboard
   field.

   For `universal-import-starter` specifically, also confirm its **second**
   surface (`withAuth`) went strict: no `PLATFORM_DEV_AUTH_BYPASS is set`
   warning at startup, and a probe request from a non-tailnet-ranged address
   against `/reference-import/start` (or `/decision`, `/preview`) now
   returns `401`, not an admitted response with a per-request `WARN` line.
   n8n must reach this app over the tailnet from here on — confirm its
   egress path (see the D-042 tailnet cutover notes) before removing the
   flag, or the legitimate n8n bridge breaks the moment the flag is gone.

## What NOT to do

- Do not re-run `sql/0069_dev_case_registry_identity.sql` after step 4 — its
  own safety guard makes it a safe no-op (it will only `RAISE WARNING` and
  do nothing once it sees the real `created_by='owner'` rows), but there is
  no reason to run it again.
- Do not call `ops.reset_test_data('RESET')` again once real identity
  exists without first confirming (read `registry.reseed_dev_case_identity()`'s
  guard) that it will refuse to touch the real rows. It is designed to
  refuse automatically, but this is production case identity — verify, do
  not assume.
- Do not hand-edit `analysis.case_registry_import_receipt` rows. The table
  has no `UPDATE`/`DELETE` triggers live today (D-110: those guard triggers
  were among the ~253 deliberately skipped in the 2026-08-30 rebuild, gated
  on a separate precondition, out of this build lane's scope) — but treat it
  as immutable by discipline regardless. If a receipt is wrong, that is an
  owner-ruled correction via `canon.change_proposal` (D-117), never a
  direct `UPDATE`/`DELETE`.
