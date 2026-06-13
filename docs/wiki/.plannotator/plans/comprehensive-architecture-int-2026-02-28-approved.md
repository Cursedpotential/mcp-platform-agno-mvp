# Comprehensive Architecture & Integration Plan: LlamaIndex Property Graph Edition

## 1. Executive Summary
This document defines the definitive end-to-end architecture for the MCP Tool Platform. It replaces monolithic indexing frameworks with **LlamaIndex Property Graph**, providing a highly modular, interchangeable orchestration layer. 

Crucially, this architecture elevates **Chain of Custody, Evidence Handling, DuckDB, Graphiti, and Semantica** to first-class citizens. Every shard of data—from the raw file down to an extracted emotion—is strictly linked via **UUIDv7**, backed by **SHA-256 hashing**, and tracked via W3C PROV-O provenance.

---

## 2. Core Data Standards: Chain of Custody & Traceability

### A. Immutable Identification
Every entity in the system uses **UUIDv7** (Time-Ordered UUIDs). This ensures that primary keys natively cluster by time, radically improving database indexing performance for chronological legal/custody timelines.
- `DocumentID`: UUIDv7
- `ChunkID`: UUIDv7
- `EntityID`: UUIDv7
- `EpisodeID`: UUIDv7 (Graphiti)

### B. Chain of Custody & Evidence Handling
The platform is built for legal admissibility:
1. **Intake Hashing:** The moment a file hits the server, a **SHA-256 hash** is generated.
2. **Immutable Storage:** The raw blob and the hash are stored immediately in **DuckDB**.
3. **Strict Linking:**
   - Every `Chunk` (shard) links its `ChunkID` back to the parent `DocumentID`.
   - Every `Entity` extracted links its `EntityID` back to the exact `ChunkID` (and character offsets) it was found in.
   - Every `Community Summary` links back to the underlying `EntityIDs`.
   - **Result:** If an LLM answers a question using a summary, the system can trace the citation perfectly backwards: Summary -> Entity -> Chunk -> Document -> SHA-256 Hash.

---

## 3. Component Responsibility Matrix

### Tier 1: Ingestion, Evidence & Document Store (The "Vault")
- **DuckDB (First-Touch Source of Truth)**: Stores the raw file blobs, SHA-256 hashes, file metadata, UUIDv7 mappings, and the raw parsed Markdown.
- **LlamaIndex Readers (Modular Parsers)**:
  - `Docling` / `Unstructured`: Primary local parsers.
  - `LlamaParse`: Cloud fallback for heavily nested/complex PDFs.
  - `Amazon Textract`: Cloud fallback *strictly routed* for screenshots of text messages.

### Tier 2 & 3: LlamaIndex Orchestration & Modular NER (The "Engine")
LlamaIndex manages the pipeline, chunking text and passing it to our custom, pluggable `BaseExtractor` wrappers:
- **GLiNER2 (Fastino)**: Local Python. Semantic entities (`person`, `location`, `legal_proceeding`).
- **Recognizers-Text (Microsoft)**: Local Node.js. Structured data (`dates`, `currency`, `phone_numbers`).
- **IBM Watson NLU**: Cloud opt-in. Emotion analysis (anger, fear, sadness) and semantic roles.
- **Google Cloud NL + Maps**: Cloud opt-in. Geocoding validation for addresses.

