# Neo4j — Skill Reference

## Overview
- **What**: Property graph database with Cypher query language. Temporal knowledge graph for entity relationships, conflict detection, and provenance tracking via W3C PROV-O.
- **Version**: 5.13+ (Neo4j Community)
- **Category**: Database/Graph
- **Installed In**: Docker service `neo4j` (Bolt: 7687, HTTP: 7474, auth: neo4j/password)
- **Role**: Knowledge graph tier — entity-relationship network with temporal validity and provenance metadata

## Architecture

Neo4j stores two separate graphs accessed through Semantica's Py MCP Server:

1. **Semantic Graph**: Entity-relation facts extracted from text (NER + relation extraction)
   - Nodes: Entity (person, device, location, etc.)
   - Relations: COMMUNICATES_WITH, LOCATED_AT, OWNS, MENTIONS, etc.
   - Properties: confidence score, source document reference

2. **Temporal Graph**: Same entities+relations tagged with validity windows [start, end)
   - Supports historical queries: "What did entity A know at time T?"
   - Conflict detection: "Entity A was at Location 1 at time T, but also at Location 2"
   - Provenance: W3C PROV-O tracking (who extracted, when, from what source)

## Configuration

### Environment Variables
```
NEO4J_URI: bolt://neo4j:7687
NEO4J_USERNAME: neo4j
NEO4J_PASSWORD: ${NEO4J_PASSWORD:-password}
NEO4J_DATABASE: neo4j (default database)
```

### Docker Service
```yaml
neo4j:
  image: neo4j:5.13
  restart: always
  ports:
    - "7687:7687"   # Bolt protocol (TS/Py clients)
    - "7474:7474"   # Browser UI
  environment:
    NEO4J_AUTH: neo4j/${NEO4J_PASSWORD}
    NEO4J_apoc_export_file_enabled: "true"
    NEO4J_dbms_memory_heap_max__size: 2G
    NEO4J_server_default_database: neo4j
  volumes:
    - neo4j_data:/data
```

## Core Graph Schema

### Entity Nodes
```cypher
-- Base entity nodes (label-based typing)
CREATE (e:Entity {
  id: uuid(),
  name: "John Doe",
  entity_type: "person",     -- 'person', 'device', 'phone_number', 'email', 'location'
  confidence: 0.95,          -- From NER extraction
  source_hash: "sha256-...", -- Link to DuckDB evidence
  created_at: timestamp()
})

CREATE INDEX ON :Entity(entity_type)
CREATE INDEX ON :Entity(source_hash)
```

### Temporal Relations
```cypher
-- Relations with temporal validity windows
CREATE (e1:Entity)-[r:COMMUNICATES_WITH {
  relation_type: "sms",      -- Cypher stores in relation property
  timestamp: datetime(...),  -- When this relation was observed
  valid_from: datetime(...), -- Temporal validity [start, end)
  valid_to: datetime(...),
  confidence: 0.88,
  evidence_id: "uuid-...",   -- Link to PostgreSQL evidence table
  source_hash: "sha256-..."
}]->(e2:Entity)

CREATE INDEX ON :Entity|*-[r:COMMUNICATES_WITH]-|Entity(timestamp)
CREATE INDEX ON :Entity|*-[r:LOCATED_AT]-|Entity(valid_from)
```

### Conflict Node (Provenance)
```cypher
-- W3C PROV-O provenance tracking
CREATE (c:Conflict {
  id: uuid(),
  entity_id: "uuid-of-entity",
  conflict_type: "location_contradiction",  -- temporal, value, source, etc.
  old_value: "Location A",
  new_value: "Location B",
  timestamp_old: datetime(...),
  timestamp_new: datetime(...),
  detected_at: timestamp(),
  detector: "conflict_detector_v1",         -- Algorithm/version that found it
  severity: "high",                         -- high, medium, low
  prov_entity: "uuid-source-hash",          -- Links to PROV-O entity
  prov_activity: "extraction-pass-1"        -- Links to PROV-O activity
})

CREATE CONSTRAINT conflict_id_unique ON (c:Conflict) ASSERT c.id IS UNIQUE
```

## API Patterns (Py MCP Server)

### Lazy Singleton Pattern
```python
# From py-mcp-server/src/server.py
_neo4j_driver = None

def _get_neo4j():
    global _neo4j_driver
    if _neo4j_driver is None:
        from neo4j import GraphDatabase
        _neo4j_driver = GraphDatabase.driver(
            NEO4J_URI,
            auth=(NEO4J_USER, NEO4J_PASS)
        )
        logger.info(f"[Neo4j] Connected to {NEO4J_URI}")
    return _neo4j_driver
```

