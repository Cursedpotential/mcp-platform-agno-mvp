# Modular Architecture & LlamaIndex Property Graph Orchestration (v6)

## 1. Executive Summary: The LlamaIndex Pivot
You are absolutely correct. Hand-rolling a custom router to perfectly synchronize DuckDB (document store), LanceDB (vector store), and Neo4j (graph store) for hybrid search is reinventing the wheel.

**The Perfect Solution: LlamaIndex Property Graph (`PropertyGraphIndex`)**
LlamaIndex's Property Graph architecture was built *exactly* for this. It is the ultimate modular orchestrator. It natively handles the complex hybrid search (Vector + Graph) across multiple databases out of the box, while allowing us to plug in our own custom local NER models and document parsers.

We get the orchestration of a framework (like MS GraphRAG), but with 100% modularity and native support for our exact 5-tier database stack.

---

## 2. Component Responsibility Matrix (The LlamaIndex Ecosystem)

### Tier 1: Ingestion & Document Store (DuckDB)
*Goal: Convert raw files and store the raw text.*
- **LlamaIndex Readers**: We use native LlamaIndex reader plugins for our modular ingestion:
  - `DoclingReader` / `UnstructuredReader` (Local, default)
  - `LlamaParse` (Cloud, for extreme complexity PDFs)
  - `TextractReader` (Cloud, strictly routed for screenshots/images)
- **Document Store (DuckDB)**: LlamaIndex natively supports using SQL databases as a `DocumentStore`. The raw parsed text is saved to DuckDB.

### Tier 2: Custom Entity Extraction (The NER Pipeline)
*Goal: Extract entities without expensive LLM calls.*
LlamaIndex allows us to build custom `BaseExtractor` classes. LlamaIndex handles the text chunking, and passes the chunks to our local models:
- **GLiNER2 Extractor**: Local Python. Extracts semantic entities (`person`, `location`, `custody_event`).
- **Recognizers-Text Extractor**: Local Node.js. Extracts structured data (`dates`, `currency`, `phone_numbers`).
- **Watson / Google Maps Extractors**: Opt-in cloud extractors for emotion and geocoding validation.

### Tier 3: Validation & Provenance (Semantica)
*Goal: Ensure no conflicting data enters the graph.*
- We insert **Semantica** as a custom LlamaIndex *Node Postprocessor*. Before LlamaIndex commits the extracted entities to the database, Semantica checks them against existing facts. If a conflict occurs, it halts for human review (Rule #8). Once validated, it attaches W3C PROV-O provenance.

### Tier 4 & 5: The Graph & Vector Stores (Neo4j + LanceDB)
*Goal: Store the validated data for hybrid retrieval.*
LlamaIndex handles the dual-write automatically:
- **Vector Store (LanceDB)**: LlamaIndex's `LanceDBVectorStore` automatically embeds the chunks (via local Ollama) and saves the vectors.
- **Graph Store (Neo4j DB #2)**: LlamaIndex's `Neo4jPropertyGraphStore` automatically saves the validated entities and relationships to our Semantica database.
- *(Sidecar)* **Temporal Graph (Neo4j DB #1)**: Graphiti continues to run alongside LlamaIndex, tracking the episodic memory of the application.

---

## 3. The End-to-End Workflow (Orchestrated by LlamaIndex)

### Step 1: Ingest & Parse
1. User uploads a file (e.g., `screenshot.png`).
2. The application checks the file type and selects the correct LlamaIndex Reader (e.g., `TextractReader`).
3. The Reader extracts the Markdown text.
4. LlamaIndex saves the raw Markdown to the **DuckDB Document Store**.

### Step 2: Extract & Validate
1. LlamaIndex chunks the text and passes the chunks through our custom `Extractor` pipeline.
2. **GLiNER2** and **Recognizers-Text** process the chunks locally, returning LlamaIndex `EntityNode` objects.
3. The pipeline reaches the **Semantica Node Postprocessor**. Semantica validates the entities against Neo4j DB #2.
4. If there's a conflict (e.g., Document says "School", DB says "Police Station"), the pipeline pauses for Human-in-the-Loop resolution (Rule #8).

### Step 3: Automated Storage (The Hybrid Commit)
1. Once validated, LlamaIndex takes over the database orchestration.
2. It sends the embeddings to **LanceDB**.
3. It sends the graph nodes and edges to **Neo4j DB #2**.
4. (Graphiti simultaneously logs the temporal episode to **Neo4j DB #1**).

### Step 4: Hybrid Retrieval & Q&A
1. The user asks a complex question to the Agno Agent.
2. The Agent uses the `PropertyGraphIndex.as_retriever()` tool.
3. **The Magic:** LlamaIndex automatically performs a hybrid search. It queries **LanceDB** for vector similarity AND traverses **Neo4j** for graph relationships simultaneously, merging the results context perfectly.
4. The LLM synthesizes the final answer with exact citations.

---

## 4. Why LlamaIndex Property Graph is the Ultimate Solution
1. **Solves the Routing Problem:** You don't have to write thousands of lines of code to synchronize DuckDB, LanceDB, and Neo4j. LlamaIndex's `StorageContext` manages all three natively.
2. **100% Interchangeable:** Want to swap LanceDB for Qdrant? Change one line of code: `vector_store = LanceDBVectorStore()` -> `vector_store = QdrantVectorStore()`. The rest of the pipeline stays identical.
3. **Pluggable NER:** LlamaIndex's extractor architecture means we can easily plug in GLiNER2, Microsoft Recognizers-Text, and IBM Watson as simple Python classes. LlamaIndex handles feeding them the text chunks.
4. **Agno Friendly:** Agno agents can easily consume LlamaIndex retrievers as standard tools.

---

# Plan Feedback

I've reviewed this plan and have 1 piece of feedback:

## 1. General feedback about the plan
> OK so redo the detailed I proposal and plan making sure that Symantec and Duckdb and Graffiti remain first class parts of this system as well as I didn't see anything in there for chain of custody and evidence handling processes the SHA 256 hashing and things like that Also ensuring that we're using UUID 7 on everything and linking all of the bits and pieces all of the summaries all of the sharding all the fragments all everything has to be linked So take that in a close consideration and then rewrite it using the Lama index property graph and I think we'll be there

---
