# Semantica platform review and architecture handoff — 2026-08-02

> _Byline: Codex · GPT-5 · 2026-08-02_

> Companion audit: [`HANDOFF-2026-08-02-sbv-chatminer-parser-gap-review.md`](HANDOFF-2026-08-02-sbv-chatminer-parser-gap-review.md)
> covers SBV, ChatMiner, SMS Backup & Restore, custody/reconciliation, and the
> parser/repair implementation in detail.

## Purpose and decision summary

This document records the source-level review of HawkSight AI's Semantica,
the current Agno-MCP-Platform implementation, the database and AgentOS issues
discussed on 2026-08-02, and the recommended target topology.

The central recommendation is:

> **Adopt Semantica as a first-class, governed evidence-intelligence worker—not
> as a new source of truth, not as an agent memory replacement, and not through
> its upstream Agno adapters without a platform-owned compatibility layer.**

Semantica should consume custody-approved `NormalizedRecord` inputs, produce
source-linked candidate entities, relations, events, conflicts, resolutions,
temporal facts, and ontology-validation results, and project approved derived
facts into the Neo4j `evidence` database. PostgreSQL remains the canonical
control and provenance plane. Weaviate remains a rebuildable retrieval
projection. Graphiti remains the ignorant agent's accumulating belief state in
the separate Neo4j `memory` database.

SurrealDB should leave the critical runtime path because its upstream deployment
problems are outside this project's control. Its existing data should be
preserved and exported/read-only until parity is proven; nothing should be
deleted.

This is a recommendation and implementation handoff, not a claim that the
topology is already operational. The current Semantica integration is a design
configuration only.

## Executive findings

1. **Semantica is a strong architectural fit.** Its useful capabilities include
   NER, relation/triplet/event extraction, coreference, semantic roles,
   deduplication, entity resolution, conflict detection, bitemporal facts,
   temporal queries and reasoning, W3C PROV-O lineage, ontology generation and
   validation, SHACL/OWL/SKOS, explainable reasoning, graph algorithms,
   persistent graph/vector/triplet backends, pipeline orchestration, export,
   decision tracking, and GraphRAG/context retrieval.

2. **The platform is not actually running Semantica.** The repository contains
   a vendored `0.3.0-alpha` tree and `server/analysis/semantica_wiring.py`, but
   the `semantica` package is not installed and the wiring module only returns
   dictionaries. Its unit tests prove those dictionaries, not ingestion,
   extraction, persistence, horizon enforcement, or Neo4j writes.

3. **The vendored copy is materially behind upstream.** The official repository
   now declares `0.6.0`. A package-source-only diff found 157 changed files,
   36,486 insertions, and 2,566 deletions between the vendored package and the
   reviewed upstream package.

4. **Upstream's advertised Agno integration is incompatible with the platform's
   runtime.** It imports four legacy APIs absent from local Agno 2.8.6:
   `agno.memory.db.base.MemoryDb`, `agno.memory.db.row.MemoryRow`,
   `agno.knowledge.base.AgentKnowledge`, and `agno.document.base.Document`.
   `agno.tools.toolkit.Toolkit` still exists. Upstream tests conceal this by
   installing stub Agno modules in `sys.modules`; they do not validate the
   adapters against real Agno 2.8.x.

5. **Semantica's temporal model is necessary but insufficient for the project's
   knowledge-horizon mechanism.** It implements valid and transaction time via
   `valid_from`, `valid_until`, `recorded_at`, and `superseded_at`. Its source has
   zero occurrences of `occurred_at`, `knowledge_time`, or `disclosure_tier`.
   The platform must map the clocks explicitly and add disclosure policy at the
   retrieval boundary.

6. **Default extraction behavior is too permissive for forensic use.** When
   relation models and patterns return nothing, the upstream relation extractor
   can connect adjacent entities with `related_to` at confidence `0.3`. Empty
   output is preferable to invented forensic edges. All extraction products
   must remain candidates until validation and, where material, human approval.

7. **Upstream runtime surfaces are not safe security boundaries.** The Explorer
   explicitly has no authentication and permits GET, POST, and DELETE. The Agno
   KG toolkit accepts agent-supplied strings beginning with `MATCH` and executes
   them as raw Cypher. Neither surface should be exposed to case agents or the
   network without a platform-owned authenticated API, allowlisted operations,
   case scoping, horizon enforcement, and write approval.

