# PostgreSQL with pgvector — Skill Reference

## Overview
- **What**: Unified relational database consolidating MySQL into PostgreSQL. pgvector extension for semantic search. Single source of truth for forensic evidence.
- **Version**: 16+ (pgvector/pgvector:pg16)
- **Category**: Database/Relational
- **Installed In**: Docker service `postgres` (port 5432, evidence database)
- **Role**: Forensic tier — canonical storage for entities, relations, and evidence metadata

## Architecture

PostgreSQL is the **consolidated relational tier** for all structured forensic data. It replaced earlier MySQL-based evidence storage and now serves as:
- Entity store (persons, devices, locations, etc.) with pgvector embeddings
- Relation store (connections between entities with temporal validity)
- Evidence metadata (chain of custody, confidence scores, source provenance)
- Unified schema bridging DuckDB ingestion → LanceDB vectors → Neo4j graph

## Configuration

### Environment Variables
```
PG_HOST: postgres (service name in docker-compose)
PG_PORT: 5432
PG_USER: dial
PG_PASSWORD: ${POSTGRES_PASSWORD:-dial_password}
PG_DATABASE: evidence
DATABASE_URL: postgresql://dial:password@postgres:5432/evidence
```

### Docker Service
```yaml
postgres:
  image: pgvector/pgvector:pg16      # pg16 + pgvector extension pre-loaded
  restart: always
  ports:
    - "5432:5432"
  environment:
    POSTGRES_USER: dial
    POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-dial_password}
    POSTGRES_DB: evidence
  volumes:
    - pgdata:/var/lib/postgresql/data
    - ./init/postgres:/docker-entrypoint-initdb.d
```

## Core Schema

### Entities Table
```sql
CREATE TABLE entities (
  id UUID PRIMARY KEY,
  name VARCHAR NOT NULL,
  entity_type VARCHAR,        -- person, device, phone_number, email, location, etc.
  embedding vector(768),      -- Semantica 768-dim embedding (all-MiniLM-L6-v2)
  metadata JSONB,             -- source_hash, platform, first_seen, last_seen
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- HNSW index for fast semantic similarity search (vector_cosine_ops)
CREATE INDEX entities_embedding_hnsw ON entities USING hnsw (embedding vector_cosine_ops);
CREATE INDEX entities_type_idx ON entities(entity_type);
CREATE INDEX entities_metadata_gin ON entities USING gin(metadata);
```

### Evidence Table (New)
```sql
CREATE TABLE evidence (
  id UUID PRIMARY KEY,
  source_hash VARCHAR NOT NULL UNIQUE,  -- SHA-256 at first touch (DuckDB)
  ingestion_id VARCHAR,                 -- Foreign key to DuckDB forensic_vault
  source_type VARCHAR,                  -- 'sms', 'imessage', 'facebook', 'whatsapp', 'email'
  platform VARCHAR,                     -- Normalized platform name
  timestamp TIMESTAMPTZ NOT NULL,       -- When evidence was created
  entities UUID[] DEFAULT '{}',         -- Array of entity IDs in this evidence
  metadata JSONB,                       -- provenance, confidence, extraction_status
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX evidence_source_hash_idx ON evidence(source_hash);
CREATE INDEX evidence_timestamp_idx ON evidence(timestamp DESC);
CREATE INDEX evidence_type_idx ON evidence(source_type);
```

### Relations Table
```sql
CREATE TABLE relations (
  id UUID PRIMARY KEY,
  source_id UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
  relation_type VARCHAR,                -- 'communicates_with', 'located_at', 'owns', etc.
  target_id UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
  confidence DOUBLE,                    -- 0.0-1.0
  temporal_range TSRANGE,               -- Validity period [start, end)
  evidence_id UUID REFERENCES evidence(id),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX relations_source_idx ON relations(source_id);
CREATE INDEX relations_target_idx ON relations(target_id);
CREATE INDEX relations_temporal_idx ON relations USING gist(temporal_range);
```

## API Patterns (TS MCP Server)

### PostgresWriter Service
```typescript
// From ts-mcp-server/src/tools/PostgresWriter.ts
const writer = new PostgresWriter(process.env.DATABASE_URL);

// Insert evidence record
await writer.writeRecord('evidence', {
  id: uuidv7(),
  source_hash: sha256('sms-content'),
  source_type: 'sms',
  timestamp: new Date(),
  metadata: { platform: 'sms', confidence: 0.95 }
});

// Query with caution — postgres_raw_query exposes forensic data
const result = await writer.query(
  'SELECT * FROM entities WHERE entity_type = $1',
  ['person']
);
```

### Semantic Search Pattern
```sql
-- Find similar entities by embedding
SELECT id, name, embedding <-> $1::vector AS distance
FROM entities
WHERE entity_type = 'person'
ORDER BY embedding <-> $1::vector
LIMIT 10;
```

## Security Considerations

### postgres_raw_query Risk
The `query()` method in PostgresWriter allows **arbitrary SQL execution** with parameters. On forensic data, this is a **critical attack surface**:
- Avoid exposing raw query interface to untrusted agents
- Always use parameterized queries (prepared statements)
- Log and audit all query executions to evidence database
- Implement row-level security policies for multi-tenant isolation

### Chain of Custody
- All evidence must have `source_hash` (SHA-256 from DuckDB)
- Never update `source_hash` or `ingestion_id` after insertion
- Timestamp all modifications with user/agent context
- Use PostgreSQL roles to enforce read-only access for forensic reviewers

## Integration Points

- **DuckDB**: Ingestion pipeline writes to PostgreSQL via `PostgresWriter` after Pass 1 (embeddings)
- **LanceDB**: Vector embeddings replicated for pure similarity search (768-dim, cosine distance)
- **Neo4j**: Relations exported from PostgreSQL → temporal graph for conflict detection
- **Semantica**: Entity embeddings generated via `semantica_generate_embeddings()` (768-dim, all-MiniLM-L6-v2)
- **DIAL Core**: Evidence metadata and entity metadata feed into frontend dashboard

## Common Pitfalls

- **Embedding Dimension**: We use **768 dimensions** (Semantica's all-MiniLM-L6-v2), NOT 1536. Ensure consistency.
- **HNSW Index Performance**: On large datasets (>1M entities), HNSW rebuilds are expensive. Monitor reindex operations.
- **Timezone Handling**: Always use `TIMESTAMPTZ`; cast to UTC for cross-system consistency.
- **Circular Foreign Keys**: Evidence ↔ entities many-to-many should use junction table (not array type).
- **Source Hash Uniqueness**: Enforce UNIQUE constraint on source_hash to prevent duplicate ingestions.

## References
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [pgvector Extension](https://github.com/pgvector/pgvector)
- [HNSW Indexing](https://en.wikipedia.org/wiki/Hierarchical_navigable_small_world)
- [JSONB & GIN Indexes](https://www.postgresql.org/docs/current/datatype-json.html)
