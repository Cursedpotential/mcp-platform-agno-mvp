---
title: Neo4j
type: reference
status: active
created: 2026-03-30
updated: 2026-03-30
reviewed: 2026-03-30
tags:
  - dial-stack
  - wiki
  - database
  - neo4j
  - graph
summary: Reference note for Neo4j as the graph and provenance layer for derived entity, relationship, and timeline structures in dial-stack.
repo_usage_state: partial
repo_version: no active root compose service; py-mcp-server expects NEO4J_URI and Neo4j 5.x style usage
upstream_version: Neo4j Operations Manual current 2026.01 and 5.26 LTS reviewed 2026-03-30
official_docs:
  - https://neo4j.com/docs/operations-manual/current/
official_repo:
  - https://github.com/neo4j/neo4j
official_downloads:
  - https://neo4j.com/docs/operations-manual/current/docker/
---

# Neo4j

## At a Glance

- **What it is**: Graph database and Cypher execution engine.
- **Current role in `dial-stack`**: Derived graph layer for entities, relations, provenance, and timeline-style queries.
- **Current repo state**: Expected by the Python analysis layer, but not currently composed in the root docker stack.

## How `dial-stack` Uses It

Neo4j is not where evidence first lands. It is where **derived graph structure** should go after canonical relational storage.

Current local anchors:

- [server.py](C:/Users/matts/Projects/TheBigOne/dial-stack/mcp-servers/py-mcp-server/src/server.py)
- [workflow_tools.py](C:/Users/matts/Projects/TheBigOne/dial-stack/mcp-servers/py-mcp-server/src/tools/workflow_tools.py)
- [docker-compose.yml](C:/Users/matts/Projects/TheBigOne/dial-stack/docker-compose.yml) for environment expectations only

Current intended responsibilities:

- entity graph structures
- relation graph structures
- provenance-oriented graph patterns
- later contradiction and timeline views

## Position in the Pipeline

Neo4j is downstream of the canonical evidence path.

Current intended order:

`DuckDB -> PostgreSQL -> Semantica + LanceDB -> Neo4j / PostgreSQL enrichment`

That means Neo4j should hold **derived graph structure**, not replace canonical evidence storage.

## Repo Version vs Upstream Version

| Posture | Value | Notes |
|---|---|---|
| Repo runtime | external / not composed in root stack | Python service expects `NEO4J_URI` |
| Repo usage style | Neo4j 5.x-era patterns | Tooling and examples assume modern driver usage |
| Upstream docs reviewed | `2026.01 current`, `5.26 LTS` | From Neo4j Operations Manual |

## How We Could Expand Its Use

- provenance subgraphs linked back to PostgreSQL and DuckDB anchors
- graph-backed analyst views for timelines and relationship clusters
- contradiction and narrative-shift detection after the MVP pipeline is stable
- explicit W3C PROV-style mappings where helpful for derived outputs

## What We Need to Watch

- no active compose service means graph features can look “implemented” in docs while still being infrastructure-partial
- graph writes must remain attributable to canonical evidence IDs
- contradiction detection should stay downstream, not creep into first-pass ingest
- graph structure should not become the only source of truth for evidence facts

## Key Repo Files

- [server.py](C:/Users/matts/Projects/TheBigOne/dial-stack/mcp-servers/py-mcp-server/src/server.py)
- [workflow_tools.py](C:/Users/matts/Projects/TheBigOne/dial-stack/mcp-servers/py-mcp-server/src/tools/workflow_tools.py)
- [ARCHITECTURE.md](C:/Users/matts/Projects/TheBigOne/dial-stack/docs/wiki/architecture/ARCHITECTURE.md)

## Official Sources

- [Neo4j Operations Manual](https://neo4j.com/docs/operations-manual/current/)
- [Neo4j Docker Docs](https://neo4j.com/docs/operations-manual/current/docker/)
- [Neo4j GitHub](https://github.com/neo4j/neo4j)

## Related Notes

- [[skills/database/postgresql|PostgreSQL]]
- [[skills/database/lancedb|LanceDB]]
- [[skills/nlp/semantica|Semantica]]
- [[architecture/ARCHITECTURE|dial-stack Architecture]]
- [[INDEX|dial-stack Wiki Index]]
