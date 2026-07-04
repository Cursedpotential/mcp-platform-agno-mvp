# E1 — As-Built Database Inventory (Ground Truth)

> _Byline: Claude Code · Opus 4.8 · 2026-06-30_
>
> Source of truth: the four migration files under `Agno-MCP-Platform/sql/`
> (`0001_init_extensions.sql`, `0002_schema.sql`, `0003_normalized_records.sql`,
> `0004_custom_types.sql`). This is a static read of the DDL as written. Where the
> DDL's apply-once semantics mean the live DB may differ from the file, that drift is
> flagged. Agno-managed tables (created by the Agno runtime, not by us) are listed but
> not column-decomposed because their DDL is not in this repo.

---

## 0. Schemas

| Schema | Purpose | Security boundary |
|---|---|---|
| `public` | HITL audit tables (`agent_run`, `approval_request`), ChatMiner output (`transcript_insight`), plus all Agno-managed tables (knowledge vectors/contents, learning stores, `agno_approvals`, sessions). | Mixed. Agno reads/writes its own tables. Audit tables are legacy (no live writer). |
| `evidence` | Raw/source data + custody/integrity hashes. | **Read-only to agents**, enforced at the connection (`readonly_engine` + `default_transaction_read_only`), NOT in the prompt. |
| `analysis` | Derived/normalized artifacts emitted by parsers. | **Write-after-approval** only — writes permitted only after a recorded HITL approval. |

Created explicitly: `evidence`, `analysis` (`0002`). `public` is the implicit default
schema — every unqualified table below (`agent_run`, `approval_request`,
`transcript_insight`) lands in `public`.

Design intent (`0002` header): `evidence` = RO source; `analysis` = derived,
write-after-approval; `public` = HITL audit + Agno-owned. Explicit non-goal: there is
**no** `learned_knowledge` table — the native Agno LearningMachine owns that (ADR-0004).

---

## 1. Extensions (`0001`)

All run at first boot via `/docker-entrypoint-initdb.d` (once, on an empty data dir).

**Required / always created:**
- `vector` — embeddings (required)
- `pg_trgm` — fuzzy/trigram match (feeds dedup)
- `pgcrypto` — hashing only (digest/hmac for custody); **not** used for UUIDs (PG18 has native `uuidv7()`)
- `btree_gin` — mixed scalar+text composite indexes
- `btree_gist` — powers `EXCLUDE` constraints on `tstzrange` (bitemporal no-overlap)
- `unaccent` — accent-insensitive FTS
- `citext` — case-insensitive text (names/emails/handles)
- `ltree` — hierarchical labels (MCL factor trees, taxonomies)
- `hstore` — key-value attr bags
- `fuzzystrmatch` — soundex/levenshtein/metaphone (entity resolution)

**Guarded / best-effort (wrapped in `DO $$ … EXCEPTION WHEN OTHERS`):** only succeed on
the custom PG image; a stock image logs a NOTICE and continues:
- `postgis` — geography/GiST spatial index (backs `geo_point` domain in `0004`)
- `pg_duckdb` — DuckDB engine in PG (owner decision 2026-06-10)
- `pg_stat_statements` — requires preload via custom image CMD

**Notes / drift:**
- `uuidv7()` is assumed **native** → requires **PostgreSQL 18**. If the live engine is
  < PG18, every `DEFAULT uuidv7()` fails. (Hard dependency, undeclared as a guard.)
- Multicorn2 FDW intentionally removed (ADR-0032); `postgres_fdw`/`file_fdw` remain in-base.
- `pg_textsearch` deliberately not enabled (deferred until Agno hybrid search proves insufficient).

---

## 2. Tables

### 2.1 `public.agent_run` (`0002`) — LEGACY (superseded by `agno_approvals`)