8. **The recommended database topology is one canonical evidence/control plane
   with derived projections—not a database per concept and not separate
   ignorant/hindsight stores.** Domain, topic, and horizon are independent
   metadata axes. A pass is a retrieval permission, never a destination.

## Research basis and exact revision

Primary upstream sources reviewed:

- Official repository: <https://github.com/semantica-agi/semantica>
- Official documentation: <https://docs.getsemantica.ai/>
- Architecture: <https://docs.getsemantica.ai/architecture/>
- Agno integration: <https://docs.getsemantica.ai/integrations/agno/>
- Core concepts: <https://docs.getsemantica.ai/concepts/>
- Context module: <https://docs.getsemantica.ai/reference/context/>
- Quickstart: <https://docs.getsemantica.ai/quickstart/>
- Change management: <https://docs.getsemantica.ai/guides/change-management/>

The official GitHub repository redirects from the older HawkSight organization
to `semantica-agi/semantica`. The reviewed local clone is:

- Path: `.research/semantica-upstream`
- Commit: `1ad00075a3ac51d764dfc34135980849657641f9`
- Commit time: `2026-08-02T13:19:12+05:30`
- Subject: merge of PR #821, record-decision logging
- Declared package version: `0.6.0`
- License: MIT, copyright HawkSight AI
- Inventory: 346 source Python files, 243 test Python files, and 24 test files
  explicitly carrying an integration marker

The official citation page still referenced `0.5.1` during review while the
repository and package metadata declared `0.6.0`. This is documentation drift,
so the commit hash—not a marketing version string—is the reliable review pin.

## Semantica capability inventory

### Ingestion, parsing, normalization, and splitting

Semantica ships broad general-purpose ingestion and parsing support: local
files, web sources, feeds, databases, streams, Git, email, cloud and enterprise
connectors, MCP sources, and multiple document/media formats. Normalization and
splitting include text cleanup, date/number/entity normalization, token and
semantic chunking, topic/community strategies, and provenance wrappers.

**Platform use:** selective only. The platform already has a custody-first,
format-aware parser registry and one canonical `NormalizedRecord` contract.
Semantica must not become an alternate intake door. It should receive records
only after H1/H2/H3 custody and platform parsing. Selected Semantica parsers may
be registered as substitution candidates where they add measurable coverage,
but they must obey the same tool contract and never bypass custody.

### Semantic extraction

The semantic extraction package includes:

- named entity recognition with configurable method chains;
- relation extraction and subject-predicate-object triplet generation;
- event detection;
- coreference resolution;
- semantic-role and semantic-network extraction;
- LLM-backed and local/model-backed providers;
- batch execution, validation, confidence metadata, retries, and provenance;
- temporal extraction of relation validity windows.

**Platform use:** this should be Semantica's first production role. Outputs are
`working.*` candidates, not evidence and not conclusions. Every candidate needs
the source artifact/H1, normalized record ID, text span or offsets, extractor
name/version, model/provider, prompt/config fingerprint, confidence, timestamps,
and run ID. The last-resort adjacency generator must be disabled or its outputs
quarantined from the evidence graph. Failed extraction must be visible; it must
not silently degrade from a trusted model to a weak heuristic without changing
the method and confidence recorded in provenance.

### Knowledge-graph construction and analytics

Semantica can construct graph nodes and relationships, merge entities, resolve
identities, create temporal relationships, persist to multiple graph stores,
and run graph analytics including centrality/PageRank, Louvain and Leiden
community detection, pathfinding, Node2Vec, similarity, link prediction, and
snapshots/versioning.

**Platform use:** Neo4j `evidence` is a derived, rebuildable projection of
approved evidence-linked facts. Graph algorithms can identify review leads,
clusters, bridges, changes, and potentially important paths; their outputs are
analytical candidates and must preserve algorithm/version/parameters. Link
prediction must never be displayed as an observed relationship.

### Bitemporal and temporal intelligence

`BiTemporalFact` models:

- `valid_from` and `valid_until`: when a fact was true in the represented world;
- `recorded_at` and `superseded_at`: when the system recorded or replaced it.

Temporal querying supports point-in-time/range queries, valid time,
transaction time, both axes, Allen interval relations, temporal paths,
evolution, consistency, revision chains, snapshots, and OWL-Time-oriented
export. Natural-language temporal rewriting is also present.

**Platform mapping:**

