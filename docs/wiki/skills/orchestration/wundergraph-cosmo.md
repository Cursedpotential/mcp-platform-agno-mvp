# WunderGraph Cosmo — Skill Reference

## Overview
- **What**: GraphQL federation router for deterministic, auditable cross-tier queries. Composes PostgreSQL, Neo4j, LanceDB subgraphs into unified schema. Critical for forensic analysis — all queries reproducible, versioned, and legally defensible.
- **Version**: Latest stable (Phase F roadmap)
- **Status**: Planned (Docker integration pending)
- **Category**: Orchestration/GraphQL
- **Port**: 4000 (router)
- **Installed In**: Node.js service (docker service `cosmo`)

## Purpose

WunderGraph Cosmo enables two complementary retrieval patterns:

1. **Production/Legal Queries** (WunderGraph): Pre-approved, federated schemas. All queries deterministic, auditable, versioned.
2. **Exploratory Queries** (DIAL Native): Ad-hoc MCP tool calls via Semantica. Fast iteration; useful patterns promoted to federated schemas.

### Promotion Workflow
```
Ad-hoc DIAL Query (Semantica MCP)
    ↓ (proves useful, forensically valuable)
    ↓
Create Federated Schema (WunderGraph)
    ↓
Canonicalize Query (make deterministic)
    ↓
Test & Version (evidence_federated_query wrapper)
    ↓
Production Query (auditable, legally defensible)
```

## Subgraph Architecture

Cosmo federates four subgraphs into supergraph:

### 1. PostgreSQL Subgraph
**Purpose**: Relational facts, entities, relations with confidence/provenance metadata.

```graphql
type Entity @key(fields: "id") {
  id: ID!
  name: String!
  entityType: String!
  embedding: [Float!]!
  confidence: Float!
  metadata: JSON!
  createdAt: DateTime!
}

type Relation @key(fields: "id") {
  id: ID!
  sourceId: ID!
  relationType: String!
  targetId: ID!
  confidence: Float!
  timestamp: DateTime!
  provenance: Provenance!
}

type Query {
  entity(id: ID!): Entity
  entitiesByType(type: String!): [Entity!]!
  relationsBySource(sourceId: ID!): [Relation!]!
}
```

### 2. Neo4j Subgraph
**Purpose**: Entity timelines, graph pattern queries, temporal relations.

```graphql
type EntityTimeline @key(fields: "entityId") {
  entityId: ID!
  entity: Entity!
  timeline: [TimelineEvent!]!
  connectedEntities: [Entity!]!
}

type TimelineEvent {
  timestamp: DateTime!
  relation: String!
  targetEntity: Entity!
  confidence: Float!
  sourceDocument: String!
}

type Query {
  entityTimeline(entityId: ID!): EntityTimeline
  pathBetweenEntities(from: ID!, to: ID!): [Path!]!
  entitiesActiveInWindow(start: DateTime!, end: DateTime!): [Entity!]!
}
```

### 3. LanceDB Subgraph (Vector Proxy)
**Purpose**: Semantic similarity across facts. Proxied via Node.js service (LanceDB has no native GraphQL).

```graphql
type SimilarFact {
  factId: ID!
  similarity: Float!
  fact: Fact!
}

type Query {
  similarFacts(factId: ID!, limit: Int = 10): [SimilarFact!]!
  semanticSearch(query: String!, limit: Int = 10): [SimilarFact!]!
}
```

### 4. DuckDB Subgraph (Analytics Proxy)
**Purpose**: Temporal aggregations, conflict statistics, analytics over raw facts.

```graphql
type ConflictStatistic {
  entityId: ID!
  conflictCount: Int!
  timeRange: String!
  severity: String!
}

type Query {
  conflictStats(entityId: ID!): ConflictStatistic!
  conflictTimelineByEntity(entityId: ID!): [ConflictStatistic!]!
}
```

## Federated Supergraph Composition

```yaml
# cosmo.yaml
graph:
  name: dial-forensics
  namespace: production

subgraphs:
  - name: postgres-sg
    routing_url: http://postgres-graphql:5433/graphql
    schema: ./schemas/postgres.graphql

  - name: neo4j-sg
    routing_url: http://neo4j:7687/graphql
    schema: ./schemas/neo4j.graphql

  - name: lancedb-sg
    routing_url: http://lancedb-proxy:3001/graphql
    schema: ./schemas/lancedb.graphql

  - name: duckdb-sg
    routing_url: http://duckdb-proxy:3002/graphql
    schema: ./schemas/duckdb.graphql

composition:
  enabled: true
  check_interval: 30s

router:
  port: 4000
  log_level: info
  execution_timeout: 30s
```

## MCP Tool: `evidence_federated_query` (Planned)

Wrapper tool that executes pre-approved federated queries and wraps results with auditability metadata.

```python
@server.tool()
def evidence_federated_query(
    query_name: str,  # e.g., "entity_timeline", "conflict_report"
    variables: dict,
    version: str = "latest"
) -> dict:
    """Execute a versioned, canonical federated query.

    Returns:
    {
        "result": {...},           # GraphQL result
        "executedAt": "...",      # ISO timestamp
        "queryVersion": "1.2.3",  # Schema version
        "subgraphLatencies": {...},
        "provenance": "..."       # Link to canonical query definition
    }
    """
```

## Why Forensics Matters

Forensic-grade queries must be:
- **Deterministic**: Same query → same result, always
- **Auditable**: Full execution trace with subgraph latencies
- **Reproducible**: Query version pinned in evidence record
- **Legally Defensible**: Pre-approved schema, signed query definitions

Cosmo ensures all three via federation + versioning.

## API Patterns

- **Query Composition**: Single GraphQL query across all subgraphs
- **Field Resolution**: `@requires`, `@provides` for cross-subgraph data dependencies
- **Deterministic Routing**: Consistent subgraph order ensures reproducible results
- **Batching**: Multiple related queries combined into single network call
- **Error Aggregation**: Partial failures from one subgraph don't fail entire query
- **Tracing**: X-Request-ID header propagated across subgraphs for audit

## Integration Points

- **DIAL Chat**: Exploratory queries via Semantica MCP tools
- **Evidence Review UI**: Federated queries via Cosmo GraphQL endpoint (port 4000)
- **CopilotKit**: Multi-step workflows combining ad-hoc + federated queries
- **PostgreSQL**: Relational subgraph queries
- **Neo4j**: Timeline and pattern queries
- **LanceDB**: Vector similarity proxy
- **DuckDB**: Analytics and conflict statistics
- **Docker**: Service orchestration (cosmo container TBD)

## Common Pitfalls

- **Entity References**: `@key` directive critical for federation; missing breaks composition
- **Schema Conflicts**: Duplicate type definitions across subgraphs cause validation errors
- **Timeout Tuning**: Subgraph latency multiplies in complex queries; set per-subgraph timeouts
- **Authentication**: Subgraph auth independent; federation doesn't inherit credentials
- **Versioning**: Breaking schema changes require version bump; clients must pin versions
- **Proxy Services**: LanceDB/DuckDB require custom GraphQL adapters; maintain consistency
- **Query Complexity**: Large federated queries across 4 subgraphs can be slow; use batching and caching

## References
- [WunderGraph Cosmo Documentation](https://wundergraph.com/cosmo)
- [GraphQL Federation Specification](https://www.apollographql.com/docs/federation/)
- [Apollo Subgraph Implementation Guide](https://www.apollographql.com/docs/federation/subgraph-spec/)
- [MCP_Tool_Platform/server/mcp/graphql](https://github.com/dial-stack/dial-stack) (legacy reference)
