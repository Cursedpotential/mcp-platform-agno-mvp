# D1 — Source Evidence & Chain-of-Custody (PG Domain Reconciliation)

> _Byline: Claude Code · Opus 4.8 (1M) · 2026-06-30_
>
> **Scope:** the source/custody core of the unified PostgreSQL resource (PG18 + PostGIS +
> embedded DuckDB via `pg_duckdb`). This domain owns: the **raw source registry**, the
> recursive **file decomposition** tree, the **3-level (H1/H2/H3) integrity-hash ledger**
> (extending the as-built `evidence.evidence_hash`), and the append-only, hash-chained
> **chain-of-custody event log**. Lineage/runs/reviews/redactions/exports/audit-spine are
> cross-cutting provenance handled in their own domain pass; here we land only what makes a
> *source artifact's identity and custody* defensible.
>
> **Law (ground truth):** `extracted/E1_asbuilt_inventory.md`. **Donor intents:**
> `extracted/E2_messaging_core.md` (§A `messaging_documents` custody), paper section
> `sections/09-provenance-custody.md`, crosswalk `discovery/A3_crosswalk.md`,
> `discovery/CONTEXT_PACK.md`, and the extension/reconciliation addendum.

---

## 1. Reconciliation stance (what changed vs the paper design)

The paper (§09) invented a **parallel top-level `provenance` schema** and an
`evidence.raw_object` table that duplicates the as-built `evidence.evidence_hash`. Both
violate the as-built security boundary. This reconciliation **re-homes everything under the
three as-built schemas** and **extends — not replaces — `evidence.evidence_hash`**:

| Paper construct (§09) | Reconciled home | Why |
|---|---|---|
| `evidence.raw_object` | **`evidence.source`** (new, in the as-built `evidence` schema) | Raw/source ⇒ `evidence` (agents RO, connection-enforced). "raw_object" renamed to match the §3 canonical-model name `custody.source` → flattened to `evidence.source`. |
| `custody.file_node` (file→page→frame→…) | **`evidence.file_node`** | Same RO boundary; recursive decomposition of a source. |
| `provenance.custody_hash` (H1/H2/H3) | **folded into `evidence.evidence_hash`** (extended) | The as-built ledger already *is* the hash table (`digest BYTEA`, `blob_key`, `meta`). Adding a `level` + locator + Merkle-member column subsumes the paper table — one ledger, not two. |
| `provenance.audit_log` / custody actions | **`evidence.custody_event`** (chain-of-custody slice only) | The *custody* transitions (collected→sealed→verified→disputed→released) live with the source, append-only + pgcrypto hash-chained. The global system audit-spine (`run_start`/`review`/`export`/`access`) is a separate cross-cutting domain. |
| `provenance.run` / `artifact` / `lineage_edge` / `review` / `redaction` / `export` / version registries | **out of D1** (lineage/provenance domain) | Not source-custody; deferred to keep this domain tight. `evidence.evidence_hash.id` stays the stable artifact anchor those tables will FK to (as `analysis.normalized_record.artifact_id` already does). |

**As-built invariants preserved.** `evidence.evidence_hash.id` (PK, `uuidv7()`) is **not
touched** — `analysis.normalized_record.artifact_id → evidence.evidence_hash(id)` keeps
working. The as-built `source_ref TEXT`, `algo`, `digest BYTEA`, `hashed_at`, `blob_key`,
`meta` columns and the `algo<>'sha256' OR octet_length(digest)=32` CHECK all remain; new
columns are purely **additive** (`ADD COLUMN IF NOT EXISTS`).

**Custom-type discipline (`0004`).** Reuses `confidence`, `canonical_id`, `source_system`,
`source_ref` (composite). Creates the renamed `sensitivity_tier` (the §5.1 bug fix). New
closed sets that have no as-built type use `TEXT + CHECK` to mirror the as-built style
(`normalized_record.disclosure_tier`, `agent_run.status`), avoiding a sprawl of new enums.

**`disclosure_tier` double-definition fix (E1 §5.1).** Kept as a migration action: the
substantive bitemporal column (`analysis.normalized_record.disclosure_tier` TEXT
`contemporaneous|hindsight|discovered`) is the survivor; the orphan `0004` enum
`('public','restricted','sealed')` is **renamed to `sensitivity_tier`** and reused here for
`evidence.source.sensitivity_tier`. (The `normalized_record` column rename to
`knowledge_horizon` is an *analysis*-domain call, only referenced here.)