| Platform field | Semantica concept | Rule |
|---|---|---|
| `occurred_at` | `valid_from`/event time | Preserve the source precision and uncertainty; never replace absent source time with ingest time. |
| `knowledge_time` | closest to `recorded_at`, but semantically different | Record when the relevant person/agent could know the fact, not merely when software inserted it. Keep both if they differ. |
| fact retirement/correction | `superseded_at` | Append a new version; do not overwrite the historical assertion. |
| `disclosure_tier` | no upstream equivalent | Platform-owned enum and mandatory retrieval predicate. |

Some temporal query APIs operate over in-memory graph dictionaries and reserve
the textual query parameter for future use. Do not assume temporal filtering is
automatically pushed into Neo4j. The platform adapter must compile and test the
actual database predicate.

### Provenance and lineage

Semantica provides W3C PROV-O-oriented entities, activities, agents, derivation
links, checksums, wrappers across modules, lineage queries, and in-memory/SQLite
storage.

**Platform use:** map Semantica lineage into canonical PostgreSQL provenance and
run ledgers. In-memory or sidecar SQLite provenance is not sufficient for legal
replay. Required provenance should fail closed. Semantica's use of “chain of
custody” means transformation lineage; it must never be confused with the
platform's two H3 constructions or its immutable evidence custody events.

### Conflict detection and source comparison

Semantica can detect value, type, relationship, temporal, and logical conflicts,
track sources, calculate credibility, produce investigation guidance, and apply
resolution strategies such as recency, majority vote, confidence, or source
weighting.

**Platform use:** conflict detection is high-value. Automatic conflict
resolution is not. Store every conflicting assertion and source separately,
create a review item, and let a human or explicitly authorized review workflow
record a decision without erasing the alternatives.

### Deduplication and entity resolution

Candidate generation, similarity scoring, blocking, clustering, merging, and
multiple deduplication strategies are present. These can reduce duplicate
persons, organizations, locations, events, and repeated assertions.

**Platform use:** generate merge proposals with reasons and scores. Use stable
platform IDs and alias edges. Never destructively merge original evidence or
discard the pre-merge identities. An accepted merge should be reversible via
append-only mapping history.

### Ontology lifecycle and validation

Semantica supports ontology generation/inference/evaluation, namespace and reuse
management, alignment, versioning, OWL and SKOS, SHACL shape generation, and
validation modes including stricter closed shapes.

**Platform use:** seed Semantica from the owner-controlled `reference.*`
vocabularies. Treat generated classes, mappings, or ontology extensions as
proposals. Use SHACL as an executable gate before graph projection. Version the
ontology used for each extraction run so old results remain reproducible.

### Reasoning and inference

Available engines include forward chaining, Rete-style rule execution,
deductive and abductive reasoning, graph reasoning, SPARQL reasoning, Datalog,
and explanation/derivation paths.

**Platform use:** deductions and abductions belong in `analysis.*`, labeled by
kind. Abduction is a hypothesis, not a fact. Every conclusion must retain its
premises, rule/engine version, confidence where applicable, horizon ID, and
source lineage. Reasoning must run after retrieval filtering so future facts
cannot leak into the ignorant walk.

### Context graphs and decision intelligence

Semantica provides `ContextGraph`, `AgentContext`, vector-backed memory,
decision recording, causal chains, precedent search, policy versioning,
compliance checks, checkpoints/diffs, multi-hop GraphRAG, and shared agent
context.

**Platform use:** selectively adopt decision/provenance concepts, not the
default storage topology. `ContextGraph` is in-memory by default. The upstream
`AgnoKnowledgeGraph` accepts graph-backend parameters but constructs a bare
`ContextGraph()`, a FAISS vector store, and an in-process `_docs` cache; those
backend arguments do not produce the advertised persistent production path in
the reviewed source. Graphiti remains the agent-belief system. PostgreSQL
records platform decisions and policies. Semantica may analyze or explain them.

### Storage and exports

Graph stores include Neo4j, FalkorDB, Apache AGE, and Amazon Neptune. Vector
stores include FAISS, Weaviate, Qdrant, Milvus, PgVector, Pinecone, and SQLite.
Triplet stores include Blazegraph, Jena, RDF4J, and Anzo. Exports include RDF,
OWL, SHACL, JSON/JSON-LD, YAML, CSV, Parquet, Arrow, Neo4j CSV, GraphML, GEXF,
DOT, and AQL.

