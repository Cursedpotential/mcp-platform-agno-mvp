# PostGIS - Geospatial Capabilities for PostgreSQL

## Overview

PostGIS adds geospatial capabilities to PostgreSQL, enabling location-based queries for forensic evidence (geotagged photos, GPS data, location check-ins).

## Installation

```sql
-- Install extension
CREATE EXTENSION IF NOT EXISTS postgis;

-- Verify installation
SELECT PostGIS_Version();
```

## Core Types

| Type | Description |
|------|-------------|
| `geometry` | Planar coordinates (projected) |
| `geography` | Spherical coordinates (WGS84) |
| `raster` | Gridded data (satellite imagery) |

## Configuration

```sql
-- Create table with location column
CREATE TABLE evidence_locations (
    evidence_id UUID REFERENCES evidence(uuidv7),
    location GEOGRAPHY(POINT, 4326),  -- WGS84
    accuracy_meters FLOAT,
    source VARCHAR(64),  -- 'gps', 'exif', 'check-in'
    timestamp TIMESTAMP
);

-- Create spatial index
CREATE INDEX ON evidence_locations 
USING GIST (location);
```

## Query Patterns

### Distance Calculations
```sql
-- Find evidence within radius
SELECT 
    e.uuidv7,
    ev.file_path,
    ST_Distance(el.location, ST_MakePoint(-83.0507, 42.3314)) AS distance_meters
FROM evidence e
JOIN evidence_locations el ON e.uuidv7 = el.evidence_id
JOIN evidence_files ev ON e.uuidv7 = ev.evidence_id
WHERE ST_DWithin(
    el.location,
    ST_MakePoint(-83.0507, 42.3314),  -- Detroit
    5000  -- 5km radius
);
```

### Timeline Correlation
```sql
-- Find co-located events on timeline
SELECT 
    e1.evidence_id AS participant_a,
    e2.evidence_id AS participant_b,
    COUNT(*) AS colocations
FROM evidence_locations e1
JOIN evidence_locations e2 ON ST_DWithin(e1.location, e2.location, 50)
WHERE e1.evidence_id < e2.evidence_id
AND ABS(EXTRACT(EPOCH FROM (e1.timestamp - e2.timestamp))) < 3600
GROUP BY e1.evidence_id, e2.evidence_id
HAVING COUNT(*) > 3;
```

### Pattern Detection
```sql
-- Detect movement patterns
WITH movement AS (
    SELECT 
        evidence_id,
        timestamp,
        location,
        LAG(location) OVER (PARTITION BY evidence_id ORDER BY timestamp) AS prev_location
    FROM evidence_locations
)
SELECT 
    evidence_id,
    COUNT(*) AS movement_count,
    AVG(ST_Distance(location, prev_location)) AS avg_distance
FROM movement
WHERE location IS NOT NULL
GROUP BY evidence_id;
```

## Integration with Dial-Stack

### Use Cases
1. **Geotagged Photos** - Extract GPS from EXIF, store as PostGIS points
2. **Timeline Correlation** - Find co-located participants
3. **Pattern Detection** - Movement heatmaps, frequent locations
4. **Boundaries** - Check if locations fall within regions

### EXIF to PostGIS
```sql
-- Extract from EXIF metadata
INSERT INTO evidence_locations (evidence_id, location, source)
SELECT 
    uuidv7,
    ST_SetSRID(ST_MakePoint(exif_longitude, exif_latitude), 4326),
    'exif'
FROM duckdb_evidence
WHERE exif_latitude IS NOT NULL;
```

### Directus View
```sql
-- Create view for Directus
CREATE VIEW evidence_map AS
SELECT 
    e.uuidv7,
    ev.file_path,
    ST_AsGeoJSON(el.location)::json AS location_geojson,
    el.accuracy_meters,
    el.source
FROM evidence e
JOIN evidence_locations el ON e.uuidv7 = el.evidence_id
JOIN evidence_files ev ON e.uuidv7 = ev.evidence_id;
```

## Useful Functions

```sql
-- Distance between two points
ST_Distance(point1, point2)

-- Points within polygon
ST_Contains(polygon, point)

-- Buffer around point
ST_Buffer(point, radius_meters)

-- Convert to GeoJSON
ST_AsGeoJSON(geometry)

-- Parse GeoJSON
ST_GeomFromGeoJSON(json)
```

## Resources

- **Website**: https://postgis.net/
- **Docs**: https://postgis.net/documentation/
- **Tutorial**: https://postgis.net/workshops/postgis-intro/

## Related

- [PG_VECTOR](./PG_VECTOR.md) - Vector similarity
- [PG_DUCKDB](./PG_DUCKDB.md) - DuckDB integration
- [Dial-Stack Architecture](../../../../docs/ARCHITECTURE.md) - System architecture