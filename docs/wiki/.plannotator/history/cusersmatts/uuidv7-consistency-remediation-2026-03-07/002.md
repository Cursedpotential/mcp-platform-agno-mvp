
# UUIDv7 Consistency Remediation Plan (Updated)

## Why This Matters
UUID generation is the **first thing that happens** when evidence enters the system. If it's inconsistent (v4 vs v7, truncated vs full, hand-rolled vs library), everything downstream — dedup, cross-tier linking, chronological ordering, chain of custody — is built on sand.

---

## Key Findings

### 1. No Existing Data (Good News)
The codebase has **zero seed files, migrations, or database files**:
- ✅ 0 seed files
- ✅ 0 migration files  
- ✅ 0 `.sql` files with INSERT statements
- ✅ 0 database files (`.db`, `.sqlite`, `.duckdb`)
- Only 2 hardcoded UUIDs in cassette-based test files (thread identifiers, not database records)

**Conclusion**: No migration needed. All UUIDs we fix will be fresh UUIDv7s when records are created.

### 2. WunderGraph's Role (Clarified)
WunderGraph Cosmo is an **API gateway** that sits on top of all databases. It does NOT generate UUIDs — it just passes through whatever the databases/resolvers return. Only ONE file needs fixing in WunderGraph:
- `cosmo/subgraphs/evidence-ingestion/resolvers.ts` — has inline hand-rolled UUIDv7 implementation (P2)

### 3. Architecture Decision: MySQL Evidence Index
You correctly identified the need for a **master lookup table**. Currently:
- DuckDB `ingestion_log` has hash, UUID, filename (closest to master index)
- But no **unified cross-tier lookup** that joins all tiers together
- Tables are fragmented across DuckDB, PostgreSQL, and MySQL

**Solution**: Add a new `evidence_master_index` table in MySQL (Tier 5) that provides a unified lookup for hash→UUID→filename across all tiers.

---

## Agent Delegation Strategy

Per your instruction to use domain-specific skills:

| Task | Agent | Skills/Context7 Used |
|------|-------|---------------------|
| Drizzle schemas (MySQL tables) | `@impl` | Context7: Drizzle ORM docs for UUID columns, indexes, generated columns |
| Python dedup service | `@impl` | Context7: uuid-utils Python package docs |
| GraphQL subgraphs | `@impl` | Context7: GraphQL Federation docs |
| MySQL evidence index table | `@impl` | Context7: SQL/MySQL best practices for indexing |

---

## Consolidation: One UUIDv7 Implementation

**Current state**: 3 separate implementations
1. `uuidv7` npm package (used by coordinator, readers, identity-service) ✅ CORRECT
2. `server/mcp/utils/uuidv7.ts` — 83-line hand-rolled version (used by duckdb-vault, ingestion-log, provenance-chain)
3. Inline implementation in `cosmo/subgraphs/evidence-ingestion/resolvers.ts`

**Plan**: Consolidate to the `uuidv7` npm package everywhere. Delete the hand-rolled implementations.

For Python (`deduplication_service.py`): Use the `uuid_utils` Rust-based package (100-200x faster than Python stdlib).

---

## Execution Steps

### Phase 1: Consolidate TypeScript UUIDv7 (P2 items first — they enable the rest)

| Step | File | Change | Risk |
|------|------|--------|------|
| 1a | `server/mcp/utils/uuidv7.ts` | Replace entire file with: `export { uuidv7 } from 'uuidv7'` | None — drop-in replacement |
| 1b | `cosmo/subgraphs/evidence-ingestion/resolvers.ts` | Remove inline UUIDv7 impl, import from `uuidv7` npm package | Low |
| 1c | Verify `uuidv7` npm package is in `package.json` dependencies (not just devDeps) | Check only | None |

### Phase 2: Add MySQL Evidence Master Index (New Architecture Addition)

**Table Design** (Drizzle schema + SQL):