**Platform use:** Neo4j and Weaviate only for the current target. Avoid adding
another live store merely because Semantica supports it. Export capabilities
are valuable for court packages, interoperability, audits, and rebuilds, but
exports must be generated from approved/versioned data and carry manifests and
lineage.

### Pipeline, services, CLI, MCP, and Explorer

Semantica includes pipeline builders and validation, dependency sorting,
parallelism, resource scheduling, retries/backoff, failure recovery,
incremental/delta processing, CLI entry points, a REST service, an MCP server,
and the Knowledge Explorer UI/API.

**Platform use:** reuse pipeline internals inside a dedicated worker where they
fit, but keep the platform workflow ledger and approval model authoritative.
Do not expose the Explorer directly. Do not expose Semantica's raw MCP graph
tools directly to agents. Wrap narrowly scoped capabilities through the
platform API and ContextForge federation.

## Local implementation assessment

### What exists

- `server/vendored/semantica`: full old Semantica source, version
  `0.3.0-alpha`.
- `server/analysis/semantica_wiring.py`: desired Weaviate, Neo4j, and seed
  configuration expressed as dictionaries.
- `tests/test_semantica_wiring.py`: configuration assertions, including secret
  names rather than values.
- Architecture text assigning Semantica to Neo4j `evidence` and Graphiti to
  Neo4j `memory`.

### What does not exist

- no installed/importable `semantica` distribution in the current environment;
- no production Semantica worker/service or lifecycle;
- no adapter from `NormalizedRecord` to Semantica extraction inputs;
- no candidate-output tables and promotion path proven end to end;
- no actual PostgreSQL seed loader for the declared ontology/entity tables;
- no authenticated platform API for Semantica capabilities;
- no Neo4j projection implementation, idempotency key, or rebuild command;
- no horizon-filtered Semantica/Neo4j/Weaviate query gateway;
- no live integration tests against Neo4j and Weaviate;
- no real Agno 2.8 compatibility tests;
- no observed Semantica write in the deployed system.

Therefore, “Semantica is first-class” is the desired product position, not the
current implementation state.

## Recommended target topology

```text
Original files / exports
        |
        v
R2 immutable objects + PostgreSQL custody (H1/H2/H3)
        |
        v
Platform parsers -> NormalizedRecord
        |
        +------------------------------+
        |                              |
        v                              v
PostgreSQL working records       Semantica worker
(canonical clocks/tiers)         (extract candidates only)
        |                              |
        |                       PostgreSQL candidate +
        |                       provenance/review ledger
        |                              |
        |                     approval/validation gate
        |                              |
        +--------------+---------------+
                       |
             rebuildable projections
               /               \
              v                 v
     Neo4j `evidence`       Weaviate retrieval
     approved fact graph    domain/topic metadata

Agent retrieval gateway (mandatory pre-filter by case + horizon)
              |
       +------+------+
       |             |
 ignorant walk   hindsight view
       |
Graphiti -> Neo4j `memory` (the ignorant agent's belief history)
```

### Store responsibilities

| Store | Responsibility | Authority | Rebuildability |
|---|---|---|---|
| R2 | Original immutable bytes and export packages | Canonical original | Primary recovery root |
| PostgreSQL `evidence` | Custody, immutable raw references, source identity | Canonical | Rebuilt only from originals with custody verification |
| PostgreSQL `working` | Normalized records, extraction candidates, entity aliases, review/promotion | Canonical derived/control state | Rebuilt from evidence; preserve human review separately |
| PostgreSQL `analysis` | Findings, hypotheses, explanations, horizon deltas | Canonical analytical record | Recomputed from approved inputs/rules; versioned |
| PostgreSQL `reference` | Owner-curated ontologies, patterns, vocabularies | Canonical curated data | Precious; version and back up |
| PostgreSQL `ops` and `ai` | Runs, approvals, AgentOS sessions/memory/admin/content/learning | Canonical operational state | Consolidate from fragmented DB handles |
| Neo4j `evidence` | Approved evidence/entity/event/relation projection | Derived | Fully rebuildable from PostgreSQL |
| Neo4j `memory` | Graphiti ignorant-agent beliefs and discoveries | Agent cognitive state | Separate lifecycle; never confused with evidence |
| Weaviate | Chunk/entity/fact retrieval projection | Derived | Fully rebuildable; all queries pre-filtered |
| SurrealDB | Legacy operational data during exit | Temporary/read-only | Export, reconcile, then park; never delete here |