**Court-safe lanes.** Everything in `evidence.*` is `raw_evidence` by construction
(originals + their integrity hashes + custody log). No inference, no labels, no findings
live here — those are `analysis.*`. Originals are **write-once**; custody is **append-only**.

---

## 2. Reconciled DDL

```sql
-- =====================================================================
-- D1 — Source Evidence & Chain-of-Custody
-- Target: unified PG18 resource (agno-postgres:18-duckdb), schema `evidence`
-- Extensions used: pgcrypto (digest sha256), pg_trgm (filename fuzzy),
--   ltree (decomposition path), btree_gin, hstore/jsonb. Raw bytes in R2,
--   reachable via pg_duckdb httpfs (r2_bucket/r2_key).
-- Boundary: `evidence` = raw/source, agents READ-ONLY (connection-enforced).
--   Writes here come from the ingestion service role only (never agents).
-- =====================================================================

-- ── 0. Bug fix: rename the orphan 0004 enum so its name stops colliding
--      with the substantive bitemporal text column on normalized_record.
--      (idempotent guard)
DO $$ BEGIN
    ALTER TYPE disclosure_tier RENAME TO sensitivity_tier;   -- public|restricted|sealed
EXCEPTION
    WHEN undefined_object THEN NULL;   -- already renamed or 0004 not applied
    WHEN duplicate_object THEN NULL;   -- sensitivity_tier already exists
END $$;

-- ── 1. Shared write-once / append-only guard (lives in `evidence`) ────
CREATE OR REPLACE FUNCTION evidence.forbid_mutation() RETURNS trigger
  LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION
      'evidence.% is immutable (P1/P4 originals/append-only): % blocked',
      TG_TABLE_NAME, TG_OP;
END $$;

-- ── 2. Raw source registry (write-once original-of-record) ────────────
--      = paper evidence.raw_object  ⊕  E2 messaging_documents custody fields
CREATE TABLE IF NOT EXISTS evidence.source (
    id                  uuid PRIMARY KEY DEFAULT uuidv7(),
    -- identity (H1 mirrored here for content-addressing; full ledger in evidence_hash)
    sha256              bytea NOT NULL,                 -- H1 canonical identity (32B)
    md5_prefilter       bytea,                          -- pre-filter / CaseBible MD5 join ONLY
    byte_size           bigint NOT NULL,
    mime_type           text,
    original_filename   text,
    -- source descriptor (E2 messaging_documents + paper MP 1545-1566)
    source_type         text NOT NULL                  -- device_dump|chat_export|screenshot|
                        CHECK (source_type IN ('device_dump','chat_export','screenshot',
                          'call_log','pdf','media','takeout','social_export','document','other')),
    source_platform     text,                           -- android|ios|facebook|snapchat|...
    custodian           text NOT NULL DEFAULT 'Matt Salem',   -- E2 acquired_by
    acquisition_source  text NOT NULL,                  -- device dump|onedrive|gdrive|scan|subpoena
    acquisition_method  text                            -- E2 acquisition_method
                        CHECK (acquisition_method IS NULL OR acquisition_method IN
                          ('forensic_image','manual_export','cloud_pull','photograph','scan','backup')),
    origin_device_id    text,                           -- upstream provenance
    origin_account      text,
    -- timestamp-certainty triple (the precision class missing from ALL prior schemas)
    acquired_at_raw     text,                           -- as-reported string
    acquired_at_utc     timestamptz,                    -- normalized (= E2 acquired_date)
    acquired_tz_offset  text,
    acquired_certainty  text NOT NULL DEFAULT 'exact'
                        CHECK (acquired_certainty IN ('exact','approximate','inferred','uncertain')),
    -- storage / custody location (raw bytes in R2; pg_duckdb reach)
    provenance_tier     text NOT NULL DEFAULT 'r2_canonical'
                        CHECK (provenance_tier IN ('r2_canonical','backup_corroborating')),
    r2_bucket           text,                           -- e.g. casebible-raw
    r2_key              text,                           -- content-addressed object key
    local_path          text,                           -- D:/Backup corroborating copy, if any
    hash_canon_version  text NOT NULL DEFAULT 'h1-rawbytes-v1',  -- canonicalization recipe id
    -- classification (reuses the renamed 0004 enum; never auto-promoted)
    sensitivity_tier    sensitivity_tier NOT NULL DEFAULT 'restricted',  -- public|restricted|sealed
    legal_sensitivity   text NOT NULL DEFAULT 'none'
                        CHECK (legal_sensitivity IN ('none','privileged','confidential','in_camera')),
    privacy_sensitivity text NOT NULL DEFAULT 'none'
                        CHECK (privacy_sensitivity IN ('none','pii','minor','sensitive_pii')),
    -- supersession (a corrected re-export is a NEW source, never an in-place edit)
    supersedes_source_id uuid REFERENCES evidence.source(id),
    -- ── MUTABLE WHITELIST: lifecycle status flags maintained by ingestion runs.
    --    Authoritative history is custody_event (§4); these are convenience state.
    custody_status      text NOT NULL DEFAULT 'collected'
                        CHECK (custody_status IN
                          ('collected','sealed','in_processing','verified','disputed','released')),
    extraction_status   text NOT NULL DEFAULT 'pending'
                        CHECK (extraction_status IN ('pending','running','done','failed','n/a')),
    processing_status   text NOT NULL DEFAULT 'pending'
                        CHECK (processing_status IN ('pending','enriched','analyzed','failed')),
    review_status       text NOT NULL DEFAULT 'not_reviewed'
                        CHECK (review_status IN ('not_reviewed','in_review','reviewed','flagged')),
    export_status       text NOT NULL DEFAULT 'not_exported'
                        CHECK (export_status IN ('not_exported','in_package','exported','withdrawn')),
    verified_by         text,                           -- E2 verified_by
    verified_at         timestamptz,                    -- E2 verified_date
    -- metadata: original (as-received, never edited) vs derived (system-computed)
    original_metadata   jsonb NOT NULL DEFAULT '{}',    -- EXIF/headers/export manifest (E2 metadata)
    derived_metadata    jsonb NOT NULL DEFAULT '{}',    -- mime sniff, page_count, record_count (S1)
    ingested_at         timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT source_sha256_len CHECK (octet_length(sha256) = 32),
    CONSTRAINT source_sha256_uniq UNIQUE (sha256)       -- content-addressed dedupe
);
CREATE INDEX IF NOT EXISTS idx_source_custody     ON evidence.source (custody_status);
CREATE INDEX IF NOT EXISTS idx_source_platform    ON evidence.source (source_platform, source_type);
CREATE INDEX IF NOT EXISTS idx_source_filename_trgm ON evidence.source USING gin (original_filename gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_source_orig_meta   ON evidence.source USING gin (original_metadata);
CREATE INDEX IF NOT EXISTS idx_source_supersedes  ON evidence.source (supersedes_source_id);

-- write-once on bytes/identity; status whitelist trigger allows lifecycle updates only
CREATE OR REPLACE FUNCTION evidence.source_immutable_core() RETURNS trigger
  LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'evidence.source is write-once: DELETE blocked (never-delete → _stale)';
    END IF;
    -- immutable columns: any change to identity/storage/descriptor is forbidden
    IF  NEW.sha256              IS DISTINCT FROM OLD.sha256
     OR NEW.md5_prefilter       IS DISTINCT FROM OLD.md5_prefilter
     OR NEW.byte_size           IS DISTINCT FROM OLD.byte_size
     OR NEW.mime_type           IS DISTINCT FROM OLD.mime_type
     OR NEW.original_filename   IS DISTINCT FROM OLD.original_filename
     OR NEW.source_type         IS DISTINCT FROM OLD.source_type
     OR NEW.custodian           IS DISTINCT FROM OLD.custodian
     OR NEW.acquisition_source  IS DISTINCT FROM OLD.acquisition_source
     OR NEW.r2_bucket           IS DISTINCT FROM OLD.r2_bucket
     OR NEW.r2_key              IS DISTINCT FROM OLD.r2_key
     OR NEW.provenance_tier     IS DISTINCT FROM OLD.provenance_tier
     OR NEW.hash_canon_version  IS DISTINCT FROM OLD.hash_canon_version
     OR NEW.supersedes_source_id IS DISTINCT FROM OLD.supersedes_source_id
     OR NEW.original_metadata   IS DISTINCT FROM OLD.original_metadata
     OR NEW.ingested_at         IS DISTINCT FROM OLD.ingested_at THEN
        RAISE EXCEPTION 'evidence.source core/identity columns are immutable (only lifecycle status may change)';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER source_immutable BEFORE UPDATE OR DELETE ON evidence.source
  FOR EACH ROW EXECUTE FUNCTION evidence.source_immutable_core();

-- ── 3. Recursive file decomposition (file→page→frame→screenshot→OCR→msg→event)
CREATE TABLE IF NOT EXISTS evidence.file_node (
    id              uuid PRIMARY KEY DEFAULT uuidv7(),
    source_id       uuid NOT NULL REFERENCES evidence.source(id),
    parent_node_id  uuid REFERENCES evidence.file_node(id),
    node_kind       text NOT NULL                       -- file|archive_member|page|frame|
                    CHECK (node_kind IN ('file','archive_member','page','frame','region',
                      'screenshot','ocr_block','attachment','message_unit','event_unit')),
    node_path       ltree,                              -- hierarchical address within the source
    ordinal         int,                                -- position among siblings (sequence)
    sha256          bytea,                              -- node payload hash (H2-eligible); null for pure structural
    byte_span_start bigint,                             -- offset into the parent original
    byte_span_end   bigint,
    locator         jsonb NOT NULL DEFAULT '{}',        -- bbox / part-index / selector / page#
    mime_type       text,
    extraction_confidence confidence,                   -- 0004 domain: OCR/parse confidence (null for raw nodes)
    attrs           jsonb NOT NULL DEFAULT '{}',
    created_at      timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT file_node_sha_len CHECK (sha256 IS NULL OR octet_length(sha256) = 32)
);
CREATE INDEX IF NOT EXISTS idx_filenode_source  ON evidence.file_node (source_id);
CREATE INDEX IF NOT EXISTS idx_filenode_parent  ON evidence.file_node (parent_node_id);
CREATE INDEX IF NOT EXISTS idx_filenode_path    ON evidence.file_node USING gist (node_path);
CREATE INDEX IF NOT EXISTS idx_filenode_sha     ON evidence.file_node (sha256);
CREATE TRIGGER filenode_immutable BEFORE UPDATE OR DELETE ON evidence.file_node
  FOR EACH ROW EXECUTE FUNCTION evidence.forbid_mutation();

-- ── 4. Integrity-hash ledger — EXTEND the as-built evidence.evidence_hash ──
--      (as-built columns id/source_ref/algo/digest/hashed_at/blob_key/meta and
--       the 32-byte sha256 CHECK + idx_evidence_hash_digest are PRESERVED.)
ALTER TABLE evidence.evidence_hash
  ADD COLUMN IF NOT EXISTS level           text NOT NULL DEFAULT 'H1'
                          CHECK (level IN ('H1','H2','H3')),         -- 3-level custody
  ADD COLUMN IF NOT EXISTS source_id       uuid REFERENCES evidence.source(id),
  ADD COLUMN IF NOT EXISTS file_node_id    uuid REFERENCES evidence.file_node(id),
  ADD COLUMN IF NOT EXISTS md5_prefilter   bytea,                    -- pre-filter only (never integrity)
  ADD COLUMN IF NOT EXISTS record_locator  jsonb,                    -- H2: byte-span/bbox/offset
  ADD COLUMN IF NOT EXISTS member_hash_ids uuid[],                   -- H3: ordered member hash ids (Merkle input)
  ADD COLUMN IF NOT EXISTS canon_version   text NOT NULL DEFAULT 'h1-rawbytes-v1',
  ADD COLUMN IF NOT EXISTS computed_by      text;                    -- run/service that computed it
-- exactly-one-subject for H1/H2 (H3 collections use member_hash_ids)
ALTER TABLE evidence.evidence_hash
  ADD CONSTRAINT evidence_hash_subject_ck CHECK (
    level = 'H3'
    OR source_id IS NOT NULL
    OR file_node_id IS NOT NULL
  ) NOT VALID;   -- NOT VALID: legacy rows predate the FK columns; validate after backfill
CREATE INDEX IF NOT EXISTS idx_evhash_level_source ON evidence.evidence_hash (level, source_id);
CREATE INDEX IF NOT EXISTS idx_evhash_filenode     ON evidence.evidence_hash (file_node_id);
CREATE INDEX IF NOT EXISTS idx_evhash_meta         ON evidence.evidence_hash USING gin (meta);
-- (append-only by design; add the guard the as-built table lacked)
CREATE TRIGGER evidence_hash_immutable BEFORE UPDATE OR DELETE ON evidence.evidence_hash
  FOR EACH ROW EXECUTE FUNCTION evidence.forbid_mutation();

-- ── 5. Chain-of-custody event log (append-only, pgcrypto hash-chained) ─────
CREATE TABLE IF NOT EXISTS evidence.custody_event (
    seq             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id              uuid NOT NULL DEFAULT uuidv7() UNIQUE,
    source_id       uuid NOT NULL REFERENCES evidence.source(id),
    file_node_id    uuid REFERENCES evidence.file_node(id),
    evidence_hash_id uuid REFERENCES evidence.evidence_hash(id),
    event_type      text NOT NULL                       -- the custody lifecycle transitions
                    CHECK (event_type IN ('collected','sealed','in_processing','verified',
                      'disputed','released','re_hashed','integrity_violation','superseded','accessed')),
    actor           text NOT NULL,                      -- person or service-account id
    occurred_at     timestamptz NOT NULL DEFAULT now(),
    occurred_certainty text NOT NULL DEFAULT 'exact'
                    CHECK (occurred_certainty IN ('exact','approximate','inferred','uncertain')),
    detail          jsonb NOT NULL DEFAULT '{}',        -- before/after status, sha256 checked, reason
    -- tamper-evident hash chain (pgcrypto digest(...,'sha256')); per-source chain
    prev_event_digest bytea,
    event_digest      bytea NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_custody_source ON evidence.custody_event (source_id, occurred_at);
CREATE INDEX IF NOT EXISTS idx_custody_type   ON evidence.custody_event (event_type, occurred_at DESC);

-- compute prev/this digest with pgcrypto, serialized per source (no overwrite of history)
CREATE OR REPLACE FUNCTION evidence.chain_custody_event() RETURNS trigger
  LANGUAGE plpgsql AS $$
BEGIN
    PERFORM pg_advisory_xact_lock(hashtextextended(NEW.source_id::text, 0));
    SELECT ce.event_digest INTO NEW.prev_event_digest
      FROM evidence.custody_event ce
     WHERE ce.source_id = NEW.source_id
     ORDER BY ce.seq DESC LIMIT 1;
    NEW.event_digest := digest(
      convert_to(
        coalesce(NEW.source_id::text,'') || '|' ||
        coalesce(NEW.file_node_id::text,'') || '|' ||
        coalesce(NEW.evidence_hash_id::text,'') || '|' ||
        NEW.event_type || '|' || NEW.actor || '|' ||
        to_char(NEW.occurred_at,'YYYY-MM-DD"T"HH24:MI:SS.US TZH:TZM') || '|' ||
        coalesce(NEW.detail::text,'{}') || '|' ||
        coalesce(encode(NEW.prev_event_digest,'hex'),''),
      'UTF8'),
      'sha256');
    RETURN NEW;
END $$;
CREATE TRIGGER custody_event_chain BEFORE INSERT ON evidence.custody_event
  FOR EACH ROW EXECUTE FUNCTION evidence.chain_custody_event();
CREATE TRIGGER custody_event_immutable BEFORE UPDATE OR DELETE ON evidence.custody_event
  FOR EACH ROW EXECUTE FUNCTION evidence.forbid_mutation();
```