```sql
CREATE TABLE evidence_master_index (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  source_hash VARCHAR(64) NOT NULL UNIQUE,  -- SHA-256 (source of truth)
  evidence_id VARCHAR(36) NOT NULL,          -- UUIDv7 (primary key in this table)
  original_filename VARCHAR(1024) NOT NULL, -- Source filename
  tier VARCHAR(16) NOT NULL,                 -- 'duckdb'|'lancedb'|'neo4j'|'postgres'|'mysql'
  storage_path TEXT,                         -- Where it lives (e.g., '/lancedb/<hash>.lance')
  creation_timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_accessed TIMESTAMP,                   -- For cleanup/optimization
  
  INDEX idx_evidence_id (evidence_id),
  INDEX idx_source_hash (source_hash),
  INDEX idx_tier (tier)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

| Step | File | Change |
|------|------|--------|
| 2a | `server/drizzle/evidence-master-index.ts` | Create Drizzle schema for `evidence_master_index` table |
| 2b | `server/drizzle/schema.ts` | Export the new schema, add to global schema registry |
| 2c | `server/mcp/storage/duckdb-forensic-vault.ts` | After UUIDv7 generation, insert record into `evidence_master_index` table |

**Reasoning**: This provides a single source of truth for "where is this hash/evidence right now?" across all 5 tiers.

### Phase 3: Fix P0 — Storage Tier Violations

| Step | File | Lines | Change |
|------|------|-------|--------|
| 3a | `server/mcp/storage/lancedb.ts` | 139-140, 170-171 | `crypto.randomUUID()` → `import { uuidv7 } from 'uuidv7'` + `uuidv7()` |
| 3b | `server/mcp/storage/neo4j/semantic_facts.ts` | 172, 206, 241 | `crypto.randomUUID()` → `import { uuidv7 } from 'uuidv7'` + `uuidv7()` |
| 3c | `server/services/deduplication_service.py` | 135, 475, 886, 1015, 1078 | `uuid.uuid4()` → `uuid_utils.uuid7()` (add `uuid_utils` to Python deps) |

### Phase 4: Fix P1 — Schema Defaults & Plugins

| Step | File | Change |
|------|------|--------|
| 4a | `server/mcp/plugins/agent-memory.ts` | Replace `import { v4 as uuidv4 } from 'uuid'` → `import { uuidv7 } from 'uuidv7'`, update 4 call sites |
| 4b | `server/mcp/plugins/pattern-persistence.ts` | Same pattern — replace `uuidv4` import + 5 call sites |
| 4c | `server/mcp/storage/hierarchy-storage.ts` | Remove `.slice(0, 8)` truncation. Use full `uuidv7()`. This is the **collision time bomb** fix. |
| 4d | `server/drizzle/message-schemas.ts` | For ~15 tables with `.defaultRandom()`: Change to `.$defaultFn(() => uuidv7())` so new records get UUIDv7 by default. Existing data is unaffected (no migration needed). |

### Phase 5: Verify No Existing Data

| Step | Action |
|------|--------|
| 5a | Verify `grep -r "INSERT INTO\|seed\|migration" server/` returns nothing (confirmed by exploration) |
| 5b | TypeScript build check: `pnpm tsc --noEmit` |
| 5c | Python check: Ensure no database files exist that would have old UUIDs |

### Phase 6: WunderGraph Cleanup (P2)

| Step | File | Change |
|------|------|--------|
| 6a | `cosmo/subgraphs/evidence-ingestion/resolvers.ts` | Remove inline UUIDv7 impl, import from `uuidv7` npm package (done in Phase 1b) |

---

## What We're NOT Changing (And Why)

- **`externalId` hash truncation in readers** (Facebook, WhatsApp): These are 16-char SHA-256 truncations used for platform-specific message correlation, not primary keys. 64 bits of hash is collision-safe for message-level dedup within a single conversation. Leave as-is.
- **MySQL auto-increment IDs** (Tier 5): MySQL handles app metadata (users, API keys). Auto-increment is appropriate here — these aren't evidence records.
- **Existing data**: None exists in databases. Only 2 UUIDs in test cassette files (thread identifiers, not database records).

---

## Estimated Work

| Phase | Time | Notes |
|-------|------|-------|
| 1 | 15 min | Consolidate 2 files, low risk |
| 2 | 30 min | Create Drizzle schema + add index table |
| 3 | 30 min | Fix 3 files with UUID violations |
| 4 | 45 min | Fix 4 files (Drizzle schemas need care) |
| 5 | 10 min | Verification, no agents needed |
| 6 | 5 min | WunderGraph cleanup (already done in 1b) |

**Total: ~2.5 hours of agent execution time**

---

## Dependencies to Add

1. **NPM**: `uuidv7` (if not already in `package.json`)
2. **Python**: `uuid-utils` (pip install, import as `uuid_utils`)

---

## Success Criteria

- ✅ All TypeScript files use `uuidv7()` from `uuidv7` npm package (no `crypto.randomUUID()`, no `uuidv4`)
- ✅ All Python files use `uuid_utils.uuid7()` (no `uuid.uuid4()`)
- ✅ No UUID truncation in primary key fields
- ✅ Drizzle schemas use `.$defaultFn(() => uuidv7())` for new records
- ✅ MySQL `evidence_master_index` table created with proper indexes
- ✅ No existing database data to migrate
- ✅ TypeScript build passes: `pnpm tsc --noEmit`
- ✅ `grep -r "crypto.randomUUID\|uuid4\|uuidv4\|uuid\.v4" server/ cosmo/` returns 0 results (except test files)