### Independent metadata axes

Every retrievable unit should carry these independent axes:

- `case_id` / tenant boundary;
- `domain` such as legal, behavioral, platform design, or evidence;
- `topic_tags`, zero or more;
- `occurred_at` plus precision/uncertainty;
- `knowledge_time` plus whose knowledge it represents;
- `disclosure_tier`;
- source and custody IDs;
- extraction/review status;
- ontology/schema version.

Do not encode these axes by multiplying databases or collections. In particular,
do not build separate ignorant and hindsight stores. The same item is written
once; the agent's horizon determines whether it is eligible before ranking.

## Knowledge-horizon implementation contract

The horizon is the product's load-bearing mechanism. The ignorant agent performs
a sequence of retrievals over advancing horizons. The hindsight agent sees the
full eligible case record. Their delta is the deliverable.

Mandatory rules:

1. Extraction can inspect all custody-approved material because it forms no
   beliefs. Extraction output still carries all clocks and disclosure metadata.
2. Agent retrieval must apply `case_id`, `knowledge_time`, and disclosure policy
   before keyword, vector, or graph ranking/traversal.
3. Weaviate calls through Agno must use dict filters. Agno 2.8's adapter drops
   `FilterExpr` lists, which would silently expose future facts.
4. Neo4j traversal must start from eligible nodes/edges and prevent paths from
   crossing an ineligible future fact.
5. PostgreSQL queries must share the same policy object/compiled predicate.
6. Graphiti contains what the ignorant agent actually learned during the walk;
   it is not a second copy of evidence and cannot be used to bypass the horizon.
7. Every agent run records the exact horizon, policy version, retrieval query,
   eligible population count, returned IDs, and model context IDs.
8. Tests must use a planted future fact that is highly vector-similar and prove
   it never appears before its knowledge time. Post-filtering top-k is a failure.

## AgentOS, PAL, Dev, and knowledge recommendations

The confusing UI/database state comes from exposing infrastructure identities
rather than product concepts and from several genuine runtime gaps.

Confirmed current issues include fragmented database IDs, boot-time snapshotting
of the Knowledge handle, incomplete inspection aliases, raw AgentOS workflows
that bypass the platform ledger/HITL path, version skew (`requirements.txt`
2.8.0 vs lock/environment 2.8.6), and weak preconfigured-agent capabilities.

Recommended changes:

- Present logical product surfaces: Evidence, Working, Analysis, Reference,
  Agent Memory, Platform Knowledge, and Operations. Hide physical `db_id` and
  generated `knowledge_id` from normal users.
- Consolidate AgentOS operational/admin/content/learning state behind one
  PostgreSQL-backed Agno database object where the pinned Agno API permits it.
- Replace the boot-time Knowledge snapshot with a durable provider/proxy that
  can recover without restarting the process.
- Route every workflow surface through one custody/ledger/HITL implementation.
- Make PAL a real project companion with scoped platform-design knowledge,
  decision/status tools, and stable memory identity—not a memory-only shell.
- Make Dev a scoped engineering app with repository knowledge, diagnostics,
  tests, and explicit write approvals. Do not grant raw database or raw Cypher
  access.
- Either mount Transcript Miner or remove its preconfigured prompt; configuration
  must not advertise absent agents.
- Define typed outputs for extraction, findings, reviews, and handoffs.
- Pin and assert one exact Agno version in development, CI, and production before
  adapting Semantica.

## SurrealDB exit recommendation

Because the identified SurrealDB defects are upstream and cannot be fixed here,
continuing to make it the operational dependency of every AgentOS surface adds
risk without creating unique product value.

Use a reversible exit:

1. Freeze new Surreal-specific feature work.
2. Inventory and export sessions, memories, runs/traces, content state, and any
   other unique records with counts and checksums.
3. Create corresponding PostgreSQL destinations using Agno's supported schema,
   plus platform-owned mapping tables where needed.
4. Dual-read or shadow-compare only long enough to prove parity; avoid a
   long-lived dual-write architecture.
5. Switch one logical capability at a time and validate end-user UI behavior.
6. Keep SurrealDB and its files read-only/parked through an agreed retention
   period. Move anything retired to `to_be_deleted`; only the owner deletes it.

## Security and legal-evidence guardrails

- Semantica gets a dedicated service identity. It can read approved working
  inputs and write candidate/projection destinations; it cannot modify custody.
