# Goals — Curated Surreal Analysis, Walk Memory, and Investigation

> _Byline: Codex · GPT-5 · 2026-08-15_
>
> **Status:** Architecture documented; implementation not authorized by this file.
> **Build status:** NOT STARTED for the new Surreal/investigation capabilities.

## North-star outcome

Build a framework-neutral, evidence-grounded analytical environment that can reconstruct
what was knowable at any horizon, discover cross-source evidence and behavioral patterns,
materialize governed fact-centered subgraphs, and compare as-lived understanding with
hindsight without weakening PostgreSQL custody or canonical authority.

## Goal tree

### G1 — Preserve canonical authority and custody

- PostgreSQL owns sources, normalized records, claims, approvals, promotion, and audit.
- Original bytes remain in custody-controlled object storage.
- Every projection binds to source IDs, H1/SHA-256, locator, and version metadata.
- No extraction, memory, vector, or graph output silently becomes canonical.

### G2 — Build the governed Surreal analytical projection

- Define platform-owned ports independent of Spectron, Agno, and SurrealDB clients.
- Project approved manifests, spans, full normalized sources, chunks, vectors, facts,
  relationships, temporal state, traces, and TraceIQ geo observations.
- Enforce partial-source promotion and fail-closed projection reconciliation.
- Keep the legacy parked Surreal deployment untouched until an isolated target is approved.

### G3 — Recreate Spectron-compatible temporal memory

- Model valid, known/realized, recorded/system, decision, and walk-observed time.
- Implement episodic, identity, knowledge, context, instruction, uncertainty, and trace memory.
- Preserve supersession, contradiction, reconciliation, and current pointers without deletion.
- Run one isolated as-lived agent and compare it with Graphiti before replacement decisions.

### G4 — Improve chunking, routing, and embedding architecture

- Let Go parsers emit streaming structural atoms for every supported format, regardless of size.
- Form locator-preserving retrieval chunks by source type.
- Separate structural lane, semantic domains, modality, authority, sensitivity, temporal scope,
  and processing profile.
- Version parser, normalizer, chunker, classifier, embedding, and reranker independently.
- Isolate incompatible embedding spaces; fuse ranks and rerank rather than compare raw scores.
- Select models from observed gold-corpus performance, not a static vendor table.

### G5 — Build claim-centered evidence assembly

- Generate bounded cross-system investigations from candidate claims.
- Find supporting, contradicting, qualifying, contextual, duplicate, and missing evidence.
- Resolve exact spans through chunk generations to custody-backed originals.
- Establish immutable reviewed facts and materialize selected evidence subgraphs into SurrealDB.

### G6 — Build Investigation Search

- Provide Find Evidence, Reconstruct Event, and Discover Patterns modes.
- Search documents, conversations, messages, structured records, graphs, relationships,
  temporal data, and TraceIQ geo observations through authorized ports.
- Show why every result surfaced, source independence, alternatives, gaps, and uncertainty.
- Preserve investigation query plans, traces, and owner decisions.

### G7 — Build the scoped Behavioral Analysis Agent

- Analyze frozen curated groups spanning discontinuous dates, events, and conversations.
- Run closed-set analysis before separately logged outward discovery.
- Support hindsight, as-lived-so-far, and paired realization-delta modes.
- Use internal pattern lenses without confusing them with clinical diagnoses.
- Convert approved findings into conduct-first language during Case Prep export.

### G8 — Prove safety and usefulness before cutover

- Create gold corpora for legal, conversational, behavioral, code, table, OCR, temporal,
  geo, exact citation, paraphrase, mixed-domain, and contamination cases.
- Measure retrieval, routing, calibration, locator accuracy, latency, cost, storage, and
  horizon contamination per domain/question type.
- Require zero future-fact leakage in as-lived tests.
- Compare Graphiti and Surreal memory on reconstruction, reconciliation, provenance,
  isolation, invalidation, latency, and resource use.

## Phased delivery

| Phase | Outcome | Gate |
|---|---|---|
| 0 | Contracts, question inventory, gold corpus, threat model | Owner accepts contracts and planted-leak tests |
| 1 | Disposable Surreal spike with promoted manifests/spans | Exact PG/hash reconciliation and rollback/rebuild proof |
| 2 | Source/chunk/vector projection and hybrid retrieval | Profile isolation, prefilters, locator accuracy |
| 3 | Claim investigation and established-fact subgraph | Multi-source provenance and contradiction review |
| 4 | Investigation Search Workbench | Saved scopes, bounded traces, disconfirmation output |
| 5 | Behavioral agent on one curated scope | As-lived/hindsight isolation and paired delta |
| 6 | TraceIQ temporal-geo projection | PG/PostGIS authority and spatial/temporal parity |
| 7 | Graphiti/Surreal bake-off | Owner reviews measured parity/superiority |
| 8 | Optional controlled cutover | No critical unresolved safety or activation gate |

## Non-goals

- Reactivating SurrealDB as Agno's operational database.
- Moving canonical evidence, custody, or approval authority out of PostgreSQL.
- Bulk exposing unreviewed full sources after one span is approved.
- Treating LLM claims, behavioral lenses, or Graphiti beliefs as established facts.
- Comparing raw similarity scores across incompatible embedding spaces.
- Replacing Graphiti, Neo4j, or Weaviate before an observed bake-off.
- Implementing an unbounded autonomous investigator.

## Pending owner decisions

1. Whether the as-lived walk agent retrieves exclusively from SurrealDB.
2. Surreal namespace/database/context isolation per Matter, walk, and agent.
3. Exact physical claim/fact/source-span schema.
4. Weaviate named vectors versus profile-specific collections.
5. Memory embeddings versus promoted corpus embedding profiles.
6. Behavior-lens controlled taxonomy and expansion budgets.
7. Case Prep transformation and approval workflow.
