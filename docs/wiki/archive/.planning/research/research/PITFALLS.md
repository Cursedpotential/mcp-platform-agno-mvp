---
title: GraphRAG Integration Pitfalls
version: 2.0.0
created: 2026-02-28 15:45
author: thinking@opencode
project: MCP_Tool_Platform
status: final
---

# Domain Pitfalls: GraphRAG Integration

**Domain:** Evidence management platform — integrating three GraphRAG packages
**Researched:** 2026-02-28
**Confidence:** MEDIUM (cost estimates from docs + community reports; integration risks are novel)

## Critical Pitfalls

Mistakes that cause rewrites, budget blowouts, or architectural dead ends.

### Pitfall 1: Confusing the Three "GraphRAG" Projects

**What goes wrong:** Treating Microsoft GraphRAG, Neo4j GraphRAG Python, and Graphiti as interchangeable. Building on the wrong package for the wrong purpose. Attempting to use MS GraphRAG for real-time NER (it's batch-only). Attempting to use Neo4j GraphRAG for community detection (it has none).

**Why it happens:** All three have "graph" and "RAG" in the name. Blog posts conflate them. Even official docs don't clearly differentiate.

**Consequences:** Weeks of integration work on the wrong package. Architectural backtracking. "Why can't MS GraphRAG write to Neo4j?" frustration.

**Prevention:**
| Package | PyPI | Use For | DO NOT Use For |
|---|---|---|---|
| `graphrag` | Microsoft | Batch community detection, global search | Real-time NER, Neo4j writes |
| `neo4j-graphrag-python` | Neo4j | Real-time NER, query routing, Neo4j writes | Community detection, temporal memory |
| `graphiti-core` | Zep | Temporal edges, contradiction detection | Semantic facts, community detection |

**Detection:** If you're writing custom code to make a package do something it wasn't designed for, you're probably using the wrong package.

---

### Pitfall 2: LLM Cost Explosion from MS GraphRAG Standard Indexing

**What goes wrong:** Running MS GraphRAG with `standard` indexing method on every document. Entity extraction via LLM consumes ~75% of total pipeline cost. On a corpus of 10,000 messages, this means 10,000+ LLM calls just for extraction, plus calls for community summarization.

**Why it happens:** `standard` is the default. It produces higher-quality graphs. The temptation is to use it for everything.

**Consequences:** On Ollama (local GPU): GPU bottleneck, hours of processing time. On OpenRouter: $50-200+ for a single batch run on a large corpus. Blows the $24/month budget instantly.

**Prevention:**
1. **Default to `fast` indexing** (NLP-based, uses spaCy/NLTK). Zero LLM cost. Noisier graphs but adequate for initial community detection.
2. **Use `standard` selectively** — only for high-value documents where extraction quality matters (e.g., key legal filings, pivotal messages).
3. **Use BYOG** — if SimpleKGPipeline already extracted entities in real-time, feed those to MS GraphRAG via BYOG. Skip the extraction phase entirely, run only community detection.
4. **Monitor costs** — track LLM calls per batch run. Set hard limits.

**Detection:** Batch run taking hours on Ollama. OpenRouter bills spiking. These are signs you're over-indexing.

**Confidence:** HIGH — MS GraphRAG docs explicitly state "75% of the cost of indexing is in entity/relationship extraction."

---

### Pitfall 3: Dual Entity Extraction Creating Duplicate Graphs

**What goes wrong:** Running BOTH SimpleKGPipeline (real-time) AND MS GraphRAG entity extraction (batch) against the same documents, both writing to Neo4j/semantic_facts. Result: duplicate entity nodes with different schemas, conflicting relationship types, inconsistent graph.

**Why it happens:** Each package has its own entity extraction. Natural instinct is to run both for "better coverage."

**Consequences:** Graph queries return duplicates. Community detection runs on a polluted graph. Entity resolution becomes a nightmare. Custom dedup code needed.

**Prevention:**
1. **SimpleKGPipeline for real-time extraction** → writes to semantic_facts
2. **MS GraphRAG uses BYOG** — imports SimpleKGPipeline's entities from Neo4j, runs ONLY community detection + summarization
3. **Never run MS GraphRAG entity extraction against documents already processed by SimpleKGPipeline**
4. If you must use MS GraphRAG extraction (e.g., for `fast` NLP method), write to a separate staging area, not directly to semantic_facts

**Detection:** Query for entities, see duplicates with different property schemas. Count of entity nodes is 2x expected.

**Confidence:** HIGH — this is a logical consequence of running two extraction pipelines against the same data.

---

### Pitfall 4: MS GraphRAG Parquet Output ≠ Neo4j

**What goes wrong:** Assuming MS GraphRAG writes to Neo4j. It doesn't. MS GraphRAG outputs parquet files (entities.parquet, relationships.parquet, communities.parquet, community_reports.parquet). Getting this data INTO Neo4j requires a custom import step.

**Why it happens:** The name "GraphRAG" implies graph database integration. The community Neo4j import notebook exists but is easy to miss.

**Consequences:** Batch enrichment runs successfully but community data is trapped in parquet files. Can't query communities via Neo4j. Can't use ToolsRetriever to access community data. Global search works (MS GraphRAG has its own search) but data doesn't flow to the rest of the system.

**Prevention:**
1. **Build the parquet-to-Neo4j import script in Phase 2** — not an afterthought
2. Use Cypher LOAD CSV or Python neo4j driver to import:
   - entities.parquet → `:Entity` nodes
   - relationships.parquet → edges
   - communities.parquet → `:Community` nodes with `:BELONGS_TO` edges
   - community_reports.parquet → `.summary` property on Community nodes
3. **Test the import pipeline with 10 documents before scaling**

**Detection:** Batch enrichment completes, parquet files exist, but `MATCH (c:Community) RETURN count(c)` returns 0 in Neo4j.

**Confidence:** HIGH — verified via Context7. MS GraphRAG storage options are: file (parquet), Azure Blob, CosmosDB, Memory. No native Neo4j.

---

### Pitfall 5: Ollama Structured JSON Output Failures

**What goes wrong:** GraphRAG entity extraction requires LLMs to return structured JSON (entity lists, relationship tuples, etc.). Ollama models — especially smaller ones — frequently produce malformed JSON: missing quotes, trailing commas, incomplete objects, mixing JSON with natural language.

**Why it happens:** Local models are less instruction-following than cloud APIs. JSON mode support varies by model. Ollama's JSON enforcement is best-effort.

**Consequences:** Extraction fails silently or produces garbage entities. Pipeline appears to run but graph quality is terrible. Debugging is painful — need to inspect raw LLM responses.

**Prevention:**
1. **Use qwen2.5:14b or larger** — best structured output reliability among Ollama models for the size
2. **Use `on_error="IGNORE"` in SimpleKGPipeline** — skip malformed responses instead of crashing
3. **Set `max_gleanings: 1`** in MS GraphRAG config — limits extraction retries (cost control + reduces failure surface)
4. **Have OpenRouter fallback** — if Ollama reliability drops below acceptable threshold, switch extraction to Gemini Flash via OpenRouter ($2-5/month for moderate volume)
5. **Test with 20 representative documents first** — before committing to full pipeline, verify extraction quality

**Detection:** Entity counts suspiciously low. Entity names contain JSON artifacts (curly braces, quotes). Relationships don't make semantic sense.

**Confidence:** HIGH — MS GraphRAG docs explicitly warn: "We frequently see issues with malformed responses (especially JSON) when using Ollama."

---

## Moderate Pitfalls

Mistakes that cause delays, tech debt, or degraded quality.

### Pitfall 6: Running Graphiti and SimpleKGPipeline on the Same Text

**What goes wrong:** Both packages extract entities. If both run on every incoming message, you get entity nodes in BOTH semantic_facts (SimpleKGPipeline) AND temporal_memory (Graphiti). Queries need to check both databases. Entity resolution across databases is unsolved.

**Why it happens:** Both packages are designed to process text and extract entities. Running both seems like "more coverage."

**Prevention:**
- **Define clear ownership:** SimpleKGPipeline → semantic_facts (who, what, where, relationships). Graphiti → temporal_memory (when things changed, contradictions over time).
- **Consider sequential flow:** SimpleKGPipeline extracts entities first, then Graphiti gets the entities + temporal context to build temporal edges. This avoids duplicate extraction.
- **Phase 4 boundary definition** is specifically about resolving this overlap.

**Confidence:** MEDIUM — the overlap is real but the severity depends on implementation. Could be minor (different entity schemas, no conflict) or major (duplicate entities causing query confusion).

---

### Pitfall 7: LanceDB Version Pinning Conflict

**What goes wrong:** MS GraphRAG depends on LanceDB internally (it's the default vector store). The existing platform also depends on LanceDB. If they pin different versions, pip install fails or one package breaks.

**Prevention:**
1. Check version compatibility before installing: `pip install graphrag --dry-run` and inspect lancedb version
2. If conflict exists, consider:
   - Virtual environment isolation (separate venv for MS GraphRAG)
   - Pinning to the intersection version
   - Using MS GraphRAG's `memory` storage type instead of LanceDB (but loses persistence)

**Confidence:** MEDIUM — depends on specific version pins. Likely compatible (both use lancedb>=0.10) but worth checking.

---

### Pitfall 8: Community Detection on Small Corpus

**What goes wrong:** Running MS GraphRAG community detection on <100 documents. Leiden algorithm finds "communities" but they're meaningless — single-entity communities or everything in one giant community. Results don't add analytical value.

**Why it happens:** Eagerness to see community detection working. Running batch pipeline too early.

**Prevention:**
1. **Don't run batch enrichment until you have 100+ documents per case** — community detection needs volume
2. **Start with `fast` indexing** — lower quality graphs but faster iteration to see if communities are meaningful
3. **Review community reports qualitatively** before feeding into retrieval — bad communities = misleading search results

**Detection:** Communities of size 1 or 2. Single community containing 90%+ of entities. Community reports that are generic/unhelpful.

**Confidence:** MEDIUM — this is general knowledge about community detection algorithms, not GraphRAG-specific.

---

### Pitfall 9: Overcomplicating the Python Bridge API

**What goes wrong:** Building a complex RPC/gRPC/message queue system between TypeScript server and Python bridge. Adding serialization layers, retry logic, queue management.

**Why it happens:** Enterprise habits. "What if the Python bridge goes down?" engineering.

**Prevention:**
1. **Start with simple HTTP** — FastAPI endpoint, JSON request/response. The Python bridge is on the same VPS or local network.
2. **Keep the API surface small:**
   - `POST /ingest` — run SimpleKGPipeline + Graphiti on document
   - `POST /search` — run ToolsRetriever with query
   - `POST /batch-enrich` — trigger MS GraphRAG pipeline
   - `GET /health` — check all three packages
3. **Add complexity only when you hit actual problems** — not preemptively

**Confidence:** HIGH — this is a solo-operator project. KISS principle applies.

---

### Pitfall 10: Forgetting MS GraphRAG Search Requires Its Own Index

**What goes wrong:** Running MS GraphRAG `local_search()` or `global_search()` without first running `build_index()`. The search functions depend on MS GraphRAG's own index output (parquet files with community reports, entity embeddings, etc.).

**Why it happens:** Confusion between Neo4j GraphRAG's retrievers (which query Neo4j directly) and MS GraphRAG's search (which queries its own parquet-based index).

**Prevention:**
1. **MS GraphRAG search = MS GraphRAG index.** They're a pair. Can't use one without the other.
2. **Neo4j GraphRAG retrievers work independently** — they query Neo4j directly, no special index needed.
3. **Flow:** build_index() creates parquet files → local_search()/global_search()/drift_search() query those files.

**Confidence:** HIGH — verified via Context7. MS GraphRAG search functions require the index output.

---

## Minor Pitfalls

Mistakes that cause annoyance but are fixable.

### Pitfall 11: MS GraphRAG CLI vs Python API Confusion

**What goes wrong:** Following tutorials that use `graphrag init` and `graphrag index` CLI commands. These work for standalone use but don't integrate with the Python bridge architecture.

**Prevention:** Use the **Python API exclusively**:
```python
from graphrag.api import build_index, local_search, global_search, drift_search
```
The CLI is for exploration/testing. Production integration uses the API.

**Confidence:** HIGH — verified via Context7.

---

### Pitfall 12: SimpleKGPipeline Default Schema Mismatch

**What goes wrong:** SimpleKGPipeline creates nodes with its own default label/property schema. If Semantica (existing Neo4j manager) expects different labels or properties, queries break.

**Prevention:**
1. **Specify entity types explicitly** in SimpleKGPipeline constructor: `entities=["Person", "Location", ...]`
2. **Check Semantica's expected schema** before configuring SimpleKGPipeline
3. **Test with a few documents** and inspect Neo4j nodes before scaling

**Confidence:** MEDIUM — depends on Semantica's actual schema expectations. Need Phase 1 empirical testing.

---

### Pitfall 13: Forgetting to Download NLTK Data

**What goes wrong:** MS GraphRAG `fast` indexing method fails with cryptic NLTK error because `averaged_perceptron_tagger_eng` dataset isn't downloaded.

**Prevention:**
```python
import nltk
nltk.download('averaged_perceptron_tagger_eng')
```
Add to setup script. One-time download, ~2MB.

**Confidence:** HIGH — verified via Context7 documentation.

---

### Pitfall 14: Entity Resolution Is NOT Included in MS GraphRAG

**Severity:** HIGH
**Confidence:** HIGH — confirmed via Bratanič's Medium article and Neo4j blog

**What goes wrong:** MS GraphRAG extracts entities per-document. "Matt S.", "Matthew", "Matt Silverstein", and "Dad" may all refer to the same person but appear as 4 separate `__Entity__` nodes. Without entity resolution, community detection treats them as distinct people, fragmenting the graph and producing meaningless communities.

**Why it matters for custody domain:** Names are inconsistent across 8 years of messages. The same person appears as first name, nickname, "Mom"/"Dad", full legal name, etc. Without resolution, the graph is useless.

**Prevention (per Bratanič's approach):**
1. Generate embeddings for all entity names
2. Build k-NN graph (k=10) on name embeddings
3. Run Weakly Connected Components (WCC) via Neo4j GDS to find candidate clusters
4. Filter by word distance (Levenshtein) to remove false positives
5. LLM evaluation for ambiguous cases ("Is 'Matt' the same person as 'Matthew S.'?")
6. Merge nodes with Cypher: redirect all relationships to canonical entity

**When to do it:** AFTER parquet import, BEFORE community detection makes sense. This is a Phase 2 task.

**Cost:** Low if using Ollama for embeddings + LLM evaluation. WCC is a GDS algorithm (free in Neo4j Community via GDS plugin).

---

## Phase-Specific Warnings

| Phase | Likely Pitfall | Severity | Mitigation |
|---|---|---|---|
| Phase 1: Neo4j GraphRAG integration | **Pitfall 12** — SimpleKGPipeline schema vs Semantica schema mismatch | Medium | Test with 5 documents, inspect Neo4j nodes before scaling |
| Phase 1: Neo4j GraphRAG integration | **Pitfall 5** — Ollama JSON failures with SimpleKGPipeline | High | Test qwen2.5:14b reliability. Have OpenRouter fallback ready. |
| Phase 2: MS GraphRAG batch pipeline | **Pitfall 2** — LLM cost explosion if using `standard` method | Critical | Default to `fast`. Use BYOG to skip extraction. |
| Phase 2: MS GraphRAG batch pipeline | **Pitfall 4** — Parquet output not reaching Neo4j | High | Build import script first, not last. |
| Phase 2: MS GraphRAG batch pipeline | **Pitfall 8** — Community detection on small corpus is meaningless | Medium | Wait for 100+ docs per case before running. |
| Phase 3: TrinityRouter simplification | **Pitfall 9** — Overcomplicating Python bridge API | Medium | Start with 4 FastAPI endpoints. Add complexity only when needed. |
| Phase 4: Graphiti boundary definition | **Pitfall 3** — Dual extraction creating duplicates | Critical | Define extraction ownership before implementing. Never run both on same text for same purpose. |
| Phase 4: Graphiti boundary definition | **Pitfall 6** — Graphiti + SimpleKGPipeline overlap | High | Sequential flow: SimpleKGPipeline first, Graphiti gets temporal context from its output. |
| Phase 2: MS GraphRAG batch pipeline | **Pitfall 14** — Entity resolution missing from MS GraphRAG | High | Build entity resolution as post-import step. k-NN + WCC + LLM eval per Bratanič. |

## GraphRAG-Specific vs General Pitfalls

**This file covers GraphRAG integration pitfalls only.** The prior PITFALLS.md (2026-02-25) covered general platform pitfalls:
- DuckDB concurrent write limitations
- Neo4j Community Edition single-database constraint (worked around with dual databases)
- Python bridge reliability
- Embedding dimension mismatches
- Chain of custody integrity

Those pitfalls remain valid. This file adds the GraphRAG-specific layer on top.

## Sources

- Context7: `/microsoft/graphrag` — cost warnings, Ollama JSON issues, pipeline phases, BYOG
- Context7: `/websites/microsoft_github_io_graphrag` — fast vs standard, vector store config, NLTK requirements
- Context7: `/neo4j/neo4j-graphrag-python` — SimpleKGPipeline on_error behavior, ToolsRetriever architecture
- MS GraphRAG docs: "75% of indexing cost is entity extraction" (index/methods page)
- MS GraphRAG docs: "frequently see issues with malformed responses (especially JSON) when using Ollama"
- Neo4j Blog: https://neo4j.com/blog/developer/microsoft-graphrag-neo4j/ — Integration guide, retriever setup
- Medium (Bratanič): https://medium.com/neo4j/implementing-from-local-to-global-graphrag-with-neo4j-and-between-lines-d6571220d7e0 — Entity resolution, cost analysis, Leiden with GDS
- graphrag.com: https://graphrag.com/appendices/research/2404.16130 — Original paper, pattern catalog
- Existing codebase: systemRouter.ts (389 lines), graphiti-client.ts (752 lines)