| Column | Type | Constraints / Default |
|---|---|---|
| `id` | UUID | PK, `DEFAULT uuidv7()` |
| `agent_name` | TEXT | NOT NULL |
| `run_type` | TEXT | NOT NULL, CHECK IN (`platform`,`builder`) |
| `status` | TEXT | NOT NULL, CHECK IN (`queued`,`running`,`awaiting_approval`,`completed`,`failed`,`cancelled`) |
| `user_prompt` | TEXT | NOT NULL |
| `summarized_plan` | TEXT | nullable |
| `approval_required` | BOOLEAN | NOT NULL, DEFAULT TRUE |
| `started_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() |
| `completed_at` | TIMESTAMPTZ | nullable |
| `error_message` | TEXT | nullable |

Index: `idx_agent_run_status (status, started_at DESC)`.
**Status:** superseded 2026-06-12 by native `agno_approvals`; kept only for provenance,
no code writes here.

### 2.2 `public.approval_request` (`0002`) — LEGACY (superseded by `agno_approvals`)

| Column | Type | Constraints / Default |
|---|---|---|
| `id` | UUID | PK, `DEFAULT uuidv7()` |
| `agent_run_id` | UUID | FK → `agent_run(id)` ON DELETE CASCADE |
| `run_id` | UUID | nullable (Agno run id for `continue_run`) |
| `paused_tool` | TEXT | nullable |
| `requested_action` | TEXT | NOT NULL |
| `requested_by_agent` | TEXT | NOT NULL |
| `risk_level` | TEXT | NOT NULL, CHECK IN (`low`,`medium`,`high`,`critical`) |
| `approval_status` | TEXT | NOT NULL, DEFAULT `pending`, CHECK IN (`pending`,`approved`,`rejected`,`expired`) |
| `requested_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() |
| `decided_at` | TIMESTAMPTZ | nullable |
| `decided_by` | TEXT | nullable |
| `decision_notes` | TEXT | nullable |

Index: `idx_approval_request_status (approval_status, requested_at DESC)`.
**Status:** legacy, same as `agent_run`.

### 2.3 `evidence.evidence_hash` (`0002` + `0003` ALTERs) — custody/integrity

| Column | Type | Constraints / Default |
|---|---|---|
| `id` | UUID | PK, `DEFAULT uuidv7()` |
| `source_ref` | TEXT | NOT NULL — what was hashed (path/object key/record id) |
| `algo` | TEXT | NOT NULL, DEFAULT `sha256` |
| `digest` | BYTEA | NOT NULL — RAW bytes (32B for sha256) |
| `hashed_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() |
| `blob_key` | TEXT | nullable — added by `0003` (`ADD COLUMN IF NOT EXISTS`); where the write-once blob landed |
| `meta` | JSONB | NOT NULL, DEFAULT `'{}'` — added by `0003` |

Table-level CHECK: `algo <> 'sha256' OR octet_length(digest) = 32` (sha256 digests must be 32 bytes).
Index: `idx_evidence_hash_digest (digest)`.
Append-only by design (custody columns grow additively).

### 2.4 `public.transcript_insight` (`0002`) — ChatMiner output

| Column | Type | Constraints / Default |
|---|---|---|
| `id` | UUID | PK, `DEFAULT uuidv7()` |
| `source_file` | TEXT | NOT NULL |
| `platform` | TEXT | nullable |
| `insight_type` | TEXT | NOT NULL |
| `content` | TEXT | NOT NULL |
| `metadata` | JSONB | NOT NULL, DEFAULT `'{}'` |
| `mined_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() |

Index: `idx_transcript_insight_type (insight_type, mined_at DESC)`.

### 2.5 `analysis.normalized_record` (`0003`) — canonical record (bitemporal spine)

| Column | Type | Constraints / Default |
|---|---|---|
| `id` | UUID | PK, `DEFAULT uuidv7()` |
| `artifact_id` | UUID | NOT NULL, FK → `evidence.evidence_hash(id)` |
| `record_type` | TEXT | NOT NULL, CHECK IN (`message`,`call`,`event`,`media`) |
| `source` | TEXT | NOT NULL — parser/source key (e.g. `chatgpt-export`) |
| `conversation_id` | TEXT | nullable |
| `role` | TEXT | nullable — sender/author role |
| `participants` | JSONB | NOT NULL, DEFAULT `'[]'` |
| `content` | TEXT | NOT NULL, DEFAULT `''` |
| `occurred_at` | TIMESTAMPTZ | nullable — **VALID TIME** (when it happened) |
| `knowledge_time` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() — when we learned it |
| `disclosure_tier` | **TEXT** | NOT NULL, DEFAULT `contemporaneous`, **CHECK IN (`contemporaneous`,`hindsight`,`discovered`)** |
| `attrs` | JSONB | NOT NULL, DEFAULT `'{}'` |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() |

Indexes: `idx_normrec_artifact (artifact_id)`, `idx_normrec_conv (source, conversation_id)`,
`idx_normrec_occurred (occurred_at)`.
This is the cross-store bitemporal substrate: valid time (`occurred_at`) + knowledge time
(`knowledge_time`) + disclosure tier drive the Part-2 knowledge-horizon replay.

