# MySQL Foreign Data Wrapper (mysql_fdw)

## Overview

mysql_fdw allows PostgreSQL to read from MySQL databases, enabling federation with legacy evidence systems or external MySQL-based platforms.

## Installation

```bash
# Ubuntu/Debian
apt-get install postgresql-<version>-mysql-fdw

# From source
git clone https://github.com/EnterpriseDB/mysql_fdw.git
cd mysql_fdw
make USE_PGXS=1
make install USE_PGXS=1
```

```sql
-- Create extension in PostgreSQL
CREATE EXTENSION mysql_fdw;
```

## Configuration

### Create Foreign Server
```sql
-- Define MySQL server connection
CREATE SERVER mysql_evidence_server
FOREIGN DATA WRAPPER mysql_fdw
OPTIONS (
    host 'mysql-legacy.example.com',
    port '3306',
    database 'evidence_legacy'
);
```

### Create User Mapping
```sql
-- Map PostgreSQL user to MySQL credentials
CREATE USER MAPPING FOR postgres
SERVER mysql_evidence_server
OPTIONS (
    username 'evidence_reader',
    password 'secure_password'
);
```

### Create Foreign Tables
```sql
-- Import table schema from MySQL
IMPORT FOREIGN SCHEMA evidence_legacy
FROM SERVER mysql_evidence_server
INTO public;

-- Or create explicitly
CREATE FOREIGN TABLE mysql_evidence (
    id BIGINT,
    case_number VARCHAR(64),
    file_hash VARCHAR(64),
    platform VARCHAR(32),
    uploaded_at DATETIME,
    metadata TEXT
)
SERVER mysql_evidence_server
OPTIONS (
    dbname 'evidence_legacy',
    table_name 'evidence'
);
```

## Dial-Stack Integration

### Use Case: Legacy Evidence Migration

```sql
-- Query legacy MySQL from PostgreSQL
SELECT 
    pg.uuidv7,
    pg.file_path,
    my.case_number,
    my.uploaded_at
FROM evidence pg
JOIN mysql_evidence my ON pg.sha256_hash = my.file_hash
WHERE my.uploaded_at > '2020-01-01';
```

### Use Case: Dual-Write During Migration

```sql
-- Trigger to sync new evidence to legacy MySQL
CREATE OR REPLACE FUNCTION sync_to_mysql()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO mysql_evidence (
        case_number, file_hash, platform, uploaded_at
    ) VALUES (
        NEW.case_number, NEW.sha256_hash, NEW.platform, NOW()
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER evidence_sync
AFTER INSERT ON evidence
FOR EACH ROW
EXECUTE FUNCTION sync_to_mysql();
```

### Use Case: Cross-Database Deduplication

```sql
-- Find duplicates across PostgreSQL and MySQL
SELECT 
    COALESCE(pg.uuidv7, my.id) AS evidence_id,
    COALESCE(pg.file_path, 'legacy') AS file_path,
    pg.sha256_hash AS pg_hash,
    my.file_hash AS mysql_hash
FROM evidence pg
FULL OUTER JOIN mysql_evidence my ON pg.sha256_hash = my.file_hash
WHERE pg.sha256_hash IS NOT NULL OR my.file_hash IS NOT NULL;
```

## Query Optimization

### Push Down Predicates
```sql
-- WHERE clause pushed to MySQL
EXPLAIN (ANALYZE, VERBOSE)
SELECT * FROM mysql_evidence
WHERE platform = 'whatsapp';

-- Output shows:
-- Foreign Scan on mysql_evidence
--   Filter: (platform = 'whatsapp'::text)
--   MySQL query: SELECT * FROM evidence WHERE platform = 'whatsapp'
```

### Column Projection
```sql
-- Only fetch needed columns
SELECT file_hash, platform FROM mysql_evidence;
-- MySQL query: SELECT file_hash, platform FROM evidence
```

## Performance Considerations

### Bottlenecks
1. **Network Latency** - Every query crosses network
2. **Join Overhead** - Cross-database joins slower than local
3. **Type Conversion** - MySQL to PostgreSQL type mapping

### Mitigations
```sql
-- Materialize frequently accessed data
CREATE MATERIALIZED VIEW legacy_evidence_cache AS
SELECT * FROM mysql_evidence;

-- Refresh periodically
REFRESH MATERIALIZED VIEW legacy_evidence_cache;

-- Create indexes locally
CREATE INDEX ON legacy_evidence_cache(file_hash);
```

## Type Mapping

| MySQL Type | PostgreSQL Type |
|------------|-----------------|
| INT | INTEGER |
| BIGINT | BIGINT |
| VARCHAR | VARCHAR |
| TEXT | TEXT |
| DATETIME | TIMESTAMP |
| DATE | DATE |
| DECIMAL | NUMERIC |
| BLOB | BYTEA |
| JSON | JSONB |
| TINYINT(1) | BOOLEAN |

## Resources

- **GitHub**: https://github.com/EnterpriseDB/mysql_fdw
- **Docs**: https://github.com/EnterpriseDB/mysql_fdw/blob/master/README.md
- **PostgreSQL FDW**: https://www.postgresql.org/docs/current/postgres-fdw.html

## Related

- [PG_DUCKDB](./PG_DUCKDB.md) - DuckDB federation
- [PostgreSQL](../../database/postgresql.md) - Core database
- [WunderGraph Cosmo](../../orchestration/wundergraph-cosmo/INTEGRATION.md) - GraphQL federation