# pg_duckdb - DuckDB in PostgreSQL

## Overview

pg_duckdb is a PostgreSQL extension that enables DuckDB queries within PostgreSQL, allowing analytical queries on DuckDB tables through PostgreSQL.

## Installation

```sql
-- Install extension
CREATE EXTENSION pg_duckdb;

-- Enable DuckDB queries
SET duckdb.force_execution = true;
```

## Configuration

```sql
-- Configuration options
SET duckdb.max_memory = '4GB';
SET duckdb.thread_count = 8;

-- Allow DuckDB tables
SET duckdb.enable_external_access = true;
```

## Usage with Foreign Data Wrapper

```sql
-- Create foreign server for DuckDB
CREATE SERVER duckdb_server FOREIGN DATA WRAPPER duckdb_fdw
OPTIONS (database '/path/to/evidence.duckdb');

-- Create foreign table mapping
CREATE FOREIGN TABLE evidence_hashes (
    hash_id UUID,
    file_hash VARCHAR(64),
    algorithm VARCHAR(16),
    created_at TIMESTAMP
) SERVER duckdb_server OPTIONS (table 'hashes');
```

## Query Examples

```sql
-- Query DuckDB from PostgreSQL
SET duckdb.force_execution = true;

SELECT 
    file_hash,
    algorithm,
    COUNT(*) as hash_count
FROM duckdb_table
GROUP BY file_hash, algorithm;
```

## Integration with Dial-Stack

### Processing Pipeline
```
DuckDB (T1) → pg_duckdb → PostgreSQL (T2)
```

### Use Cases
1. **Analytical Queries** - Run DuckDB analytics from Directus
2. **Cross-Database Joins** - Join DuckDB and PostgreSQL tables
3. **Hash Verification** - Query evidence hashes through PostgreSQL API
4. **Metadata Views** - Create PostgreSQL views over DuckDB tables

### Directus Integration
```sql
-- Create view for Directus
CREATE VIEW evidence_metadata AS
SELECT 
    e.uuidv7,
    e.file_path,
    d.hash_sha256,
    d.first_seen,
    d.transformations
FROM evidence e
JOIN duckdb_metadata d ON e.uuidv7 = d.evidence_id;
```

## Performance Considerations

### Bottlenecks
- **Data Transfer** - Large result sets between DuckDB and PostgreSQL
- **Planning Overhead** - Query planning in both engines

### Mitigations
```sql
-- Limit transferred data
SET duckdb.force_execution = false;  -- For small queries
SET duckdb.materialize = true;        -- Cache results

-- Use views with filters
CREATE VIEW recent_evidence AS
SELECT * FROM duckdb_evidence 
WHERE created_at > NOW() - INTERVAL '7 days';
```

## Resources

- **GitHub**: https://github.com/duckdb/pg_duckdb
- **Docs**: https://duckdb.org/docs/extensions/pg_duckdb
- **Examples**: https://github.com/duckdb/duckdb_pg_demo

## Related

- [PostGIS](./PostGIS.md) - Geospatial queries
- [pg_vector](./PG_VECTOR.md) - Vector similarity
- [mysql_fdw](./MYSQL_FDW.md) - MySQL federation