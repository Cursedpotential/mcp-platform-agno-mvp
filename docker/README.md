# docker/ — Progressive Disclosure Map

> Dockerfiles for each service container.

## Directory Map

```
docker/
  postgres/            <- Custom PG18 image: pg_duckdb + PostGIS + pgvector.
  tools/               <- Consolidated tool container (SBV + tools-facade).
  gateway/             <- LiteLLM proxy + OpenCode server.
  sandbox/             <- Isolated agent execution (no secrets, no published ports).
  graphiti/            <- Graphiti MCP config (Neo4j + LiteLLM LLM/embeddings).
  agent-ui/            <- Agent UI container (if present).
```

## Service Topology (compose.yaml)

| Service | Image | Profile | Ports |
|---|---|---|---|
| agentos-db | agno-postgres:18-duckdb | default | 5432 |
| agentos-api | agentos:latest | default | 8000 |
| platform-tools | agno-platform-tools:latest | tools | 8080, 8090 |
| sandbox | agno-sandbox:latest | tools | (internal only) |
| desktop | kasmweb/desktop:1.16.0 | desktop | 6901 |
| gateway | agno-gateway:latest | tools | 4000, 4096 |
| neo4j | neo4j:5-community | graph | 7474, 7687 |
| graphiti-mcp | zepai/knowledge-graph-mcp:latest | graph | 8071 |
