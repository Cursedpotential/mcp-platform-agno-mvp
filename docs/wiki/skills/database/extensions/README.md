# PostgreSQL Extensions for Forensic Evidence Platform

## Overview

PostgreSQL serves as the Tier 2 (normalized data) and Tier 4 (relational/relational view) layer in Dial-Stack. Multiple extensions enable advanced capabilities.

## Extension Directory

| Extension | Purpose | Wiki Page |
|-----------|---------|-----------|
| **pg_duckdb** | DuckDB queries in PostgreSQL | [PG_DUCKDB.md](./PG_DUCKDB.md) |
| **pg_vector** | Vector similarity search | [PG_VECTOR.md](./PG_VECTOR.md) |
| **PostGIS** | Geospatial capabilities | [PostGIS.md](./PostGIS.md) |
| **mysql_fdw** | MySQL Foreign Data Wrapper | [MYSQL_FDW.md](./MYSQL_FDW.md) |

## Installation Order

```sql
-- 1. Core extensions
CREATE EXTENSION IF NOT EXISTS uuid-ossp;       -- UUID generation
CREATE EXTENSION IF NOT EXISTS pgcrypto;        -- Cryptographic functions
CREATE EXTENSION IF NOT EXISTS pg_trgm;         -- Trigram similarity

-- 2. Geospatial
CREATE EXTENSION IF NOT EXISTS postgis;          -- Geospatial
CREATE EXTENSION IF NOT EXISTS postgis_topology; -- Topology

-- 3. Vector search
CREATE EXTENSION IF NOT EXISTS vector;           -- pg_vector

-- 4. DuckDB integration
CREATE EXTENSION IF NOT EXISTS pg_duckdb;        -- DuckDB in PG

-- 5. Foreign Data Wrappers
CREATE EXTENSION IF NOT EXISTS postgres_fdw;     -- Postgres FDW
CREATE EXTENSION IF NOT EXISTS mysql_fdw;        -- MySQL FDW
```

## Architecture Integration

```
┌─────────────────────────────────────────────────────────────┐
│                     PostgreSQL (Tier 2/4)                    │
│                                                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌───────────────┐│
│  │ pg_duckdb       │  │ pg_vector       │  │ PostGIS        ││
│  │ - Query DuckDB  │  │ - Semantic      │  │ - Location     ││
│  │ - Transform    │  │   search         │  │   queries      ││
│  │   results      │  │ - Deduplication  │  │ - Patterns     ││
│  └────────┬────────┘  └────────┬────────┘  └───────┬───────┘│
│           │                    │                   │         │
│           ▼                    ▼                   ▼         │
│  ┌─────────────────────────────────────────────────────────┐│
│  │              Unified Evidence Schema                     ││
│  │  - evidence (master index)                              ││
│  │  - evidence_locations (PostGIS)                         ││
│  │  - evidence_embeddings (pg_vector)                      ││
│  │  - evidence_metadata (pg_duckdb views)                  ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
                              │
                    pg_duckdb FDW
                              │
                              ▼
                     DuckDB (Tier 1)
```

## Cross-Extension Queries

### Join DuckDB and Vector Data
```sql
-- Find similar evidence across platforms
SELECT 
    d.file_hash,
    d.platform,
    v.model,
    1 - (e.embedding <=> v.query_vector) AS similarity
FROM duckdb_evidence d
JOIN evidence_embeddings e ON d.evidence_id = e.evidence_id
JOIN lancedb_vectors v ON e.evidence_id = v.id
WHERE d.platform = 'imessage'
ORDER BY similarity DESC
LIMIT 10;
```

### Geospatial + Vector Search
```sql
-- Find evidence near location with similar content
SELECT 
    ev.file_path,
    ST_Distance(el.location, ST_MakePoint(-83.05, 42.33)) AS distance,
    1 - (e.embedding <=> $query_vector) AS similarity
FROM evidence ev
JOIN evidence_locations el ON ev.uuidv7 = el.evidence_id
JOIN evidence_embeddings e ON ev.uuidv7 = e.evidence_id
WHERE ST_DWithin(el.location, ST_MakePoint(-83.05, 42.33), 5000)
ORDER BY similarity DESC, distance
LIMIT 20;
```

### MySQL FDW Join
```sql
-- Join MySQL evidence from legacy system
SELECT 
    pg.e.uuidv7,
    pg.e.file_path,
    my.legacy_evidence.case_number,
    my.legacy_evidence.upload_date
FROM evidence pg
JOIN mysql_evidence my ON pg.e.sha256_hash = my.e.file_hash;
```

## Performance Considerations

### Index Strategies
```sql
-- Vector index for similarity
CREATE INDEX ON evidence_embeddings 
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Spatial index for location
CREATE INDEX ON evidence_locations 
USING GIST (location);

-- Trigram index for text search
CREATE INDEX ON evidence (file_path, platform) 
USING GIN (platform gin_trgm_ops);
```

### Query Optimization
```sql
-- Set work_mem for large ops
SET work_mem = '256MB';

-- Use CTEs for complex federations
WITH nearby AS (
    SELECT evidence_id
    FROM evidence_locations
    WHERE ST_DWithin(location, $point, 5000)
),
similar AS (
    SELECT evidence_id
    FROM evidence_embeddings
    ORDER BY embedding <=> $vector
    LIMIT 100
)
SELECT * FROM evidence
WHERE uuidv7 IN (SELECT evidence_id FROM nearby)
AND uuidv7 IN (SELECT evidence_id FROM similar);
```

## Resources

- **PostgreSQL Docs**: https://www.postgresql.org/docs/current/
- **Extension Catalog**: https://www.postgresql.org/docs/current/contrib.html
- **pgvector**: https://github.com/pgvector/pgvector
- **PostGIS**: https://postgis.net/
- **pg_duckdb**: https://github.com/duckdb/pg_duckdb

## Related

- [DuckDB](../duckdb.md) - Tier 1 processing
- [LanceDB](../lancedb.md) - Tier 3 embeddings
- [Neo4j](../neo4j.md) - Tier 4 knowledge graph