- Agents receive narrow tools, never database drivers, arbitrary filesystem
  paths, raw Cypher, or Semantica's unauthenticated Explorer.
- Graph projection uses idempotent, parameterized operations with allowlisted
  labels and relationship types. The upstream `Neo4jStore` supports arbitrary
  query and destructive methods; do not expose it directly.
- Every material write uses the platform approval mechanism and records the
  actor, tool, model, inputs, result, and code/config versions.
- Raw evidence text is not sent to an external model merely because Semantica
  supports that provider. Provider selection and redaction follow evidence
  policy.
- Automatic conflict resolution, entity merges, ontology changes, inferences,
  and link predictions cannot overwrite canonical data.
- The Explorer may be useful as an operator UI only after it is mounted behind
  platform authentication/authorization and mutation routes are disabled or
  separately approved.

## Implementation sequence and acceptance gates

### Phase 0 — freeze the contracts

- Resolve and document the exact Agno version.
- Adopt a Semantica source strategy: pinned upstream commit or a maintained
  platform fork. Do not silently copy `0.6.0` over the old vendor tree.
- Write an ADR for Semantica's role, database ownership, and SurrealDB exit.
- Define platform candidate, provenance, review, promotion, and projection
  schemas through new numbered migrations.

**Gate:** fresh database bootstrap succeeds from numbered migrations; contracts
name all clocks, disclosure tier, custody links, and review state.

### Phase 1 — isolated Semantica worker

- Package Semantica in its own image/venv because its “core” dependencies include
  Torch, Transformers, spaCy, sentence-transformers, OpenCV, librosa, FAISS,
  plotting, and notebook libraries.
- Expose a small internal API: extract entities, extract relations/events,
  detect conflicts, propose dedup/entity links, validate with ontology.
- Accept normalized IDs or immutable blob references, never arbitrary host paths.
- Write outputs to PostgreSQL candidates and provenance only.

**Gate:** one example of each supported record type runs end to end in a
disposable database; zero writes reach custody, Neo4j, or Weaviate.

### Phase 2 — ontology and extraction validation

- Seed owner-curated reference data.
- Establish gold datasets for NER, relations, event time, entity resolution,
  conflicts, and false-positive behavior.
- Disable last-resort fabricated relations.
- Record model/config/prompt and ontology versions.

**Gate:** measured precision/recall thresholds are approved; empty and failed
outputs are visible; no fallback can masquerade as the primary method.

### Phase 3 — governed Neo4j evidence projection

- Define stable node/edge IDs and uniqueness constraints.
- Project only approved facts with source IDs, clocks, disclosure tier,
  confidence, status, and projection version.
- Implement rebuild and reconciliation from PostgreSQL.
- Keep Graphiti permissions confined to `memory`.

**Gate:** rebuild twice produces identical counts/IDs; graph rows reconcile to
PostgreSQL; unauthorized database writes fail at the database role.

### Phase 4 — governed Weaviate projection and retrieval

- Choose collection shape based on operational scale, not horizon. Domain and
  topic remain metadata.
- Carry all horizon and provenance metadata at chunk/object level.
- Implement one platform retrieval policy that emits Weaviate dict filters,
  PostgreSQL predicates, and Neo4j predicates.

**Gate:** planted-future-fact tests pass across all stores; returned `k` is not
silently reduced by post-filtering; every result traces to custody.

### Phase 5 — agent integration

- Build new Agno 2.8-native adapters against the actual pinned wheel; do not use
  the legacy upstream memory/knowledge bases.
- Give agents read/query tools through the retrieval gateway and candidate write
  tools through approval-gated APIs.
- Implement the ignorant horizon walk and hindsight run as explicit workflows.
- Persist the delta as a versioned analysis artifact.

**Gate:** live observed writes and retrievals prove each feature. Config
acceptance alone is not evidence. Contamination tests prove the ignorant agent
cannot see a planted future fact.

### Phase 6 — operational/UI repair and Surreal retirement

- Expose logical surfaces and health/reconciliation views.
- Migrate AgentOS operational state to PostgreSQL with count/checksum parity.
- Repair PAL/Dev product contracts and remove phantom configuration.
- Preserve SurrealDB read-only until owner-approved retirement.

**Gate:** the user can see agents, workflows, knowledge contents, vectors,
entities, graph facts, memories, runs, and failures through logical product
views without knowing physical database IDs.

## Test matrix required before “first-class” may be claimed

