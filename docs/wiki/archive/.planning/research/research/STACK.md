---
title: GraphRAG Technology Stack
version: 2.0.0
created: 2026-02-28 15:00
author: thinking@opencode
project: MCP_Tool_Platform
status: final
---

# Technology Stack: GraphRAG as Abstraction Layer

**Project:** MCP_Tool_Platform
**Researched:** 2026-02-28
**Confidence:** HIGH (versions verified via Context7, PyPI, official docs)

## The Three-Package Strategy

"GraphRAG" is not one thing. Three separate projects serve three distinct roles:

| Package | PyPI Name | Version | License | Python | Role in Platform |
|---|---|---|---|---|---|
| **Neo4j GraphRAG Python** | `neo4j-graphrag-python` | 1.5.0 | Apache 2.0 | >=3.10 | **Primary abstraction layer** — real-time NER, graph writes, query routing |
| **Microsoft GraphRAG** | `graphrag` | 3.0.5 (Feb 27, 2026) | MIT | >=3.11, <3.14 | **Batch enrichment engine** — community detection, summarization, global search |
| **Graphiti** | `graphiti-core` | 0.5.x | Apache 2.0 | >=3.10 | **Temporal memory** — episodic nodes, temporal edges, contradiction detection |

**All three run on the Python bridge VPS.** The TypeScript server calls them via the existing Python bridge HTTP API.

## Recommended Stack

### Core GraphRAG Packages

| Technology | Version | Purpose | Why This One |
|---|---|---|---|
| `neo4j-graphrag-python` | 1.5.0 | Real-time entity extraction + query routing | **Native Neo4j.** SimpleKGPipeline does NER-to-graph in one call. ToolsRetriever lets the LLM pick the right retriever. Replaces most custom TrinityRouter logic. |
| `graphrag` | 3.0.5 | Batch community detection + global summarization | **Only package with Leiden community detection.** Already referenced in STORAGE_ARCHITECTURE.md line 614 for Pass 2 enrichment. |
| `graphiti-core` | 0.5.x | Temporal edges + contradiction detection | **Already ~40% integrated.** Neither GraphRAG package handles temporal awareness. Irreplaceable for the forensic use case. |

### LLM / Embedding Infrastructure (UNCHANGED)

| Technology | Purpose | GraphRAG Integration |
|---|---|---|
| **Ollama** (GPU VPS) | Local LLM inference + embeddings | Both packages support via LiteLLM. Zero API cost. |
| **LiteLLM** (bundled) | Provider abstraction | MS GraphRAG uses natively since v2.6.0. Neo4j GraphRAG uses its own LLM interface but supports OpenAI-compatible APIs (i.e., Ollama). |
| **nomic-embed-text** v1.5 | 768-dim text embeddings | Already deployed. Used by existing LanceDB pipeline. Both packages can use it. |
| **qwen2.5:14b** | Entity extraction LLM | Best structured-JSON reliability vs size for Ollama. Recommended for both SimpleKGPipeline and MS GraphRAG extraction. |
| **OpenRouter** (fallback) | Cloud LLM when Ollama fails | Gemini Flash cheapest for extraction. Use when Ollama produces malformed JSON. |

### Storage Backends (UNCHANGED — GraphRAG Uses These)

| Technology | Version | Purpose | GraphRAG Relationship |
|---|---|---|---|
| **DuckDB** | 1.1.x | Master clock, ETL, chain of custody | **Upstream of GraphRAG.** First touch happens here, THEN documents flow to GraphRAG pipelines. |
| **LanceDB** | 0.15.x | Vector embeddings + binary storage | **MS GraphRAG's default vector store.** Zero additional config — point it at existing LanceDB path. |
| **Neo4j** | 5.x | Dual graph databases | **Neo4j GraphRAG writes here natively.** MS GraphRAG needs a parquet-to-Cypher import step. |
| **MySQL** | 8.x | Application metadata (Drizzle) | **Outside GraphRAG scope entirely.** No change. |

### Supporting Libraries

| Library | Version | Purpose | Notes |
|---|---|---|---|
| `spacy` + `en_core_web_md` | 3.7+ | NLP extraction (MS GraphRAG `fast` method) | Already installed on Python bridge. 92MB model. |
| `nltk` | 3.9+ | NLP extraction (MS GraphRAG `fast` default) | Needs `averaged_perceptron_tagger_eng` download. |
| `neo4j` (Python driver) | 5.x | Neo4j connection | Required by both neo4j-graphrag-python and Graphiti. Single driver, no conflict. |
| `pydantic` | 2.x | Config + data models | Both packages use Pydantic. Compatible. |
| `networkx` | 3.x | Graph algorithms | MS GraphRAG uses for internal graph ops. |
| `graspologic` | 3.x | Leiden algorithm | MS GraphRAG dependency for community detection. |

## Dependency Compatibility

### Python Version Constraint
```
graphrag:              >=3.11, <3.14
neo4j-graphrag-python: >=3.10
graphiti-core:         >=3.10
─────────────────────────────────────
INTERSECTION:          Python 3.12 or 3.13 ← USE THIS
```

### LanceDB Version Risk
- MS GraphRAG bundles LanceDB as default vector store
- Existing platform uses LanceDB directly
- **Risk:** Version pinning conflicts
- **Mitigation:** Check `graphrag` dependency pins. If conflict, isolate in venv or pin compatible version. Most likely fine — both use lancedb>=0.10.

### Neo4j Driver Compatibility
- `neo4j-graphrag-python` depends on `neo4j` driver >=5.x
- `graphiti-core` depends on `neo4j` driver >=5.x
- **No conflict.** Same driver.

