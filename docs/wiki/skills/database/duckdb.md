# DuckDB — Skill Reference

## Overview
- **What**: Embedded columnar analytics database. Master clock and forensic vault for chain of custody. Tier 1 ingestion layer.
- **Version**: Node.js API (via @duckdb/node-api)
- **Category**: Database/Analytics
- **Installed In**: TS MCP Server (`src/services/DuckDbService.ts`), file-based (`./data/duckdb/forensic_vault.db`)
- **Role**: First-touch ingestion, SHA-256 hashing, temporal indexing, write tracking across all downstream tiers

## Architecture

DuckDB is the **master clock and forensic foundation**. Every piece of evidence is:
1. **Hashed at first touch** (SHA-256) for chain of custody
2. **Timestamped immediately** with nanosecond precision (master clock)
3. **Tracked through Pass 1 & Pass 2** enrichment stages
4. **Marked for write** to each downstream tier (LanceDB, Neo4j, PostgreSQL)

Single-writer model prevents race conditions; lazy singleton in TS MCP server ensures one DuckDB connection per process.

## Configuration

### Environment & Initialization
```typescript
// From ts-mcp-server/src/services/DuckDbService.ts
const config = {
  path: process.env.DUCKDB_PATH || './data/duckdb/forensic_vault.db',
  readOnly: false
};

class DuckDBClient {
  async initialize(): Promise<boolean> {
    const instance = await DuckDBInstance.create(this.config.path);
    const connection = await instance.connect();
    await this.createTables();
    return true;
  }
}
```

## Core Schema

### Forensic Vault Tables
```sql
-- Ingestion log: First-touch SHA-256 hash and metadata
CREATE TABLE ingestion_log (
  id VARCHAR PRIMARY KEY,              -- UUIDv7 for sortable insertion order
  source_hash VARCHAR UNIQUE NOT NULL, -- SHA-256 at first touch
  source_type VARCHAR,                 -- 'sms', 'imessage', 'facebook', 'whatsapp', 'email'
  source_name VARCHAR,                 -- Filename or source identifier
  raw_content VARCHAR,                 -- For text: full content; NULL for binary
  binary_path VARCHAR,                 -- For binaries: path in LanceDB multimodal vault
  ingested_at TIMESTAMP,               -- Master clock: NOW()
  pass1_status VARCHAR,                -- 'pending', 'processing', 'completed', 'failed'
  pass1_completed_at TIMESTAMP,        -- Timestamp of embedding/NER completion
  pass2_status VARCHAR,                -- Deduplication and conflict detection
  metadata JSON                        -- Arbitrary metadata from source parser
);

CREATE INDEX idx_source_hash ON ingestion_log(source_hash);
CREATE INDEX idx_ingested_at ON ingestion_log(ingested_at);

-- Normalized messages: Staging for enrichment
CREATE TABLE normalized_messages (
  id VARCHAR PRIMARY KEY,              -- UUIDv7
  ingestion_id VARCHAR REFERENCES ingestion_log(id),
  platform VARCHAR,                    -- 'sms', 'imessage', 'facebook', etc.
  sender VARCHAR,                      -- Extracted sender identifier
  recipient VARCHAR,                   -- Extracted recipient identifier
  content VARCHAR,                     -- Normalized message text
  timestamp TIMESTAMP,                 -- Original message timestamp
  embedding_status VARCHAR,            -- 'pending', 'completed'
  entity_status VARCHAR,               -- 'pending', 'completed'
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Write tracking: Which tier has received this evidence
CREATE TABLE write_tracking (
  id VARCHAR PRIMARY KEY,
  ingestion_id VARCHAR REFERENCES ingestion_log(id) UNIQUE,
  duckdb_written BOOLEAN DEFAULT false,
  lancedb_written BOOLEAN DEFAULT false,
  neo4j_semantic_written BOOLEAN DEFAULT false,
  neo4j_temporal_written BOOLEAN DEFAULT false,
  postgresql_written BOOLEAN DEFAULT false,
  last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## API Patterns (TS MCP Server)

### DuckDbVault Service
```typescript
// From ts-mcp-server/src/tools/DuckDbVault.ts
const vault = new DuckDbVault();