> **pg_duckdb reach:** raw bytes never live in PG — `evidence.source.r2_bucket/r2_key` point
> at the R2 object-locked original; analytical reads use `SELECT … FROM read_parquet/read_csv`
> over the account-wide S3 secret (ADR-0030). `evidence.source` is the relational index of
> those objects, and `evidence_hash` proves byte-identity on read-back.

---

## 3. Decision table

| Table / field | Decision | Source (as-built / paper / prior) | Note |
|---|---|---|---|
| **`evidence` schema** as home for all of D1 | **adopt** | as-built E1 §0 | Re-home; paper's `provenance`/`raw_object`/`custody.*` schemas rejected (boundary). |
| `evidence.evidence_hash` (id/source_ref/algo/digest/hashed_at/blob_key/meta + 32B CHECK + digest idx) | **adopt (unchanged)** | as-built `0002`+`0003` | PK is the artifact anchor `normalized_record.artifact_id` FKs to — untouched. |
| `evidence_hash.level H1/H2/H3` | **merge** | paper §3.2 `custody_hash.level` → into as-built ledger | Folds the paper's separate `custody_hash` table into the one as-built ledger. |
| `evidence_hash.source_id / file_node_id` | **adapt** | paper `custody_hash.raw_id/artifact_id` | Re-pointed at the reconciled `evidence.source`/`file_node`. |
| `evidence_hash.record_locator / member_hash_ids / canon_version / md5_prefilter / computed_by` | **adopt** | paper §3.2/§6.2 | H2 locator, H3 Merkle members, reproducibility recipe, md5 pre-filter (P5). |
| `evidence_hash` immutability trigger | **adopt** | paper §6 (P4) | As-built table had no UPDATE/DELETE guard; added. |
| **`evidence.source`** (table) | **merge** | paper `evidence.raw_object` ⊕ E2 `messaging_documents` ⊕ A3 TraceIQ `data_source/original_json` | New raw-source registry; the §3-canonical `custody.source` flattened into `evidence`. |
| `source.sha256 / md5_prefilter / byte_size / mime_type` | **adopt** | paper §6.1; E2 `file_hash`/`file_size`/`file_type` | sha256 = identity (P5); md5 = CaseBible join pre-filter only. |
| `source.custodian / acquisition_method / verified_by / verified_at` | **adopt** | E2 `acquired_by/acquisition_method/verified_by/verified_date` | Doc-level custody fields promoted to the source registry. |
| `source.acquisition_source / origin_device_id / origin_account` | **adopt** | paper §4.2 (MP 1545-1566) | Upstream provenance. |
| `source.acquired_at_raw/_utc/_tz_offset/_certainty` | **adapt** | paper timestamp triple + A3 "precision class missing from ALL prior schemas" | Adds the exact/approximate/inferred/uncertain class A3 flags as required. |
| `source.provenance_tier / r2_bucket / r2_key / local_path` | **adopt** | paper §4.1 (R2 canonical vs D:/Backup corroborating) | R2 wins on mismatch unless a review rules otherwise. |
| `source.sensitivity_tier` (enum) | **adapt** | `0004` `disclosure_tier` **renamed** | The §5.1 bug fix — reuse the renamed enum for access classification. |
| `source.legal_sensitivity / privacy_sensitivity` | **adopt** | paper §4.2 | Drives redaction need; distinct from `sensitivity_tier`. |
| `source.{custody,extraction,processing,review,export}_status` (mutable whitelist) | **adapt** | paper §4.2 status quintet + E2/S1 `status` | Denormalized convenience state; authoritative history = `custody_event`. |
| `source.original_metadata vs derived_metadata` | **adopt** | paper §4.2; E2 `metadata`; S1 `raw_text/page_count/record_count` | Original never edited; derived clearly separated. |
| `source.supersedes_source_id` | **adopt** | paper §4.3 (corrected re-export = new object) | Append-only supersession, never in-place edit. |
| `source` write-once + status-whitelist trigger | **adopt** | paper §4.3 P1 | Identity/bytes immutable; only lifecycle columns mutable. |
| **`evidence.file_node`** (recursive decomposition) | **adopt** | paper §3 `custody.file_node` (MP 1566); E2 `messaging_attachments` (ocr_text/exif/is_screenshot) as node kinds | file→page→frame→screenshot→OCR→message→event tree; `ltree` path. |
| `file_node.extraction_confidence` | **adopt** | `0004` `confidence` domain | Reuses the as-built domain for OCR/parse confidence. |
| **`evidence.custody_event`** (append-only, hash-chained) | **adapt** | paper §10 `audit_log` (custody slice) + §3 `custody.custody_event` | Per-source chain-of-custody log; pgcrypto `digest(...,'sha256')` chain. |
| `custody_event` pgcrypto hash chain (`prev_event_digest`/`event_digest`) | **adopt** | paper §10 hash-chaining; addendum §A pgcrypto | Tamper-evident; deletion/edit breaks the chain. |
| E2 `messaging_documents` (as a standalone table) | **deprecate** | E2 §A | Its custody fields are absorbed into `evidence.source`; the messaging *content* tables land in the messaging domain and FK to `evidence.source`. |
| E2 message-level `content_hash` | **merge** (note) | E2 §B | Registered as an `evidence_hash` **H2** row (level='H2', file_node_id→message_unit), not a duplicate column store. |
| `source_ref` composite type (`0004`) | **preserve-as-note** | `0004`; E1 §5.2 collision | NOT used on `evidence_hash` (whose `source_ref` is a TEXT column); reserved for cross-store pointers elsewhere. Collision documented, not "fixed" (no SQL conflict). |
| paper `provenance.run/artifact/lineage_edge/review/redaction/export/*_version` | **defer (out of D1)** | paper §5-§11 | Cross-cutting provenance/lineage domain; will FK to `evidence_hash(id)` + `evidence.source(id)`. |