### 2.6 Agno-managed tables (created by the Agno runtime, NOT in this repo's SQL)

Live in `public`. DDL owned by Agno (≈ 2.6.13); columns not reproduced here:
- `agno_approvals` — native HITL approvals store; `@approval` tools write here, `/approvals` serves them. **Supersedes** `agent_run` + `approval_request`.
- Knowledge store — vector/contents tables for Agno hybrid search (embeddings + content).
- Learning store(s) — the native LearningMachine's `learned_knowledge` equivalent (ADR-0004).
- Session/memory tables — Agno session + memory persistence.

> These must be enumerated against the **live** database (`information_schema`) to be
> authoritative; they cannot be reconstructed from this repo.

---

## 3. Custom Types (`0004`)

> **Apply-once caveat:** `0004` runs automatically only on an **empty** data dir (after
> `0001`–`0003`). On an existing `pgdata` volume it must be applied **by hand**
> (`psql … -f sql/0004_custom_types.sql`). So on the live DB these types may or may not
> exist — a primary drift axis. All objects are idempotent-guarded.

### 3.1 ENUMs

| Type | Values | Intended use |
|---|---|---|
| `entity_type` | `person`,`org`,`project`,`tech`,`location`,`concept` | Entity classification |
| `temporal_class` | `historical`,`current`,`future` | Temporal staging |
| `event_type` | `milestone`,`decision`,`meeting`,`incident`,`change`,`memory`,`upcoming` | Event classification |
| `disclosure_tier` | **`public`,`restricted`,`sealed`** | (comment says) NormalizedRecord knowledge-time gating — **see §5 BUG** |
| `mcl_factor` | `a`…`l` | MCL 722.23 best-interest factors |
| `source_system` | `postgres`,`neo4j`,`milvus`,`surrealdb` | Which store an id/record came from |
| `match_method` | `exact`,`resolved`,`manual` | How an id_xref link was established |

### 3.2 DOMAINS

| Type | Base | Constraint | Notes |
|---|---|---|---|
| `confidence` | `numeric(4,3)` | `VALUE IS NULL OR (VALUE >= 0 AND VALUE <= 1)` | 0.000–1.000 confidence score |
| `canonical_id` | `uuid` | (none) | Comment says "lowercase-hyphenated uuid **string**" but base type is `uuid`, not `text` — doc/impl mismatch (§5) |
| `geo_point` | `geography(Point, 4326)` | (PostGIS) | WGS84 GPS point; **guarded** — skipped with NOTICE if PostGIS type absent |

### 3.3 COMPOSITE TYPES

| Type | Fields | Notes |
|---|---|---|
| `source_ref` | `system source_system`, `native_id text`, `locator text` | Provenance pointer; usage note suggests `source_ref[]` columns. **Name collides** with `evidence_hash.source_ref` (a TEXT column) — §5 |

### 3.4 Usage notes (NOT executed — `0004` tail)

Documentation only; no objects created:
- Bitemporal Relationship validity + no-overlap via `tstzrange` + `EXCLUDE USING gist (...)`.
- Hierarchies via `ltree`. Fuzzy match via `pg_trgm` / `levenshtein`. Geo KNN via GiST `<->`.

---

## 4. Cross-Reference: which types are actually used

| Custom type | Used by a column in these migrations? |
|---|---|
| `entity_type`, `temporal_class`, `event_type`, `mcl_factor`, `source_system`, `match_method` | **No** — defined for future tables; orphan in this DDL |
| `disclosure_tier` (enum) | **No** — the only `disclosure_tier` column (`normalized_record`) uses **TEXT+CHECK**, not this enum (§5) |
| `confidence`, `canonical_id`, `geo_point` (domains) | **No** — orphan in this DDL |
| `source_ref` (composite) | **No** — orphan in this DDL |

Every type in `0004` is currently **unreferenced** by any table created in `0001`–`0003`.
They are forward-declarations for tables not yet written here (Entity / Relationship /
Event / id_xref spine described in `PROJECT_CANON`).

---

## 5. Inconsistencies & Bugs

### 5.1 `disclosure_tier` DOUBLE DEFINITION (primary bug)

`disclosure_tier` exists as **two incompatible things** with **disjoint vocabularies and
different semantics**:

- **`0003`**: `analysis.normalized_record.disclosure_tier` is **`TEXT NOT NULL DEFAULT
  'contemporaneous' CHECK (disclosure_tier IN ('contemporaneous','hindsight',
  'discovered'))`**. Semantics = **knowledge-horizon / temporal disclosure** (when a fact
  became known relative to the event).