// Log ingestion at first touch (SHA-256 immediately)
await vault.logIngestion(
  sourceType: 'sms',
  sourceName: 'message_backup_2025.xml',
  rawContent: '<xml>...</xml>',
  metadata: { parser_version: '1.0', line_count: 10000 }
);
// Returns: { id: 'uuidv7-...', source_hash: 'sha256-hex-string' }

// Get pending Pass 1 (embeddings)
const pending = await vault.getPendingPass1(limit: 50);

// Mark evidence as written to downstream tier
await vault.updateWriteTracking(
  ingestionId: 'uuid-...',
  tier: 'postgresql',  // 'lancedb' | 'neo4j_semantic' | 'neo4j_temporal' | 'postgresql'
  written: true
);

// Update Pass 1 status
await vault.updatePass1Status(
  ingestionId: 'uuid-...',
  status: 'completed'  // 'pending' | 'processing' | 'completed' | 'failed'
);
```

### Hashing Pattern (SHA-256 at First Touch)
```sql
-- In logIngestion(), compute SHA-256 of raw content
SELECT sha256(raw_content) AS source_hash
FROM ingestion_log
WHERE id = 'uuid-...';

-- Deduplication: Check if source_hash already exists
SELECT COUNT(*) FROM ingestion_log
WHERE source_hash = 'sha256-hex-string';
```

### UUIDv7 Generation
```typescript
// From ts-mcp-server/src/services/DuckDbService.ts
import { uuidv7 } from 'uuidv7';

const ingestionId = uuidv7();  // Sortable by insertion timestamp
```

## Known Gaps & Future Work

### Missing: Read/Query Tool
Currently, DuckDB is **write-only** from MCP perspective. The Python/TS servers cannot easily query the forensic vault. Need:
- `duckdb_query(sql, params)` tool in TS MCP Server
- Read-only connection for audit queries
- Stream large result sets without memory overflow

### Missing: DuckDB → PostgreSQL Pipeline
Ingestion data lives in DuckDB but must be **exported to PostgreSQL** for canonical storage:
- Need ETL step: `duckdb_export_to_postgres(ingestion_id, tier)`
- Should mirror write_tracking status in PostgreSQL's evidence table
- Currently manual or handled in downstream services

### DuckDbVault Singleton Issue
Each call to `new DuckDbVault()` creates a new instance. Should implement **lazy singleton**:
```typescript
let _duckdb_vault: DuckDbVault | null = null;
function getDuckDbVault(): DuckDbVault {
  if (!_duckdb_vault) {
    _duckdb_vault = new DuckDbVault();
    _duckdb_vault.initialize();
  }
  return _duckdb_vault;
}
```

## Integration Points

- **TS MCP Server**: Ingestion logging via DuckDbVault; tracking writes to downstream tiers
- **Semantica (Py MCP)**: Reads normalized messages, extracts entities/relations, marks Pass 1 complete
- **PostgreSQL**: DuckDB data exported/synced to PostgreSQL evidence table
- **LanceDB**: Multimodal embeddings written to LanceDB vault; write_tracking updated
- **Neo4j**: Temporal facts exported to Neo4j for graph-based conflict detection

## Common Pitfalls

- **Single-Writer Model**: Don't spawn multiple DuckDB connections to the same file. Use singleton.
- **Concurrent Writes**: DuckDB blocks writes; queuing system needed for high-concurrency ingestion.
- **Source Hash Collisions**: SHA-256 is cryptographically unique, but verify UNIQUE constraint is enforced.
- **Pass 1 Blocking**: If embeddings fail, mark status='failed' and alert; don't block downstream ingestion.
- **Write Tracking Deadlock**: Update write_tracking atomically; don't leave it in inconsistent state.
- **Timestamp Precision**: Master clock should be nanosecond; use CURRENT_TIMESTAMP or explicit datetime.

## References
- [DuckDB Documentation](https://duckdb.org/docs/)
- [DuckDB Node.js API](https://duckdb.org/docs/api/nodejs/)
- [SHA-256 Hashing](https://en.wikipedia.org/wiki/SHA-2)
- [UUIDv7 (Sortable by Time)](https://www.ietf.org/archive/id/draft-ietf-uuidrev-rfc4122bis-07.html#section-6.7)
- [Chain of Custody Best Practices](https://en.wikipedia.org/wiki/Chain_of_custody)