---

## 4. Migration notes (ALTER/CREATE to reach this on the LIVE DB)

> **Verify-before-claim (addendum §D.9):** diff against the live `agno-postgres:18-duckdb`
> catalog **before** applying. Confirm (a) PG major = 18 so `uuidv7()` resolves (E1 §5.5),
> (b) `pgcrypto`, `pg_trgm`, `ltree`, `btree_gist`/`btree_gin` are present (`0001`),
> (c) whether `0004` was hand-applied (so `disclosure_tier`/`confidence`/`source_ref` exist),
> (d) the live row-count of `evidence.evidence_hash` (for the backfill + `VALIDATE`).

1. **Type rename (bug fix).** `ALTER TYPE disclosure_tier RENAME TO sensitivity_tier;`
   guarded by the `DO $$ … EXCEPTION` block (no-op if `0004` was never applied or already
   renamed). Do **not** touch `analysis.normalized_record.disclosure_tier` (TEXT column,
   `contemporaneous|hindsight|discovered`) here — its rename to `knowledge_horizon` is an
   analysis-domain migration. If `0004` was never hand-applied on the live volume (E1 §5.4),
   the rename is skipped and `sensitivity_tier` must be created fresh:
   `CREATE TYPE sensitivity_tier AS ENUM ('public','restricted','sealed');`
