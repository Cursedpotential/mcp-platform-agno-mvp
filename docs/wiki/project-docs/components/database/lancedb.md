---
title: LanceDB
type: reference
status: active
created: 2026-03-30
updated: 2026-03-30
reviewed: 2026-03-30
tags:
  - dial-stack
  - wiki
  - database
  - lancedb
  - vectors
summary: Reference note for LanceDB as the vector retrieval and embedding store used in parallel with Semantica after canonical PostgreSQL writes.
repo_usage_state: partial
repo_version: unpinned python dependency `lancedb` in py-mcp-server requirements; runtime path /data/lancedb
upstream_version: Python LanceDB v0.30.2-beta.1 latest GitHub release reviewed 2026-03-30
official_docs:
  - https://docs.lancedb.com/quickstart
official_repo:
  - https://github.com/lancedb/lancedb
official_downloads:
  - https://github.com/lancedb/lancedb/releases
  - https://pypi.org/project/lancedb/
---

# LanceDB

## At a Glance

- **What it is**: Vector database and retrieval layer.
- **Current role in `dial-stack`**: Parallel embedding and retrieval store after canonical PostgreSQL writes.
- **Why it matters**: It gives us high-speed semantic search without turning PostgreSQL into the only retrieval surface.

## How `dial-stack` Uses It

Current local anchors:

- [server.py](C:/Users/matts/Projects/TheBigOne/dial-stack/mcp-servers/py-mcp-server/src/server.py)
- [requirements.txt](C:/Users/matts/Projects/TheBigOne/dial-stack/mcp-servers/py-mcp-server/requirements.txt)
- [docker-compose.yml](C:/Users/matts/Projects/TheBigOne/dial-stack/docker-compose.yml)

Current responsibilities:

- store embeddings for evidence and entity retrieval
- support semantic similarity lookups
- run as a parallel retrieval lane alongside Semantica-derived processing

## Position in the Pipeline

The working order is:

`DuckDB -> PostgreSQL -> Semantica + LanceDB in parallel -> PostgreSQL enrichment`

That means LanceDB is **not** the canonical evidence store. It is a derived semantic-access layer.

## Repo Version vs Upstream Version

| Posture | Value | Notes |
|---|---|---|
| Repo dependency | unpinned `lancedb` | Drift risk in `py-mcp-server` |
| Repo runtime path | `/data/lancedb` | Volume-backed path in compose |
| Upstream latest reviewed | `Python LanceDB v0.30.2-beta.1` | GitHub releases reviewed 2026-03-30 |

The version posture is weaker here than it should be. This is a good candidate for explicit pinning once the MVP flow stabilizes.

## How We Could Expand Its Use

- hybrid retrieval across evidence, summaries, and entity-level embeddings
- richer attachment or multimodal retrieval if we index non-text evidence
- reranking and analyst-facing retrieval experiences
- dedicated vector collections keyed by evidence type or workflow stage

## What We Need to Watch

- unpinned dependency drift
- accidental duplication of canonical truth between PostgreSQL and LanceDB
- embeddings created before evidence linkage is stable
- retrieval outputs that are not traceable back to evidence IDs and hashes

## Key Repo Files

- [server.py](C:/Users/matts/Projects/TheBigOne/dial-stack/mcp-servers/py-mcp-server/src/server.py)
- [requirements.txt](C:/Users/matts/Projects/TheBigOne/dial-stack/mcp-servers/py-mcp-server/requirements.txt)
- [docker-compose.yml](C:/Users/matts/Projects/TheBigOne/dial-stack/docker-compose.yml)

## Official Sources

- [LanceDB Quickstart](https://docs.lancedb.com/quickstart)
- [LanceDB GitHub](https://github.com/lancedb/lancedb)
- [LanceDB Releases](https://github.com/lancedb/lancedb/releases)
- [LanceDB PyPI](https://pypi.org/project/lancedb/)

## Related Notes

- [[skills/database/postgresql|PostgreSQL]]
- [[skills/database/neo4j|Neo4j]]
- [[skills/nlp/semantica|Semantica]]
- [[architecture/ARCHITECTURE|dial-stack Architecture]]
- [[INDEX|dial-stack Wiki Index]]
