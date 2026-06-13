# WunderGraph Cosmo - Federated GraphQL

## Overview

WunderGraph Cosmo is a GraphQL federation platform that unifies multiple data sources into a single graph API.

## Architecture

```
                    ┌─────────────────────┐
                    │   Cosmo Router      │
                    │   (Supergraph)      │
                    │   Port: 3002       │
                    └─────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              │               │               │
              ▼               ▼               ▼
    ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
    │ Evidence    │  │ Knowledge   │  │ Rules       │
    │ Ingestion    │  │ Graph       │  │ Engine      │
    │ subgraph     │  │ subgraph    │  │ subgraph    │
    │ Port: 4011   │  │ Port: 4012   │  │ Port: 4013  │
    │              │  │              │  │             │
    │ PostgreSQL   │  │ Neo4j        │  │ MySQL       │
    │ + DuckDB     │  │ + Semantica  │  │ (fdw)       │
    └─────────────┘  └─────────────┘  └─────────────┘
```

## Installation

```bash
# Install CLI
npm install -g @wundergraph/wcli

# Initialize project
wcli init cosmo-config
cd cosmo-config
```

## Configuration

### graph.yaml
```yaml
federated_graph: traceiq-forensic
namespace: production

subgraphs:
  - name: evidence-ingestion
    url: http://localhost:4011/graphql
    schema: ./subgraphs/evidence-ingestion/schema.graphql
    
  - name: knowledge-graph
    url: http://localhost:4012/graphql
    schema: ./subgraphs/knowledge-graph/schema.graphql
    
  - name: rules-engine
    url: http://localhost:4013/graphql
    schema: ./subgraphs/rules-engine/schema.graphql

mcp_gateway:
  enabled: true
  expose_tools:
    - ingest_evidence
    - verify_custody_chain
    - query_timeline
    - detect_platform_hops
    - resolve_entities
    - flag_behavioral_patterns
    - get_severity_classification
```

### Local Router Compose
```bash
# Generate router config
wcli router compose -i graph.yaml -o router.json

# Start router
wcli router start -c router.json
```

## Subgraph Development

### TypeScript gRPC Server
```typescript
// subgraphs/evidence-ingestion/src/index.ts
import { createSubgraphServer } from '@wundergraph/subgraph';

const server = createSubgraphServer({
  typeDefs: `
    type Evidence {
      id: ID!
      uuidv7: String!
      fileHash: String!
      platform: String!
      createdAt: String!
    }
    
    type Query {
      evidence(id: ID!): Evidence
      searchEvidence(query: String!): [Evidence!]!
    }
  `,
  resolvers: {
    Query: {
      evidence: async (_, { id }, { dataSources }) => {
        return dataSources.postgres.getEvidence(id);
      },
    },
  },
  dataSources: {
    postgres: new PostgresDataSource(process.env.DATABASE_URL),
    duckdb: new DuckDBDataSource(process.env.DUCKDB_PATH),
  },
});

server.listen(4011);
```

## Federation Directives

### @shareable
```graphql
# Shared across subgraphs
type Evidence @shareable {
  id: ID!
  uuidv7: String!
}
```

### @key (Entity Resolution)
```graphql
# Entity with primary key
type Entity @key(fields: "id") {
  id: ID!
  name: String!
  type: String!
  platform: String!
}
```

### @external and @requires
```graphql
# Cross-subgraph references
type Entity {
  id: ID!
  name: String!
  platform: String!
  
  # From knowledge-graph subgraph
  relations: [Relation!]! @external
  timeline: [Event!]! @requires(fields: "id")
}
```

### @authenticated
```graphql
# Authentication required
type Query {
  ingestEvidence(file: Upload!): Evidence! @authenticated
}
```

### @requiresScopes
```graphql
# Role-based access
type Mutation {
  deleteEvidence(id: ID!): Boolean! @requiresScopes(scopes: ["admin"])
}
```

## Docker Compose Setup

```yaml
# docker-compose.yml
services:
  cosmo-router:
    image: wundergraph/cosmo-router:latest
    ports:
      - "3002:3002"
    volumes:
      - ./router.json:/app/router.json
    environment:
      - COSMO_API_URL=http://control-plane:3001
    depends_on:
      - evidence-ingestion
      - knowledge-graph
      - rules-engine

  evidence-ingestion:
    build: ./subgraphs/evidence-ingestion
    ports:
      - "4011:4011"
    environment:
      - DATABASE_URL=postgres://user:pass@postgres:5432/evidence

  knowledge-graph:
    build: ./subgraphs/knowledge-graph
    ports:
      - "4012:4012"
    environment:
      - NEO4J_URI=bolt://neo4j:7687
      - SEMANTICA_API=http://semantica:4004

  rules-engine:
    build: ./subgraphs/rules-engine
    ports:
      - "4013:4013"
    environment:
      - MYSQL_URI=mysql://user:pass@mysql:3306/rules
```

## Federation Query Example

```graphql
# Query across all subgraphs
query GetEvidenceWithRelations($id: ID!) {
  evidence(id: $id) {
    id
    uuidv7
    fileHash
    platform
    
    # From knowledge-graph subgraph
    entities {
      id
      name
      type
      relations {
        target {
          name
        }
        relationType
      }
    }
    
    # From rules-engine subgraph
    severity {
      level
      score
      reasons
    }
  }
}
```

## MCP Gateway Integration

### Expose GraphQL as MCP Tools
```yaml
# mcp-gateway-config.yaml
mcp_gateway:
  enabled: true
  server_name: traceiq-mcp
  tools:
    - graphql_operation: evidence(id: $id)
      mcp_tool_name: get_evidence
      description: Get evidence by ID
    
    - graphql_operation: searchEvidence(query: $query)
      mcp_tool_name: search_evidence
      description: Search evidence by query
    
    - graphql_operation: ingestEvidence(file: $file)
      mcp_tool_name: ingest_evidence
      description: Ingest new evidence file
```

## Resources

- **Official Docs**: https://wundergraph.com/docs/cosmo
- **GitHub**: https://github.com/wundergraph/cosmo
- **CLI Reference**: https://wundergraph.com/docs/cosmo/cli
- **Federation Guide**: https://wundergraph.com/docs/cosmo/federation

## Related

- [Directus](../directus/INTEGRATION.md) - File upload interface
- [Semantica](../../nlp/semantica.md) - Knowledge graph construction
- [PostgreSQL](../postgresql.md) - Data layer