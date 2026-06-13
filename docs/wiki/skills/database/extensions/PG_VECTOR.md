# pg_vector - Vector Similarity Search in PostgreSQL

## Overview

pg_vector is a PostgreSQL extension for vector similarity search, enabling semantic search, recommendations, and embeddings storage.

## Installation

```sql
-- Install extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Verify installation
SELECT * FROM pg_extension WHERE extname = 'vector';
```

## Configuration

```sql
-- Create table with vector column
CREATE TABLE embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    evidence_id UUID REFERENCES evidence(uuidv7),
    embedding vector(1536),  -- OpenAI embeddings
    model VARCHAR(128),
    created_at TIMESTAMP DEFAULT NOW()
);
```

## Index Types

### HNSW (Hierarchical Navigable Small World)
```sql
-- Best for high recall, fast queries
CREATE INDEX ON embeddings 
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
```

### IVFFlat (Inverted File Flat)
```sql
-- Best for fast builds, moderate recall
CREATE INDEX ON embeddings 
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
```

## Query Patterns

### Semantic Search
```sql
-- Find similar embeddings
SELECT 
    e.evidence_id,
    ev.file_path,
    1 - (embedding <=> query_vector) AS similarity
FROM embeddings e
JOIN evidence ev ON e.evidence_id = ev.uuidv7
ORDER BY embedding <=> query_vector
LIMIT 10;
```

### Batch Similarity
```sql
-- Find similar evidence in bulk
SELECT 
    e1.evidence_id AS source,
    e2.evidence_id AS target,
    1 - (e1.embedding <=> e2.embedding) AS similarity
FROM embeddings e1, embeddings e2
WHERE e1.evidence_id != e2.evidence_id
AND e1.embedding <=> e2.embedding < 0.3
LIMIT 100;
```

## Integration with Dial-Stack

### Embedding Pipeline
```
DuckDB (metadata) → PostgreSQL (normalized) → LanceDB (vectors)
                                          ↓
                                    pg_vector (API layer)
```

### Use Cases
1. **Semantic Search** - Find similar evidence by content
2. **Deduplication** - Detect near-duplicates via embedding similarity
3. **Recommendation** - Suggest related evidence
4. **Clustering** - Group evidence by semantic similarity

### Synchronization with LanceDB
```sql
-- Create view combining LanceDB vectors with PostgreSQL metadata
CREATE VIEW evidence_with_vectors AS
SELECT 
    e.uuidv7,
    e.file_path,
    e.platform,
    v.embedding,
    v.model
FROM evidence e
JOIN lancedb_vectors v ON e.uuidv7 = v.evidence_id;
```

## Performance Tuning

### Index Selection
| Use Case | Recommended Index | Configuration |
|----------|------------------|---------------|
| High recall | HNSW | `m=16, ef_construction=64` |
| Fast build | IVFFlat | `lists = sqrt(rows)` |
| Memory limited | IVFFlat | `lists = rows / 1000` |

### Query Optimization
```sql
-- Set search parameters
SET hnsw.ef_search = 100;  -- Trade recall for speed
SET ivfflat.probes = 10;   -- Number of clusters to search

-- Use partial indexes
CREATE INDEX ON embeddings 
USING hnsw (embedding vector_cosine_ops)
WHERE model = 'text-embedding-3-small';
```

## Resources

- **GitHub**: https://github.com/pgvector/pgvector
- **Docs**: https://github.com/pgvector/pgvector#readme
- **Examples**: https://github.com/pgvector/pgvector/tree/master/examples

## Related

- [PG_DUCKDB](./PG_DUCKDB.md) - DuckDB integration
- [DuckDB](../duckdb.md) - Data processing
- [LanceDB](../lancedb.md) - Vector storage