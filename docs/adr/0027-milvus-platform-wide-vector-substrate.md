# ADR-0027: Milvus = the platform-wide vector/ANN substrate (Knowledge engine included)
- Status: Accepted
- Date: 2026-06-13
- _Byline: Claude Code · Opus 4.8 · 2026-06-13_

## Context
We stood up self-hosted Milvus on ovh2 for the `claude-context` code index + the Case Bible
corpus (ADR-0026). That made us own a real, purpose-built vector DB. Meanwhile two *other*
vector stores were still in the plan: **pgvector** for the domain-partitioned Knowledge engine
(ADR-0010/0011) and **SurrealDB** as the consolidated store/session/Knowledge/memory layer
(ADR-0024, which absorbed the pgvector Knowledge role). Running three vector stores — and
making SurrealDB double as a vector store — is redundant and against minimize-custom.

## Decision
**Milvus is the single vector / ANN substrate for the entire platform.** Everything that needs
similarity/semantic search lands in Milvus (one collection per embedder/domain, per ADR-0010's
contract): the code index, the Case Bible, the **domain-partitioned Knowledge engine**, and
evidence-text embeddings. Wiring uses **Agno's native Milvus vector-store / Knowledge
integration** (off-the-shelf, no custom glue).

The other layers keep their strengths — clean separation:
- **Milvus** → all vector/ANN search (incl. **hybrid dense+sparse / BM25**, partitions, RBAC).
- **SurrealDB** → structured + **bitemporal records** (valid+transaction time), AgentOS
  sessions/state, memory. **No longer the vector/Knowledge layer.**
- **Graphiti/Neo4j** → bitemporal graph cognition (unchanged, VIP).

**Sequencing (beta-aware):** Milvus is `v3.0-beta` today. Use it now for the low-stakes,
re-embeddable code index + Case Bible. **Lock the direction** for the platform Knowledge engine,
but perform the actual migration off pgvector in **Phase B/D** — at which point accept the beta
or pin whatever Milvus is GA by then.

## Consequences
- **Supersedes-in-part ADR-0024**: SurrealDB retains store/session/memory + bitemporal records;
  its **vector/Knowledge role moves to Milvus**. ADR-0024 is otherwise intact.
- **Supersedes-in-part ADR-0010/0011** Knowledge-vector storage (pgvector → Milvus); the
  per-task "one collection per embedder" contract carries over to Milvus collections.
- One vector engine to operate + back up; one GUI (**Attu**) to inspect every vector in the stack.
- Gains hybrid semantic+keyword retrieval — materially better for legal/Knowledge search.
- Adds a service dependency for Knowledge queries (network hop) — acceptable in an already
  distributed stack; embeddings are always re-buildable.

## Alternatives considered
- **Keep pgvector / SurrealDB for Knowledge, Milvus only for code+Case Bible** — rejected: three
  vector stores, weaker ANN, more to operate, against minimize-custom.
- **SurrealDB as the one vector store** — rejected: its vector index is not competitive with a
  purpose-built ANN DB for scale or hybrid search.
- **Wait for Milvus GA before any platform use** — rejected for code/Case-Bible (low stakes);
  retained as the gate for the Knowledge-engine *migration* only.