- **`0004`**: `CREATE TYPE disclosure_tier AS ENUM ('public','restricted','sealed')`, with
  an inline comment claiming it is "for bitemporal knowledge-time gating
  (NormalizedRecord)". Semantics = **access sensitivity / classification**.

Consequences:
1. The enum named `disclosure_tier` is **never used** — the column it claims to serve uses
   a TEXT CHECK with a completely different value set.
2. The two value sets do not overlap at all
   (`contemporaneous|hindsight|discovered` vs `public|restricted|sealed`), so they cannot
   be reconciled by a simple cast — they encode two different concepts under one name.
3. The `0004` comment is misleading: it documents the enum as gating the NormalizedRecord,
   which is false. The `0003` header comment (lines 6–9) likewise describes the column's
   tier as `contemporaneous | hindsight | discovered`, contradicting `0004`.
4. Anyone later altering `normalized_record.disclosure_tier` to use `TYPE disclosure_tier`
   (the natural assumption from the name) would silently change the meaning and reject all
   existing values.

**Recommended resolution (for the reconciliation phase, not applied here):** rename one of
them. The temporal column should be e.g. `knowledge_horizon`/`disclosure_horizon`
(values `contemporaneous|hindsight|discovered`); reserve the `disclosure_tier` enum name
for access classification (`public|restricted|sealed`) — which aligns with the
schema-level security boundary (evidence RO / analysis approval / public). Then decide
whether `normalized_record` needs the access-tier enum as a separate column.

### 5.2 `source_ref` name collision

`0004` defines a **composite TYPE `source_ref`**, while `0002`/`0003` already use
`source_ref` as a **TEXT column name** on `evidence.evidence_hash`. No hard SQL conflict
(types and columns share no namespace), but it is a readability/foot-gun trap: a future
`source_ref source_ref` column declaration reads ambiguously, and the usage note's
`source_ref[]` suggestion clashes conceptually with the existing scalar TEXT column.

### 5.3 `canonical_id` domain doc/impl mismatch

Comment: "canonical lowercase-hyphenated uuid **string**". Implementation:
`CREATE DOMAIN canonical_id AS uuid` (binary `uuid`, no text form, no
lowercase-hyphen normalization). The comment describes a `text` domain that was not built.

### 5.4 Apply-once drift (`0004`, and partly `0003`)

- `0004` does **not** auto-apply on an existing `pgdata` volume — must be run by hand. The
  set of custom types present on the live DB is therefore unknown from the files alone and
  must be verified against `information_schema`/`pg_type`.
- `0003` is written to be idempotent and "applied manually on the live DB AND kept for
  fresh init," but its `normalized_record` table only auto-creates on fresh init for the
  same reason. Verify table existence on the live DB.

### 5.5 Hard PG18 dependency, ungated

Every PK uses `DEFAULT uuidv7()`, assumed native to PG18. Unlike the extension blocks,
this is **not** guarded — on a < PG18 engine all four tables fail to create. Confirm the
live engine major version.

### 5.6 PostGIS-conditional objects

`postgis` (and thus `geo_point` domain) are best-effort. On a stock image they are
silently skipped (NOTICE only). Any later DDL referencing `geo_point` would fail on such an
image. Confirm PostGIS presence on the live DB before relying on `geo_point`.

### 5.7 Legacy audit tables still present

`agent_run` + `approval_request` are superseded by `agno_approvals` but remain in the
schema with no live writer. Live HITL state must be read from `agno_approvals`, not these.
They are dead-but-present provenance tables; treat as read-only history.

---

## 6. Security-Boundary Semantics (summary)

- **`evidence` (RO):** agents connect through a read-only engine
  (`default_transaction_read_only`) — the boundary is enforced at the DB connection, not by
  prompt instruction. Holds raw source + custody hashes (`evidence_hash`), append-only.
- **`analysis` (write-after-approval):** derived artifacts (`normalized_record`) may be
  written only after a recorded HITL approval (now in `agno_approvals`). FK from
  `normalized_record.artifact_id` → `evidence.evidence_hash(id)` ties every derived record
  back to a custody-hashed source artifact.
- **`public` (audit + Agno-owned):** legacy HITL audit (`agent_run`,`approval_request`),
  ChatMiner output (`transcript_insight`), and all Agno-managed stores (`agno_approvals`,
  knowledge vectors/contents, learning, sessions/memory). The live approval/learning state
  lives here, owned by Agno.