### Cypher Query Tool
```python
@mcp.tool()
def neo4j_cypher_query(cypher: str, parameters: Optional[dict] = None) -> str:
    """Execute arbitrary Cypher query against Neo4j."""
    driver = _get_neo4j()
    with driver.session(database=NEO4J_DB) as session:
        result = session.run(cypher, parameters or {})
        return json.dumps([record.data() for record in result], default=str)
```

### Entity Timeline Tool
```python
@mcp.tool()
def neo4j_get_entity_timeline(entity_id: str, from_date: str, to_date: str) -> str:
    """
    Get temporal evolution of entity relationships within a time window.

    Args:
        entity_id: UUID of entity to track
        from_date: ISO 8601 start date
        to_date: ISO 8601 end date

    Returns:
        JSON array of relations ordered by timestamp
    """
    cypher = """
    MATCH (e:Entity {id: $entity_id})-[r]->(target)
    WHERE r.timestamp >= $from_date AND r.timestamp <= $to_date
    RETURN e.name, r.relation_type, target.name, r.timestamp, r.confidence
    ORDER BY r.timestamp ASC
    """
    driver = _get_neo4j()
    with driver.session(database=NEO4J_DB) as session:
        result = session.run(cypher, {
            'entity_id': entity_id,
            'from_date': from_date,
            'to_date': to_date
        })
        return json.dumps([record.data() for record in result], default=str)
```

## Temporal Patterns

### Conflict Detection (Temporal Contradiction)
```cypher
-- Find entities that were at two locations simultaneously
MATCH (person:Entity {entity_type: 'person'})-[r1:LOCATED_AT]->(loc1),
      (person)-[r2:LOCATED_AT]->(loc2)
WHERE loc1.id <> loc2.id
  AND r1.timestamp = r2.timestamp  -- Same time, different places
RETURN person.name, loc1.name, loc2.name, r1.timestamp
```

### Knowledge Accumulation Over Time
```cypher
-- What entities did person A know about, ordered by first contact
MATCH (a:Entity {name: 'Alice'})-[r]->(other)
WHERE r.valid_from IS NOT NULL
RETURN other.name, r.relation_type, r.valid_from, r.confidence
ORDER BY r.valid_from ASC
```

## Provenance Tracking (W3C PROV-O)

### Track Evidence → Entity Extraction
```cypher
-- Link forensic evidence (source_hash) → extracted entities → relations
MATCH (e:Entity {source_hash: 'sha256-abc123...'})
RETURN e.id, e.name, e.entity_type, e.created_at
```

### Chain of Custody Audit Trail
```cypher
-- Who extracted what from which source, when?
MATCH (c:Conflict)
WHERE c.prov_entity = 'source-hash' AND c.prov_activity = 'extraction-pass-1'
RETURN c.entity_id, c.conflict_type, c.detected_at, c.detector, c.severity
```

## Integration Points

- **DuckDB**: Temporal facts + entities exported to Cypher CREATE statements
- **Semantica (Py MCP)**: `semantica_build_graph()` writes relations; `semantica_detect_conflicts()` creates Conflict nodes
- **PostgreSQL**: Entity canonical IDs synced bidirectionally; relations also stored in PostgreSQL for consistency
- **LanceDB**: Entity embeddings (768-dim) also stored for semantic similarity fallback
- **DIAL Frontend**: Graph visualization queries via neo4j_cypher_query tool

## Common Pitfalls

- **Duplicate Nodes**: Without UNIQUE constraints, same entity can be created multiple times. Always use:
  ```cypher
  CREATE CONSTRAINT entity_id_unique ON (e:Entity) ASSERT e.id IS UNIQUE
  ```
- **Temporal Window Edges**: Use inclusive start, exclusive end `[valid_from, valid_to)` for consistency.
- **Memory Overflow**: Large path queries (`-[*]->`) can load entire graph. Always bound with LIMIT.
- **Cypher 5.13 Syntax**: Use `MATCH...WHERE` with temporal operators; avoid legacy `.timestamp` property syntax.
- **Transaction Isolation**: Read-committed isolation; long-running transactions may miss recent writes.

## References
- [Neo4j Documentation](https://neo4j.com/docs/)
- [Cypher Manual](https://neo4j.com/docs/cypher-manual/)
- [W3C PROV-O Standard](https://www.w3.org/TR/prov-o/)
- [APOC Temporal Functions](https://neo4j.com/docs/apoc/current/)