2. **Create new tables** (idempotent `IF NOT EXISTS`): `evidence.source`,
   `evidence.file_node`, `evidence.custody_event` + their triggers/functions (§2 blocks 1-3,5).
3. **Extend the as-built ledger** (additive, online-safe): the
   `ALTER TABLE evidence.evidence_hash ADD COLUMN IF NOT EXISTS …` block. All new columns are
   nullable or have defaults, so existing rows + the `normalized_record.artifact_id` FK are
   unaffected. `level` back-fills to `'H1'` for legacy rows (they were file-level hashes).
4. **Backfill + validate the subject constraint.** Existing `evidence_hash` rows have
   `source_id IS NULL`; either (a) backfill `source_id` by joining the legacy `source_ref`
   text to the new `evidence.source` after sources are registered, then
   `ALTER TABLE evidence.evidence_hash VALIDATE CONSTRAINT evidence_hash_subject_ck;`, or
   (b) leave `NOT VALID` until the source registry is populated. Until validated, the CHECK
   guards only new inserts.
5. **Add the immutability trigger to `evidence_hash` last** — after any one-time backfill of
   `source_id`/`level` on legacy rows (the trigger blocks UPDATE, so backfill must precede it).
6. **Role grants (boundary enforcement, connection-level — not prompt):** ingestion service
   role `INSERT, SELECT` on `evidence.*`; agent read-only role `SELECT` only
   (`default_transaction_read_only` already enforces this per E1 §6). No role gets
   `UPDATE/DELETE` on `evidence.evidence_hash`, `file_node`, `custody_event`; `UPDATE` on
   `evidence.source` is permitted but the trigger restricts it to lifecycle columns.
7. **R2 object-lock** on `casebible-raw`/`nexus` is the storage-side half of write-once
   (paper §4.3) — verify immutable-retention is set; it is **not** expressible in PG DDL.

### Needs-human-review
- **Signing-key custody** for export-manifest signatures and periodic custody-chain anchoring
  (paper §13) — unspecified; needs an ADR (HSM vs pgcrypto key, rotation). Out of D1 but the
  `custody_event` chain head is the anchor point.
- **H2 canonicalization recipe** per source type (FB/Snapchat/call-log/XLSX) must be authored
  and version-pinned (`hash_canon_version`/`canon_version`) before H2/H3 are computed — coupled
  to brittle parser vintages (E2 §F, paper §13).
- **`evidence_hash` legacy backfill** (step 4): mapping the legacy free-text `source_ref` to
  `evidence.source.id` needs a human pass if the live table already holds rows.
- **`normalized_record.disclosure_tier` → `knowledge_horizon`** column rename is cross-domain
  (analysis); coordinate so the renamed `sensitivity_tier` type and the renamed column don't
  collide in review.
