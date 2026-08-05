> _Byline: Claude Code · Sonnet (R1f) · 2026-07-11_

# Semantica — vendored knowledge-engineering framework

Deep-dive on `server/vendored/semantica/` (~615 files, third-party, MIT-licensed,
upstream `Hawksight-AI/semantica`) and the platform's integration design
(`server/analysis/semantica_wiring.py`). Semantica is the platform's **entity
VIP candidate** — a general-purpose knowledge-graph/semantic-layer framework
being evaluated for the cross-source conflict-detection, dedup, and
decision-provenance lanes the current custody→parse→normalize→Graphiti path
does not cover.

---

## 1. What Semantica is (its own claim)

Semantica bills itself (`mkdocs.yml` site description) as an **"Open Source
Framework for building Semantic Layers and Knowledge Engineering"** — a
general-purpose Python toolkit that turns unstructured data into knowledge
graphs, embeddings, and semantic layers. It is not domain-specific (no legal/
forensic awareness) and not a memory framework in the agent-session sense —
it is closer to an ETL + graph-construction + reasoning toolkit that happens
to have a `context/` module aimed at agent memory as one of ~24 modules.

**Maturity / version drift.** `pyproject.toml` declares `version = "0.3.0-alpha"`
and `Development Status :: 3 - Alpha`; the package's own `semantica/__init__.py`
declares `__version__ = "0.2.7"`. These disagree — the packaging metadata was
bumped without updating the runtime version string, a small but real signal of
an actively-churning, not-yet-stabilized alpha project. Reinforcing that: the
`semantica/__init__.py` file has its `core`, `pipeline`, and `visualization`
top-level imports **commented out** ("Import submodules for dot notation
access" section) — so `from semantica import Semantica` (the orchestrator
class) is not guaranteed to work at package-root import time; submodules are
lazy-loaded via a `_ModuleProxy`. The `evals/` module's own doc page says
outright: `!!! warning "Coming Soon" — This module is currently in active
development. Documentation will be available soon.` There is no `README.md`
at the repo root at all (checked case-insensitively) — the only prose docs
are the `docs/reference/*.md` module references plus a `mkdocs.yml` nav that
references several guide pages (`index.md`, `getting-started.md`,
`installation.md`, `quickstart.md`, `concepts.md`, `modules.md`,
`use-cases.md`, `examples.md`, `glossary.md`, `cookbook.md`, `community.md`,
`contributing.md`, `faq.md`, `license.md`) that **do not exist in the vendored
tree** — only `docs/reference/` was vendored, so the onboarding/concept layer
of the docs is absent locally.

**Heavy deps are CORE, not optional.** The "safe default" install
(`pyproject.toml` `[project] dependencies`) already pulls `torch>=1.12.0`,
`transformers>=4.20.0`, `spacy>=3.4.0`, `sentence-transformers>=2.2.0`,
`umap-learn`, `faiss-cpu`, `fastembed`, `onnxruntime`, `opencv-python`,
`librosa`, `rdflib`, `networkx`, `matplotlib`/`seaborn`/`plotly` — i.e. the
ML/NLP/CV/vector stack is unconditional, not gated behind an extra. On top of
that sit ~9 optional-dependency groups (`llm-*`, `graph-neo4j`,
`vectorstore-*`, `db-snowflake`, `infra`, `cloud`, `gpu`, `split-*`, `dev`).
This is why the platform's root `pyproject.toml` explicitly excludes
`server/vendored/semantica` from the default pytest run (`norecursedirs` +
comment: *"server/vendored/semantica's test suite pulls heavy ML deps (torch,
spacy, transformers) even in its 'safe default' install and is NOT collected
by default — run it opt-in, explicitly, after installing its extras"*). It is
also excluded from ruff/mypy (per `server/AGENTS.md`: `vendored/` is
"import-only, excluded from ruff/mypy/pytest").

**Entry points.** `pyproject.toml` registers three CLI/service entry points:
`semantica` (CLI, `semantica.cli:main`, Click+Rich), `semantica-server`
(`semantica.server:main`, a FastAPI/uvicorn REST wrapper around the
`Semantica` orchestrator class), and `semantica-worker`
(`semantica.worker:main`, a signal-handling background-task worker wrapping
the same orchestrator). None of these are wired into the platform today —
they are vendored library surface, not deployed services.

