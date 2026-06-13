# Modular Architecture & Neo4j-Native GraphRAG Plan (v5)

## 1. Executive Summary & Framework Pivot
You hit the nail on the head. **Microsoft GraphRAG is a monolithic, highly-opinionated black box.** It was built primarily to showcase OpenAI models, and trying to "override" its internal extraction steps with our local tools is hacky and fights the framework's design.

**The Solution:** We ditch Microsoft GraphRAG entirely. 

Instead, we use a completely modular, native approach that perfectly fits our pipeline: **Neo4j Graph Data Science (GDS) + the Neo4j GraphRAG Python Package**. 

Because we are already using Neo4j as our database, we don't need a heavy external framework to build the graph. We build the graph ourselves using our modular pipeline, run the community clustering natively inside the database, and use Neo4j's lightweight Python package purely for retrieval.

---

## 2. Why Ditch MS GraphRAG for Neo4j Native?
1. **No "Hacking" Required**: Instead of fighting a framework to use our local NER models (GLiNER2/Recognizers-Text), our models just write directly to the database via Semantica.
2. **Native Community Detection**: MS GraphRAG downloads your data to run the Leiden algorithm (clustering). **Neo4j GDS** runs the Leiden algorithm *natively inside the database* at lightning speed.
3. **True Modularity**: We decouple the *Indexer* (Our pipeline) from the *Clustering* (Neo4j GDS) from the *Retrieval* (Neo4j GraphRAG Package).
4. **Agno Integration**: It is infinitely easier to integrate Neo4j's lightweight retrieval package into our Agno agents than it is to wrap Microsoft's massive CLI-based pipeline.

---

## 3. Component Responsibility Matrix

### Phase A: Ingestion & Document AI (The "Readers")
- **Docling (IBM) / DocStrange / Unstructured.io**: Local, primary parsers.
- **Amazon Textract**: Cloud fallback for raw images / screenshots of messages.
- **LlamaParse**: Cloud fallback for complex/nested PDFs.

### Phase B: Modular Extraction (The "Extractors")
- **Microsoft Recognizers-Text**: Local Node.js. Extracts structured data (dates, times, currency, percentages, phone numbers).
- **GLiNER2 (Fastino)**: Local Python. Extracts semantic data (names, organizations, locations, custody events) at $0 cost.
- **IBM Watson NLU**: Cloud, opt-in. Extracts emotion scores (anger, fear, sadness) and complex semantic roles.
- **Google Cloud NL + Maps API**: Cloud, opt-in. Validates and geocodes specific address entities.

### Phase C: Validation & Provenance (The "Truth Filter")
- **Semantica (Hawksight-AI)**: Checks extracted entities against existing database facts. Prompts human review (Rule #8) if a conflict is found. Attaches W3C PROV-O provenance.

### Phase D: The 5-Tier Database Storage (The "Vaults")
1. **DuckDB (Tier 1)**: First-touch raw file and markdown storage.
2. **LanceDB (Tier 2)**: Vector storage for text chunks.
3. **Neo4j Dual-DB System (Tier 3 & 4)**:
   - **Neo4j DB #1 (Graphiti)**: Temporal memory graph (episodes, timelines).
   - **Neo4j DB #2 (Semantica)**: Absolute facts, validated entities, and relationships.
4. **MySQL (Tier 5)**: App state.

---

## 4. The End-to-End Workflow (The Neo4j-Native Data Lifecycle)

### Step 1: Raw Ingest & Parse
1. User uploads a file. **DuckDB** records metadata and the blob pointer.
2. The **Document Router** sends the file to the right parser (e.g., Textract for screenshots, Docling for PDFs).
3. The clean Markdown chunk is returned and saved in DuckDB.

### Step 2: Extract & Enrich (Our Custom Indexer)
1. The Markdown chunk goes to the **NER Router**.
2. **Recognizers-Text** pulls exact dates and currencies.
3. **GLiNER2** pulls people, locations, and events.
4. If configured, **Watson** pulls emotion scores. 
5. The router merges all these into a unified `ExtractedEntity[]` JSON object.

### Step 3: Validate & Store
1. **Semantica** receives the entities and checks **Neo4j DB #2**. 
2. If conflicts exist (e.g., multiple conflicting addresses for the same event), the UI halts for human resolution.
3. Once clean, Semantica writes the nodes and edges directly into **Neo4j DB #2**, attaching PROV-O tracking metadata.
4. (Simultaneously, temporal episodes are written to **Graphiti/Neo4j DB #1**, and vectors are written to **LanceDB**).

### Step 4: Native Community Detection & Summarization (Replaces MS GraphRAG Indexer)
1. On a schedule (or triggered by the user), we run a simple Cypher query triggering **Neo4j GDS**.
2. Neo4j GDS runs the **Leiden Algorithm** internally, grouping related entities (e.g., "All communications and events related to the March 15th custody dispute").
3. We query these new clusters and ask our LLM (local or cloud) to write a 1-paragraph summary of each community.
4. The summary is saved back into Neo4j as a `CommunitySummary` node, and embedded into **LanceDB**.

### Step 5: Retrieval & Q&A (Replaces MS GraphRAG Search)
1. User asks a complex question.
2. The Agno Agent uses the **Neo4j GraphRAG Python Package**.
3. The package performs a hybrid search: It hits **LanceDB** for semantic similarity, and traverses **Neo4j** (hitting both the detailed facts and the high-level community summaries).
4. The LLM synthesizes the answer with exact provenance citations.

---

## 5. Alternative Graph Frameworks (If Needed)
If you *really* want an out-of-the-box framework to manage the pipeline instead of our custom modular flow, the only viable modular alternative to MS GraphRAG is:

**LightRAG (HKUDS)**
- *Why it's better than MS GraphRAG*: It's open-source, heavily supports local models natively (Ollama/vLLM), uses a dual-level retrieval system (low-level entities + high-level summaries), and is incredibly fast.
- *Why Neo4j Native is still better*: LightRAG manages its own graph storage (usually NetworkX or NanoGraphDB). We already have Neo4j, Semantica, and Graphiti running. Using our own pipeline + Neo4j GDS is cleaner and uses the enterprise databases we already spun up.

---

# Plan Feedback

I've reviewed this plan and have 1 piece of feedback:

## 1. General feedback about the plan
> Neo 4J native would require us to then go back to the custom router in order to incorporate Docdb and Lance DB for the hybrid approach What about Llama graph

---