| Area | Required proof |
|---|---|
| Compatibility | Real imports and execution against the exact pinned Agno and Semantica revisions; no stub-only acceptance. |
| Custody | Semantica cannot alter evidence rows/blobs; every output resolves to source and H1. |
| Extraction | Gold-set precision/recall; fallback identity; empty-output behavior; deterministic replay where possible. |
| Temporal | Valid-time and knowledge-time mapping, uncertainty, supersession, point-in-time query tests. |
| Horizon | Highly similar future facts excluded before ranking in PostgreSQL, Weaviate, and Neo4j. |
| Projection | Idempotent rebuild, counts/checksums, orphan detection, stable IDs. |
| Security | Raw Cypher rejected; cross-case access rejected; unauthenticated access rejected; DB roles enforced. |
| HITL | Candidate promotion, conflict resolution, merge, ontology change, and material graph writes require recorded approval. |
| Failure | Provider/model/store outage records a failed stage; no false COMPLETED and no silent fallback. |
| UI | End-user views show logical domains and status with drill-down provenance, not opaque DB IDs. |

## Decisions needed from the owner

1. Approve Semantica's role as a governed extraction/accountability worker with
   PostgreSQL as canonical state and Neo4j/Weaviate as projections.
2. Choose source maintenance: pinned upstream dependency plus adapters, or a
   platform fork. Recommendation: a pinned fork/image until upstream's Agno 2.8
   compatibility and forensic defaults are resolved.
3. Approve SurrealDB removal from the critical path with read-only preservation.
4. Approve the first production slice: NER + relation/event candidates +
   provenance + SHACL validation, before reasoning or agent decision tooling.
5. Decide which inferred/analytical outputs require individual approval versus
   batch review. Evidence and ontology mutations should always require approval.

## Known limitations of this review

- This was a source/static review plus local environment probes, not a deployment
  of upstream Semantica against live case services.
- Upstream's full test suite was inventoried but not installed/run because its
  default dependency set is large and would mutate the platform environment.
- Neo4j, Weaviate, and Surreal live data were not modified.
- Marketing performance/compliance claims were not accepted as guarantees.
- The source clone is a point-in-time snapshot; future upstream changes require
  a new pinned review.
- Existing repository documentation contains chronological drift. The
  2026-08-02 root `AGENTS.md` knowledge-horizon statement and the owner's latest
  rulings were treated as controlling over stale Surreal/Milvus/LiteLLM details.

## Validation and command-error audit

The PowerShell profile initially emitted a OneDrive-hosted module import error
on every shell startup. All commands that had an actual error, ambiguous glob,
truncated output, or expected nonzero status were rerun with the profile
disabled and then rerun again after the profile was repaired.

Corrections and outcomes:

- Windows `compose*.yaml` glob error: replaced with literal file enumeration;
  the compose topology findings remain.
- missing root `tests/conftest.py`: confirmed absent; the relevant Agno-specific
  conftest exists and installs stubs.
- Agno `find_spec` probe stopped at an absent parent module: replaced with
  non-throwing installed-file checks; four legacy modules are absent and
  `tools/toolkit.py` is present.
- malformed raw-Cypher regex: replaced with literal searches; raw `MATCH`
  execution is confirmed at `integrations/agno/kg_toolkit.py:283-286`.
- broad source diff included `.git` and `.venv`: recomputed on package source
  only; confirmed 157 files, +36,486/−2,566.
- `git diff --no-index` exit code 1: explicitly handled as “differences found,”
  not a failed command.
- ontology/horizon scans: rerun with `-g '*.py'`; ontology features are present,
  platform horizon terms have zero matches, and temporal fields span 23 source
  files.

No recommendation changed after this audit. No partial handoff was created by
the interrupted command, and no source, database, or deployment state was
changed during the review.

## Immediate handoff

The next implementation session should begin with Phase 0, not by installing
Semantica into the main environment and not by wiring its upstream Agno classes.
The smallest safe deliverable is:

1. ADR and exact version pins;
2. isolated Semantica worker image;
3. `NormalizedRecord` input adapter;
4. PostgreSQL candidate/provenance schemas;
5. NER/relation/event extraction with last-resort relations disabled;
6. one-file-per-format disposable-database validation;
7. no Neo4j/Weaviate writes until those gates pass.

That sequence makes Semantica genuinely first-class while preserving the
platform's defining knowledge-horizon mechanism and avoiding another hidden,
parallel source of truth.