---

## 2. Capability map — module by module

The package (`semantica/`) has 24 top-level modules. Each ships a
`docs/reference/<module>.md` (rich, hand-written-looking prose with class/
method tables) and a `<module>_usage.md` inside the package dir itself.

### `ingest/` — universal data ingestion
Entry point: `semantica.ingest.ingest()` convenience function plus dedicated
ingestor classes, one file per source type:
`file_ingestor.py`, `web_ingestor.py`, `stream_ingestor.py` (Kafka/RabbitMQ/
Kinesis/Pulsar), `repo_ingestor.py` (git clone + AST parsing), `feed_ingestor.py`
(RSS/Atom + `monitor()` polling), `email_ingestor.py` (IMAP/POP3),
`db_ingestor.py` (Postgres/MySQL/SQLite/MSSQL/Oracle/MongoDB/Cassandra/
BigQuery/Redshift), `snowflake_ingestor.py` (dedicated Snowflake connector),
`duckdb_ingestor.py`, `elastic_ingestor.py`, `mongo_ingestor.py`,
`pandas_ingestor.py`, `gdrive_ingestor.py`, `huggingface_ingestor.py` (HF
Hub datasets), `api_ingestor.py`, `mcp_ingestor.py` + `mcp_client.py` (MCP
server ingestion — connect/`ingest_resources()`/`call_tool()`),
`ontology_ingestor.py`. Config surface: env vars (`INGEST_USER_AGENT`,
`AWS_ACCESS_KEY_ID`, `KAFKA_BOOTSTRAP_SERVERS`) or YAML (`ingest.web.rate_limit`,
`ingest.files.max_size/allowed_extensions`). `ingest_provenance.py` wraps
ingestion with provenance stamping.

### `parse/` — universal document/content parser
Extracts text+structure+metadata from PDF/DOCX/PPTX/Excel/TXT/RTF, HTML/XML/
JS-rendered pages, JSON/CSV/XML/YAML, MIME email, source code (→ ASTs), and
media (OCR for images, metadata for audio/video). Feeds `split/`.

### `normalize/` — cleaning/standardization
Text cleaning (encoding fixes, whitespace), entity-name normalization,
date/time → ISO 8601, numeric/unit normalization, language detection with
confidence scoring.

### `split/` — chunking (15+ methods)
Recursive, semantic (embedding-boundary), entity-aware, relation-aware,
structural (headings/paragraphs/tables) chunking, explicitly including
**"KG-aware chunking"** that preserves entities/relationships/graph structure
"for GraphRAG workflows" — i.e. this module is graphRAG-adjacent tooling for
Semantica's own downstream KG construction, plus chunk quality validation.