### spaCy Model Sharing
- MS GraphRAG `fast` method uses `en_core_web_md`
- Existing Python bridge already uses spaCy for NER
- **No conflict.** Same model, already installed.

## Alternatives Considered

| Category | Recommended | Alternative | Why Not Alternative |
|---|---|---|---|
| Real-time NER → Neo4j | Neo4j GraphRAG SimpleKGPipeline | Custom spaCy + manual Cypher writes | SimpleKGPipeline does extraction + graph writes in one call. Custom = 200+ lines of glue code. |
| Community detection | MS GraphRAG Leiden pipeline | Custom NetworkX Leiden | MS GraphRAG handles extraction→communities→summarization end-to-end. Custom = rebuild the whole pipeline. |
| Query routing | Neo4j GraphRAG ToolsRetriever | Custom TrinityRouter query logic | ToolsRetriever lets the LLM decide which retriever fits the query. Replaces hand-coded routing rules with AI-driven routing. |
| Temporal memory | Graphiti | MS GraphRAG | MS GraphRAG has **zero** temporal awareness. No valid_at/invalid_at. No episodic memory. Graphiti is the only option. |
| Vector RAG | LanceDB (default in both) | Qdrant, Chroma, Pinecone | LanceDB already deployed AND is MS GraphRAG's default. Zero additional infra. |
| Batch pipeline | MS GraphRAG | LlamaIndex Knowledge Graph | MS GraphRAG's community detection via Leiden is unique. LlamaIndex has graph RAG but no communities, no global search. |

## Installation

```bash
# On Python bridge VPS — Python 3.12

# Core packages
pip install graphrag==3.0.5
pip install neo4j-graphrag-python==1.5.0
pip install graphiti-core  # already partially installed

# NLP models for MS GraphRAG fast indexing
python -m spacy download en_core_web_md
python -c "import nltk; nltk.download('averaged_perceptron_tagger_eng')"

# Verify all three
python -c "from graphrag.api import build_index, local_search; print('MS GraphRAG: OK')"
python -c "from neo4j_graphrag.experimental.pipeline.kg_builder import SimpleKGPipeline; print('Neo4j GraphRAG: OK')"
python -c "from graphiti_core import Graphiti; print('Graphiti: OK')"
```

## Configuration: MS GraphRAG (settings.yaml)

```yaml
llm:
  type: openai_chat
  model: ollama/qwen2.5:14b
  api_base: http://gpu-vps:11434

embeddings:
  llm:
    type: openai_embedding
    model: ollama/nomic-embed-text
    api_base: http://gpu-vps:11434

chunks:
  size: 1200
  overlap: 100

storage:
  type: file
  base_dir: ./data/graphrag/output

vector_store:
  type: lancedb
  db_uri: ./data/lancedb/multimodal_vault  # REUSE existing LanceDB

entity_extraction:
  max_gleanings: 1  # Cost control

claim_extraction:
  enabled: true  # Forensic evidence: extract behavioral claims
  description: "Extract claims about behavior, promises, threats, contradictions, and custody-relevant statements"

community_reports:
  max_length: 2000
```

## Configuration: Neo4j GraphRAG Python

```python
from neo4j import GraphDatabase
from neo4j_graphrag.experimental.pipeline.kg_builder import SimpleKGPipeline
from neo4j_graphrag.retrievers import VectorRetriever, Text2CypherRetriever

# Connect to existing semantic_facts database
driver = GraphDatabase.driver(
    "bolt://neo4j-vps:7687",
    auth=("neo4j", "password"),
    database="semantic_facts"
)

# SimpleKGPipeline — replaces custom NER + graph writes
pipeline = SimpleKGPipeline(
    llm=ollama_llm,
    driver=driver,
    embedder=ollama_embedder,
    entities=["Person", "Location", "Date", "Amount", "Event", "Claim"],
    relations=["SENT_TO", "MENTIONED", "OCCURRED_AT", "CONTRADICTS", "PROMISED", "THREATENED"],
    on_error="IGNORE",
)

# Retrievers — replace custom query routing
vector_retriever = VectorRetriever(driver=driver, index_name="evidence_vectors")
cypher_retriever = Text2CypherRetriever(driver=driver, llm=ollama_llm)
```

## Cost Impact on $24/month Budget

| Component | Monthly Cost | Notes |
|---|---|---|
| MS GraphRAG `fast` indexing (NLP) | **$0** | CPU-only, Python bridge VPS |
| MS GraphRAG `standard` via Ollama | **$0** | GPU VPS already provisioned |
| MS GraphRAG `standard` via OpenRouter | **$2-10** | Gemini Flash fallback. Only if Ollama JSON fails. |
| Neo4j GraphRAG Python | **$0** | Uses existing Neo4j + Ollama |
| Graphiti | **$0** | Uses existing Neo4j + Ollama |
| LanceDB | **$0** | Embedded, already deployed |
| **Total additional** | **$0-10/month** | **Well within $24/month budget** |

## Sources

- Context7: `/microsoft/graphrag` — architecture, pipeline, LiteLLM, BYOG, config
- Context7: `/websites/microsoft_github_io_graphrag` — settings.yaml, models, NLP methods, vector stores
- Context7: `/neo4j/neo4j-graphrag-python` — SimpleKGPipeline, ToolsRetriever, VectorRetriever
- PyPI: graphrag 3.0.5 (released Feb 27, 2026)
- PyPI: neo4j-graphrag-python 1.5.0
- Existing codebase: STORAGE_ARCHITECTURE.md, systemRouter.ts, graphiti-client.ts