### Tier 4: Validation & Provenance (Semantica)
- **Semantica (Hawksight-AI)**: Inserted as a LlamaIndex *Node Postprocessor*. 
- Intercepts all extracted nodes *before* they hit the database.
- Checks against existing facts in Neo4j. If conflicts arise, halts for **HITL (Rule #8)**.
- Attaches strict W3C PROV-O provenance tracking to the nodes.

### Tier 5: The Specialized Databases (The "Hybrid Storage")
LlamaIndex automates the writes and hybrid retrieval across these engines:
- **LanceDB**: Vector storage for the text chunks and embeddings (via local Ollama or cloud).
- **Neo4j DB #1 (Graphiti)**: Episodic/Temporal memory. Tracks the chronological sequence of events and communications.
- **Neo4j DB #2 (Semantica)**: Absolute facts, validated entities, W3C PROV-O relationships, and LlamaIndex Property Graphs.

---

## 4. The End-to-End Workflow (Data Lifecycle)

### Phase 1: Ingest & Chain of Custody
1. User uploads a file (e.g., `custody_order.pdf`).
2. The system immediately generates a **SHA-256 hash** and a **Document UUIDv7**.
3. **DuckDB** records the UUIDv7, Hash, and raw blob.
4. The **Document Router** selects the parser (e.g., `Docling`).
5. The parser returns clean Markdown, which is stored in **DuckDB** linked to the Document UUIDv7.

### Phase 2: Orchestration & Extraction
1. **LlamaIndex** retrieves the Markdown from DuckDB and chunks it. Each chunk is assigned a **Chunk UUIDv7**, linked to the Document UUIDv7.
2. LlamaIndex passes the chunks to the modular extractors.
3. **GLiNER2** extracts `{name: "John Doe"}`.
4. **Recognizers-Text** extracts `{date: "2024-03-15"}`.
5. Each extracted entity receives an **Entity UUIDv7**, linked to the Chunk UUIDv7.

### Phase 3: Semantica Validation & Provenance
1. LlamaIndex attempts to commit the nodes. **Semantica** intercepts them.
2. Semantica queries **Neo4j DB #2** to check for conflicts (e.g., John Doe is already known, but the new document claims he lives at a conflicting address).
3. If a conflict is found, the UI flags the user for resolution (Rule #8).
4. Once clean, Semantica tags the nodes with W3C PROV-O metadata (e.g., `wasDerivedFrom: Chunk UUIDv7`).

### Phase 4: Automated Hybrid Storage
1. LlamaIndex sends the chunks to an embedding model (e.g., Ollama `nomic-embed-text`).
2. The vectors are committed to **LanceDB** (keyed by Chunk UUIDv7).
3. The validated property graph nodes/edges are committed to **Neo4j DB #2 (Semantica)** via `Neo4jPropertyGraphStore`.
4. Concurrently, episodic timelines (e.g., "John Doe texted Jane Doe at 14:00") are sent to **Graphiti** and committed to **Neo4j DB #1**.

### Phase 5: Hybrid Retrieval & Q&A
1. User asks the Agno Agent: *"Show me all communications involving high anger regarding the March 15th custody drop-off."*
2. The Agno Agent uses the LlamaIndex `PropertyGraphRetriever` tool.
3. **LlamaIndex orchestrates a hybrid search**:
   - Queries **LanceDB** for vector similarity to "high anger custody drop-off".
   - Traverses **Neo4j DB #2** for exact entities ("March 15th", "John Doe").
   - Traverses **Neo4j DB #1 (Graphiti)** for the chronological sequence of those texts.
4. The LLM synthesizes the answer. Because every node is linked via UUIDv7, the system returns **unbreakable citations** pointing directly to the SHA-256 verified source documents in DuckDB.

---

## 5. Implementation Phasing

### Phase A: Foundation & Chain of Custody
- Implement UUIDv7 generation and SHA-256 hashing at the API intake layer.
- Finalize the **DuckDB** schema to store Blobs, Hashes, and Markdown text.
- Configure connection strings for LanceDB, Neo4j #1 (Graphiti), and Neo4j #2 (Semantica).

### Phase B: LlamaIndex & Modular Parsers
- Install LlamaIndex ecosystem (`llama-index-core`, `llama-index-property-graph`).
- Implement the Document Router using LlamaIndex Reader plugins (Docling, Unstructured, Textract, LlamaParse).

### Phase C: Modular NER Extractors
- Create custom LlamaIndex `BaseExtractor` wrappers for **GLiNER2** (Python bridge) and **Recognizers-Text** (Native Node.js).
- Create opt-in wrapper classes for IBM Watson NLU and Google NL.

### Phase D: Semantica Intercept & Dual Neo4j
- Implement Semantica as a custom LlamaIndex `TransformComponent` (Node Postprocessor) to intercept nodes before database insertion.
- Build the Conflict Resolution UI hook for human-in-the-loop (Rule #8).
- Wire the final `Neo4jPropertyGraphStore` commits to DB #2, and Graphiti episode commits to DB #1.

---

# Plan Feedback

I've reviewed this plan and have 1 piece of feedback:

## 1. General feedback about the plan
> So now how do we take our current code base and implement this with as little additional work as possible 'cause we need to go into a Sprint mode I need this done like in days at least able to process messages like ASAP

---