### `semantic_extract/` — entity/relation/event/triplet extraction
The core NLP module. Files: `named_entity_recognizer.py`, `ner_extractor.py`,
`relation_extractor.py`, `event_detector.py`, `triplet_extractor.py`,
`coreference_resolver.py`, `semantic_network_extractor.py`,
`semantic_analyzer.py`, `extraction_validator.py`, `llm_extraction.py`,
`providers.py`, `cache.py`, `schemas.py`. **Models used**: NER supports six
methods selectable via a `method` parameter on `NERExtractor` — `"pattern"`
(regex), `"regex"`, `"rules"` (linguistic rules), **`"ml"` (spaCy, the
default)**, `"huggingface"` (custom HF NER models), and `"llm"` (provider-based:
OpenAI, Gemini, Groq, Anthropic, Ollama, HuggingFace Transformers, via
`llm_extraction.py`'s `providers` abstraction). So spaCy is the out-of-the-box
default; LLM extraction is opt-in per-call/per-provider and used for
enhancement/refinement of ML-extracted output (entity/relation validation and
correction), not as the sole path. Coreference resolution resolves pronouns
to entities before relation/triplet extraction. Output includes confidence
scores and batch/parallel processing.

### `kg/` — knowledge-graph construction & analysis
`GraphBuilder` (`build(sources)`, entity-resolution merge-on-build),
`EntityResolver` (fuzzy + semantic-similarity dedup), `NodeEmbedder`
(Node2Vec/DeepWalk/Word2Vec), `SimilarityCalculator` (cosine/euclidean/
manhattan/Pearson, batch/pairwise), `PathFinder` (Dijkstra/A*/BFS/k-shortest),
`LinkPredictor` (preferential attachment/common-neighbors/Jaccard/Adamic-Adar/
resource-allocation), `CentralityCalculator` (degree/betweenness/closeness/
eigenvector/PageRank), `CommunityDetector` (Louvain/Leiden/label-propagation/
k-clique), `ConnectivityAnalyzer` (components/bridges/density, NetworkX-backed
with fallback), `TemporalQuery`/temporal graph support (`valid_from`/
`valid_until` time-aware edges, `.at_time()` snapshots, snapshot diffing),
`GraphBuilderWithProvenance`/`AlgorithmTrackerWithProvenance` for provenance-
tracked builds, `seed_manager.py` (KG-level seeding). Config:
`KG_MERGE_STRATEGY`, `KG_TEMPORAL_GRANULARITY`, `KG_RESOLUTION_STRATEGY` env
vars or `kg.resolution.threshold/strategy` + `kg.temporal.*` YAML.

### `graph_store/` — property-graph persistence
Unified interface over **Neo4j** and **FalkorDB** (Redis-based); also
`age_store.py` (Apache AGE) and `amazon_neptune.py`. Cypher query support
across backends, built-in PageRank/community/path-finding, bulk loading,
ACID transactions with rollback. This is the module the platform wires to
**our** Neo4j (see §4).

### `triplet_store/` — RDF triplet storage
Backends: Blazegraph, Apache Jena, RDF4J (`blazegraph_store.py`,
`jena_store.py`, `rdf4j_store.py`). SPARQL 1.1 querying, RDFS/OWL reasoning
for inference, federation across stores, `bulk_loader.py`. Not currently
wired to any platform store.

### `vector_store/` — vector database abstraction
Backends: FAISS (local), Weaviate, Qdrant, Pinecone, **Milvus**
(`milvus_store.py`), pgvector (`pgvector_store.py`). Unified interface,
hybrid search (`hybrid_search.py`/`hybrid_similarity.py`), namespace/
multi-tenant isolation (`namespace_manager.py`), metadata filtering
(`metadata_store.py`), plus a `decision_embedding_pipeline.py` /
`decision_vector_methods.py` pair tying vector storage to the `context/`
module's decision-tracking. This is the module the platform wires to
**our** Milvus (§4).

### `embeddings/` — embedding generation
`EmbeddingGenerator` (orchestrator), provider stores for Sentence-Transformers,
FastEmbed, OpenAI, BGE models (`provider_stores.py`), `TextEmbedder`
(simplified text→vector), `VectorEmbeddingManager` (formats for FAISS/Qdrant/
Weaviate/Milvus), `pooling_strategies.py`, `graph_embedding_manager.py`
(bridges to `kg.NodeEmbedder`). Note Semantica's vector-store default
dimension (768, sentence-transformers-shaped) — the platform's wiring
explicitly overrides this to 1024 for bge-m3 (see §4, and the wiring test
`test_vector_store_targets_our_milvus_with_defaults` asserts `dimension == 1024
# bge-m3, NOT Semantica's 768 default`).

### `context/` — "the intelligent brain for AI agents"
Its own docs pitch it as agent memory + decision intelligence + knowledge
organization: `AgentMemory` (`agent_memory.py`) — vector-embedded memory
items with deque-based temporal indexing, cosine-similarity retrieval with
keyword-search fallback, retention-policy cleanup, KG-linked memory
(entities/relationships attached to each `MemoryItem`), conversation-history
retrieval; `context_graph.py`/`graph_schema.py` — graph-shaped context;
`context_retriever.py` — hybrid retrieval; `entity_linker.py` — cross-source
entity linking with MD5-hash or text-based URI assignment, Jaccard-like text
similarity, KG-lookup matching, bidirectional cross-document links, "entity
web" construction; `decision_context.py`/`decision_recorder.py`/
`decision_query.py`/`decision_models.py`/`decision_methods.py` — decision
tracking/replay; `causal_analyzer.py` — causal-relationship analysis;
`policy_engine.py` — decision policy rules; `agent_context.py` — top-level
agent context object tying it together. This is the module most directly
comparable to agno's `LearningMachine` (§5) — but it is generic/local-only
(no bitemporal Neo4j write path of its own; it composes whatever
`vector_store`/`graph_store` backends you hand it).

### `provenance/` — W3C PROV-O compliant tracking
`manager.py`/`schemas.py`/`storage.py` (InMemory + SQLite backends),
`integrity.py`, `bridge_axiom.py`. Implements `prov:Entity`/`prov:Activity`/
`prov:Agent`/`prov:wasDerivedFrom` from the PROV-O ontology. Claims coverage
across "all 17 Semantica modules" (docs), source tracking down to document
ID/page/section/quote, 100% backward-compatible opt-in design. This is the
module the platform's forensic-DB planning doc explicitly cites as the model
for our graph's own provenance strategy (see §4/§5 — "PROV-O alignment
(Semantica governance)").

### `change_management/` — version control & audit trails
`change_log.py`, `managers.py`, `ontology_version_manager.py`,
`version_storage.py` (InMemory + SQLite, ACID). SHA-256 snapshot integrity
verification, entity/relationship-level diffs for KGs, structural
(class/property/axiom) versioning for ontologies, author-attributed audit
logs.

### `conflicts/` — cross-source conflict detection & resolution
Detects value/type/relationship/temporal conflicts across sources; resolves
via voting, source-credibility, recency, or confidence-score strategies;
conflict-pattern/trend/severity analysis; source-credibility tracking;
auto-generated "investigation guides" for manual resolution. **This is the
module the platform's wiring doc explicitly names as Semantica's net-new
value-add** ("cross-source CONFLICT detection, dedup, and decision-provenance
— lanes the current custody→parse→normalize→Graphiti path does not cover").

### `deduplication/` — entity dedup/merge
Multi-factor similarity (Levenshtein, Jaro-Winkler, cosine, Jaccard),
configurable merge strategies (keep-first, most-complete, etc.), clustering
for batch dedup, provenance-preserving merges.

### `ontology/` — automated ontology generation
6-stage pipeline generating OWL ontologies from raw data; inference engine
(infers classes/properties/hierarchies from entity patterns); quality
evaluation (coverage/completeness/granularity); export to Turtle/RDF-XML/
JSON-LD.

### `reasoning/` — inference
Forward-chaining rule-based inference (`IF Parent(x,y) AND Parent(y,z) THEN
Grandparent(x,z)`-style), SPARQL-based reasoning, high-performance pattern
matching, explanation generation for derived facts.

### `seed/` — bootstrap KGs from verified sources
`seed_manager.py` loads CSV/JSON/DB/API seed data (taxonomies, reference
data, verified entities), validates against schema, transforms to KG format,
merges with extracted data under configurable strategies, versions seed
sources. **This is the module name the platform's "seed-first hybrid"
integration pattern borrows its vocabulary from** — though the platform's own
seeding (§4) is a bespoke Postgres-FK projection, not literally calling
Semantica's `seed/` module machinery (open question, not confirmed either
way in the wiring code).

### `export/` — multi-format serialization
10+ formats: RDF (Turtle/RDF-XML/JSON-LD/N-Triples — `rdf_exporter.py`,
`owl_exporter.py`), JSON/CSV/Parquet/Arrow, GraphML/LPG (`lpg_exporter.py`),
direct Cypher-generating exports to Neo4j/ArangoDB/Memgraph
(`graph_exporter.py`, `arango_aql_exporter.py`), `report_generator.py`,
`vector_exporter.py`, `yaml_exporter.py`. Extensible custom-serializer
framework.

### `core/`, `utils/`, `evals/`, `visualization/`, `llms/`
`core/orchestrator.py` hosts the `Semantica` class — the optional top-level
orchestration/lifecycle/plugin-registry layer; docs explicitly say **prefer
calling individual modules directly** and reserve the orchestrator for
multi-module pipelines / app-level lifecycle / plugin integration. `utils/`
is shared logging/validation/error-handling/type-defs used internally by all
modules (not typically imported directly). `evals/` is a stub ("Coming
Soon" — no content). `visualization/` renders KGs (force-directed/
hierarchical/circular), ontology hierarchies, embedding projections (UMAP/
t-SNE/PCA), temporal timelines, and centrality/community dashboards.
`llms/` centralizes the multi-provider LLM abstraction used by
`semantic_extract/llm_extraction.py` and elsewhere.

---

## 3. Benchmarks

`benchmarks/` (`benchmarks.md`) is a dedicated performance-benchmark suite,
structurally mirroring the package's module layout, with an explicit design
principle of **isolation via mocks** ("Isolation: Use of mocks to ensure
benchmarks measure algorithm logic" and a "custom `conftest.py`
virtualization layer allows tests to run without heavy local dependencies")
— i.e. the benchmarks are deliberately decoupled from having torch/spaCy/
real backends installed, measuring algorithmic cost in isolation rather than
end-to-end system throughput. Directories and what they measure:

| Dir | Measures |
|---|---|
| `context/` | Low-level graph ops + memory-storage logic (`test_memory_storage.py`, `test_linking.py`, `test_retrieval_logic.py`, `test_graph_ops.py`) |
| `context_memory/` | Agent-level memory management + **GraphRAG retrieval patterns** (`test_agentic.py`, `test_graphrag.py`) |
| `core_processing/` | NER/extraction and graph-building throughput |
| `export/` | Serialization cost for JSON/CSV/RDF/GraphML/vector/semantic exports |
| `infrastructure/` | Regression-comparison engine (Z-score based, `compare.py`) — not a benchmark itself |
| `input_layer/` | Ingestion, parsing, splitting performance |
| `normalize/` | Text cleaning, encoding, date normalization, "heavy libs" cost |
| `ontology/` | Inference, serialization, reuse, namespace overhead |
| `output_orchestration/` | Parallelism + execution-pipeline management |
| `quality_assurance/` | Deduplication + conflict-resolution strategy cost |
| `storage/` | **Vector store (FAISS), graph store, and triplet store latency** — `test_embeddings.py`, `test_graph_store.py`, `test_triplet_storage.py`, `test_vector_storage.py` |
| `visualization/` | Layout-algorithm and chart-render cost |

CI integration: `--strict` mode fails a run if a regression >15% AND
Z-score >2.0 vs. the stored JSON baseline (`results/`) is detected — noise
below that Z-score threshold is tolerated. Three timestamped result runs are
checked in (`run_20260207_14_52_38.json` etc.), all dated 2026-02-07,
suggesting the suite was run once during initial vendoring/eval and not
re-run since. **What this tells us about intended use**: the benchmark
taxonomy treats "storage" (vector/graph/triplet) and "context_memory"
(agentic + GraphRAG) as first-class, separately-tracked performance surfaces
— consistent with Semantica being pitched as GraphRAG/agent-memory
infrastructure, not just a batch ETL tool, even though its actual `context/`
module is comparatively thin next to `kg/`, `semantic_extract/`, and the
store modules.

`tests/` (179 test files, opt-in per the root `pyproject.toml` note) mirrors
the same 24-module structure 1:1, plus `tests/cookbook/` (notebook-derived
tests) and `tests/integration/`.

---

## 4. Integration design — seed-first hybrid (`server/analysis/semantica_wiring.py`)

Full file read. This module builds **config dicts from env only** — it
performs no writes, bakes no secrets, and its own docstring states the
"actual Semantica deploy / any store creation is APPROVALS-gated." It is
design/local scaffolding, not a live deployment.

**Placement decision** (module docstring, citing "BOARD 2026-07-01, ADR
~0035"): Semantica runs as a **seed-first hybrid** targeting the platform's
own infra — it does not stand up a second graph or a second vector index.

- **Vector lane → OUR Milvus.** `vector_store_config()` derives
  `milvus_host`/`milvus_port` from `MILVUS_ADDRESS` (via
  `server/analysis/milvus_forensic.py`'s `MILVUS_URI`), sets
  `dimension = EMBED_TEXT_DIM` (**1024, bge-m3** — explicitly overriding
  Semantica's own 768-dim sentence-transformers default), `metric = "cosine"`,
  `enable_hybrid_search = True`, and pins
  `target_collections = ["forensic_records", "forensic_findings",
  "forensic_patterns"]` — i.e. Semantica writes its **derived/semantic**
  vectors directly into the platform's existing forensic Milvus collections,
  no second index. `namespace = "casebible"`. Credentials: `milvus_user`
  parsed from `MILVUS_TOKEN` (`user:pass` split), password referenced **by
  env-var name only** (`milvus_password_env = "MILVUS_TOKEN"`) — never
  inlined. `_milvus_host_port()` has explicit fallback logic (default host
  `100.119.96.29`, default port `19530`) covering scheme-ful/scheme-less/
  bare-host/trailing-slash URI forms.
- **Graph lane → OUR Neo4j, READ/derive-only.** `graph_store_config()` sets
  `backend = "neo4j"`, `uri` from `NEO4J_URI` (default
  `bolt://100.119.96.29:7687`), and critically: `role = "read_derive"`,
  `writer = "graphiti"`, `write_via_graphiti = True`,
  `graphiti_mcp_url_env = "GRAPHITI_MCP_URL"`. The docstring is explicit:
  *"The GRAPH WRITER STAYS GRAPHITI (ADR-0014): Graphiti owns bitemporal
  writes to Neo4j under `group_id="casebible"`. Semantica proposes; Graphiti
  persists."* — i.e. Semantica's own `graph_store` (Neo4j-capable, Cypher,
  transactions) module is deliberately **not** used as a writer here; the
  config only documents Semantica as a read/derive-side participant
  (entity-linking, conflict detection, decision-provenance) that hands off
  actual persistence to Graphiti.
- **Seed-first from Postgres.** `seed_config()`: `seed_from = "postgres"`,
  `ontology_tables = ["analysis.behavior_category", "analysis.detection_pattern",
  "analysis.pattern_lexicon"]`, `entity_tables = ["analysis.entity",
  "analysis.entity_alias"]`, `seal_policy = "skip_sealed_lexicon"` (sealed
  REDACTED lexicon rows never enter the graph), `extend_not_replace = True`
  — Semantica is meant to **extend the already-seeded behavioral ontology**
  (153 behavior categories, 512 detection patterns per the docstring) rather
  than invent a parallel taxonomy.
- **`full_wiring()`** nests all three configs plus `adr: "~0035 (Semantica
  placement)"`, `graph_writer: "graphiti"`, and
  `deploy: "APPROVALS-gated (prod-infra); this config is design/local only"`.
- **`secrets_referenced()`** — asserts only `MILVUS_TOKEN`, `NEO4J_PASSWORD`,
  `GRAPHITI_MCP_URL` are ever read (by name) from env; `tests/test_semantica_wiring.py`
  (in the platform's own `tests/`, not vendored) round-trips real-looking
  secret values through `full_wiring()` and asserts they never leak into the
  JSON dump — this is a load-bearing, actively-tested contract, not just a
  docstring claim.

**Two discrepancies worth flagging (not fixed, just surfaced):**

1. **`group_id` mismatch.** `graph_store_config()` asserts `group_id =
   "casebible"` (and the wiring test locks this in:
   `test_graph_store_defaults_and_graphiti_ownership` asserts
   `cfg["group_id"] == "casebible"`). But the actually-deployed Graphiti
   config (`docker/graphiti/config.yaml:38`) sets `group_id: "platform"`.
   These do not match today — either the wiring doc's `"casebible"` is
   aspirational/not-yet-applied, or the deployed Graphiti config needs
   updating before Semantica's Neo4j lane could safely coexist with it under
   the assumed partition key. `docs/planning/forensic-db-architecture/sections/
   06-neo4j-graphiti-semantica.md` §14 independently flags this whole area as
   unconfirmed: *"Semantica implementation is assumed, not confirmed (ADR
   ~0035 not yet read in full)... Confirm ADR-0035 specifics."*
2. **ADR `~0035` does not exist under that number.** The wiring file and the
   forensic-DB planning doc both cite "ADR ~0035 (Semantica placement)" (note
   the tilde — an approximate/placeholder citation), but the actual
   `docs/adr/0035-*.md` in this repo is
   **`0035-tools-subnamespacing-and-record-contract-home.md`** — an unrelated
   decision about `server/tools/` sub-namespacing. There is no ADR file
   specifically titled/numbered for "Semantica placement" in `docs/adr/`
   today (checked via `grep -rli semantica docs/adr/`, which hits 0003, 0007,
   0014, 0018, 0025, 0033 — mentions, not a dedicated Semantica-placement
   ADR). The "~0035" citation is a forward-reference to a decision that has
   not yet been formally written up as its own ADR.

The wider architecture document
(`docs/planning/forensic-db-architecture/sections/06-neo4j-graphiti-semantica.md`,
read in full) gives the fuller design context the wiring file only sketches:
Neo4j carries **two lanes** in one instance — Case KG (`group_id
"case:<id>:kg"`, written by Semantica seed-first + a mandatory **Graph Write
Adapter**, court-grade, no cloud LLM ever on evidence) and Agent
Cognition/Memory (`group_id "agent:*"`, written by Graphiti, operational,
never an exhibit). Semantica's seed phase is **deterministic FK projection
from Postgres, zero inference, zero LLM** (`entity.person`→`:Person`,
`timeline.event`→`:Event`, etc.); a second, optional "hybrid" phase lets
Semantica propose **hypothesis-only** structure (typed relations, pattern/
tactic edges) using a **local ≤4B model** (cloud LLM extraction is
hard-blocked on case content by the adapter's privacy guardrail) — every
hybrid write is `hypothesis=true, safe_for_legal_use=false`, review-gated.
All graph writes — Graphiti's and Semantica's — pass through one
`GraphWriteAdapter` chokepoint enforcing traceability, separability
(`writer` property distinguishes `semantica_seed`/`semantica_hybrid`/
`graphiti`/`adapter_manual`), reversibility (`write_batch_id`, rollback by
batch delete), idempotency (MERGE on deterministic `uid`), the privacy
guardrail, and HITL gating. Semantica's node embeddings flow to Milvus via
the same `vector_id` back-ref pattern. None of this adapter exists as code
yet — it is design only, same APPROVALS-gated status as the wiring module.

---

## 5. Positioning — who owns what

| Concern | Owner today | Notes |
|---|---|---|
| **Entities (people/devices/accounts) — canonical identity** | **PostgreSQL `entity.*`** (SSOT) | Neo4j/Semantica/Graphiti are all projections; `entity.person`/`device`/`account`/`identifier` are the source of truth |
| **Entities — graph node representation, resolution/merge** | **Semantica `kg.EntityResolver`** (proposed, seed-first) | Deterministic seed from PG FKs; fuzzy/semantic merge is a Phase-2 hypothesis, HITL-gated |
| **Entities — agent-conversation-scoped memory** | **agno `LearningMachine.entity_memory`** (`EntityMemoryConfig(mode=LearningMode.PROPOSE)` in `server/agents/providers.py:253`) | Operational/session-scoped, HITL via `PROPOSE` mode; not the case-evidence entity graph |
| **Temporal facts / bitemporal writes to Neo4j** | **Graphiti** (ADR-0014, sole writer) | `valid_at/invalid_at` + `created_at/expired_at`; Semantica never writes Neo4j directly — proposes via the (design-only) Graph Write Adapter |
| **Reference/document retrieval (RAG over static knowledge)** | **agno `Knowledge`** | Passed into `LearningMachine` and agent factories (`server/agents/factory.py`, `providers.py`); the platform's existing RAG surface — distinct from both Semantica's `vector_store`/`context.AgentMemory` and Graphiti |
| **Session context, user profile/memory, learned knowledge** | **agno `LearningMachine`** (`UserProfileConfig`, `UserMemoryConfig`, `SessionContextConfig`, `LearnedKnowledgeConfig` — all in `server/agents/providers.py:build_learning()`) | The platform's actual in-use agent-memory system; `LearnedKnowledgeConfig` is also `PROPOSE`-mode/HITL, namespaced `"platform"` |
| **Cross-source conflict detection, dedup, decision-provenance** | **Semantica `conflicts/` + `deduplication/` + `context.decision_*`** (net-new, unwired) | Explicitly the reason Semantica is being evaluated at all — "lanes the current custody→parse→normalize→Graphiti path does not cover" (wiring docstring) |
| **Vector similarity search over evidence** | **OUR Milvus (`forensic_records/findings/patterns`)**, dim-locked bge-m3/1024 | Semantica's `vector_store.milvus_store` targets these same collections — no second index — per `semantica_wiring.vector_store_config()` |
| **Behavioral-pattern / detection-pattern ontology** | **PostgreSQL `analysis.behavior_category`/`detection_pattern`/`pattern_lexicon`** (153/512/51 rows) | Seeds Semantica's `kg`/`ontology` modules via `extend_not_replace=True` — Semantica extends this, does not own or replace it |
| **Provenance / lineage record** | **PostgreSQL `provenance.provenance`** (SSOT) + Semantica's `provenance/` module as the **design model** (PROV-O) the graph's own provenance strategy is patterned on | Semantica's W3C PROV-O implementation (`prov:Entity/Activity/Agent/wasDerivedFrom`) is cited by name in the forensic-DB architecture doc as the governance pattern to mirror, even though PG remains the actual system of record |
| **RDF/OWL/ontology authoring & reasoning** | **Semantica `ontology/` + `reasoning/` + `triplet_store/`** (unwired) | No platform equivalent exists; would be net-new capability if adopted |

**Where Semantica concretely fits in the upcoming pipeline** (RESTART-0001
raw-ingest → normalize → entity/detection → analysis, per memory index):
Semantica's `ingest/`+`parse/`+`normalize/`+`split/` modules overlap the
platform's own `server/tools/` parser registry and are **not** the intended
integration point (the platform has its own ingestion path; re-parsing
through Semantica would be redundant, especially given the privacy guardrail
against cloud LLMs touching raw evidence). The realistic seam is
**downstream of normalize, at entity/detection**: after entities are resolved
in Postgres and detection-pattern findings exist in `analysis.*`, Semantica's
`kg.GraphBuilder` (seeded deterministically from those PG rows) plus
`conflicts/` and `deduplication/` run as an **analysis-time enrichment pass**
that proposes (never asserts) cross-source contradictions, duplicate-entity
merges, and hypothesis edges — all landing back through the not-yet-built
`GraphWriteAdapter` with Graphiti as the actual Neo4j writer. Nothing in this
seam is deployed; it is fully design/local per `semantica_wiring.py`'s own
`deploy` field.

---

## Coverage

Paths read (full or substantial-partial) for this deep-dive:

- `server/vendored/semantica/pyproject.toml` (full)
- `server/vendored/semantica/semantica/__init__.py` (head + version string)
- `server/vendored/semantica/mkdocs.yml` (full — nav structure, reveals missing guide pages)
- `server/vendored/semantica/docs/reference/*.md` — all 24 reference docs read (ingest, kg full; semantic_extract, provenance, change_management, context, seed, embeddings, vector_store, graph_store, triplet_store, export, conflicts, deduplication, ontology, reasoning, normalize, parse, split, core, evals, utils, visualization — overview sections)
- `server/vendored/semantica/semantica/*/` — directory listings for ingest, semantic_extract, context, kg, provenance, change_management, seed, embeddings, vector_store, graph_store, triplet_store, export (entry-point/class inventory)
- `server/vendored/semantica/semantica/semantic_extract/named_entity_recognizer.py` (docstring — NER method list)
- `server/vendored/semantica/semantica/semantic_extract/llm_extraction.py` (docstring — LLM provider list)
- `server/vendored/semantica/semantica/context/agent_memory.py` (docstring — AgentMemory design)
- `server/vendored/semantica/semantica/context/entity_linker.py` (docstring — entity-linking design)
- `server/vendored/semantica/semantica/server.py`, `worker.py`, `cli.py` (entry-point headers)
- `server/vendored/semantica/benchmarks/benchmarks.md` (full)
- `server/vendored/semantica/benchmarks/` (full file listing — all category dirs)
- `server/vendored/semantica/tests/` (directory listing — 179 files, 24 module dirs + cookbook/integration)
- `server/analysis/semantica_wiring.py` (full — read completely per task instructions)
- `tests/test_semantica_wiring.py` (full — the platform's own live-tested contract over the wiring module)
- root `pyproject.toml` (`[tool.pytest.ini_options]` — vendored-exclusion rationale)
- `server/AGENTS.md` (vendored/ policy line)
- `server/agents/providers.py` (`build_learning()` — full `LearningMachine` config, entity_memory/learned_knowledge modes)
- `docs/planning/forensic-db-architecture/sections/06-neo4j-graphiti-semantica.md` (full — the authoritative design doc for graph-layer positioning)
- `docs/adr/` — grepped for "semantica" mentions (0003, 0007, 0014, 0018, 0025, 0033); confirmed no dedicated Semantica-placement ADR exists at `0035` or elsewhere
- `docker/graphiti/config.yaml:38` (`group_id: "platform"` — cross-checked against wiring's asserted `"casebible"`)
- `docs/EVIDENCE_MERGE_MAP.md` — grepped, no direct Semantica mentions found
