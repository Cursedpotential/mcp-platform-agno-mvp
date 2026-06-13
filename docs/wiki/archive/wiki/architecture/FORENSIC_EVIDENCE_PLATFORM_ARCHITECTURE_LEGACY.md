# Forensic Evidence Platform Architecture

> **Version**: 1.0.0
> **Created**: March 3, 2026
> **Author**: Architecture Planning Session
> **Status**: Draft - Ready for Implementation

---

## Executive Summary

This document describes the architecture for a **forensic evidence platform** designed to handle 8+ years of multi-platform messaging data with cryptographic chain of custody, behavioral pattern detection, and Michigan MCL 722.23 factor analysis for custody proceedings.

**Core Value Proposition**: Raw messaging exports → temporally-aware, forensically-hashed evidence with bidirectional LLM/Portal/API access, minimizing custom code through maximum utilization of open-source libraries.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Data Ingestion Pipeline](#data-ingestion-pipeline)
3. [Hash-First Chain of Custody](#hash-first-chain-of-custody)
4. [UUIDv7 Binding Strategy](#uuidv7-binding-strategy)
5. [Semantica Integration](#sementica-integration)
6. [GraphQL Federation Layer](#graphql-federation-layer)
7. [Existing Schema Analysis](#existing-schema-analysis)
8. [Implementation Phases](#implementation-phases)

---

## Architecture Overview

### Scale & Scope

| Dimension        | Specification                                                                              |
| ---------------- | ------------------------------------------------------------------------------------------ |
| **Time Span**        | 8+ years                                                                                   |
| **Volume**           | Thousands of messages                                                                      |
| **Platforms**        | SMS, iMessage, Email, Facebook, WhatsApp, Instagram, Snapchat, Google Chat, Telegram, Signal |
| **Challenge**        | Platform hopping (same conversation split across platforms)                                |
| **Outputs**          | Timeline reconstruction, pattern reports, MCL 722.23 factor analysis, contradiction detection, gaslighting/deceit detection |
| **Chain of Custody** | UUIDv7 binding, SHA-256 hashing, no black boxes, explainable                              |

### The 6-Tier Storage Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                                     INGESTION LAYER                                  │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐        │
│  │ CMS     │  │ Portal  │  │ LLM     │  │ Bucket  │  │ API     │  │ Manual  │        │
│  │ Upload  │  │ UI      │  │ Agent   │  │ (S3/R2) │  │ Webhook │  │ Import  │        │
│  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘        │
│       │            │            │            │            │            │              │
│       └────────────┴────────────┴────────────┴────────────┴────────────┘              │
│                                        │                                             │
│                                        ▼                                             │
│                        ┌───────────────────────────────┐                             │
│                        │   UUIDv7 Assignment           │                             │
│                        │   SHA-256 Hash (forensic)     │                             │
│                        │   BEFORE ANY TRANSFORMATION   │                             │
│                        └───────────────┬───────────────┘                             │
│                                        │                                             │
└────────────────────────────────────────┼─────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                           DUCKDB (TIER 1: MASTER CLOCK & ETL)                         │
│                                                                                      │
│   • Raw evidence blobs (PDFs, images, export files)                                 │
│   • SHA-256 content hash (immutability guarantee)                                   │
│   • UUIDv7 as primary key (time-sortable, globally unique)                          │
│   • Deduplication by content hash                                                   │
│   • Ingestion log (who, when, how)                                                  │
│   • Platform detection (SMS, Email, Facebook, etc.)                                 │
│   • Temporal normalization (all timestamps → UTC)                                   │
│                                                                                      │
│   • postgres extension queries PostgreSQL directly for enrichment                   │
│                                                                                      │
└────────────────────────────────────────┬────────────────────────────────────────────┘
                                         │
                       ┌─────────────────┴─────────────────┐
                       │                                   │
                       ▼                                   ▼
┌──────────────────────────────────────┐   ┌──────────────────────────────────────────┐
│   LANCEDB (TIER 2: MULTIMODAL)        │   │   POSTGRESQL (TIER 5: RELATIONAL)        │
│                                       │   │                                          │
│   • Binary shards (images, PDFs)      │   │   Schema: message-schemas.ts             │
│   • Vector embeddings (1536-dim)      │   │   + hierarchy-schema.ts (this doc)       │
│   • UUIDv7 binding to DuckDB         │   │                                          │
│   • Zero-copy Arrow to DuckDB        │   │   Tables:                                │
│                                       │   │   • sms_messages                         │
│                                       │   │   • facebook_messages                    │
│                                       │   │   • imessage_messages                    │
│                                       │   │   • whatsapp_messages                    │
│                                       │   │   • google_chat_messages                 │
│                                       │   │   • messaging_documents                  │
│                                       │   │   • messaging_conversations_enhanced     │
│                                       │   │   • messaging_messages                   │
│                                       │   │   • messaging_behaviors                  │
│                                       │   │   • mcl_factors                          │
│                                       │   │   • behavior_categories                  │
│                                       │   │                                          │
│                                       │   │   All with UUIDv7 linking to DuckDB      │
│                                       │   └──────────────────────────────────────────┘
│                                       │                  
└───────────────────────────────────────┘                  
                       │                                    
                       │                                    
                       ▼                                    
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                            SEMANTICA PIPELINE (ENTITY EXTRACTION)                     │
│                                                                                      │
│   From Cookbook:                                                                     │
│   • Entity Extraction (NER): people, places, dates, amounts, agreements             │
│   • Relation Extraction: who-said-what-to-whom, temporal edges                       │
│   • Temporal Knowledge Graphs: valid_from/valid_to, contradiction detection         │
│   • Conflict Detection: gaslighting patterns, opposing statements                   │
│   • GraphRAG: retrieve context from knowledge graph for LLM queries                  │
│   • MCPIngestor: ingest from MCP tools directly                                      │
│                                                                                      │
│   All extractions hash-linked to original evidence                                   │
│                                                                                      │
└────────────────────────────────────────┬────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                  NEO4J (TIER 3: SEMANTICA KNOWLEDGE GRAPH - ONE DATABASE)             │
│                                                                                      │
│   ┌─────────────────────────────────────────────────────────────────────────────┐   │
│   │   evidence_graph (SINGLE DATABASE)                                           │   │
│   │                                                                              │   │
│   │   Semantica handles ALL graph operations:                                   │   │
│   │   • Entity extraction (NERExtractor)                                        │   │
│   │   • Relationship discovery (RelationExtractor)                              │   │
│   │   • Temporal knowledge graphs (GraphBuilder with enable_temporal=True)     │   │
│   │   • Conflict detection (ConflictDetector)                                   │   │
│   │   • W3C PROV-O provenance tracking                                          │   │
│   │   • Decision tracking (AgentContext.record_decision)                        │   │
│   │   • Contradiction detection across time                                     │   │
│   │   • Platform-hopping linking                                                │   │
│   │                                                                              │   │
│   │   All nodes use UUIDv7 IDs linked to DuckDB via source_hash                 │   │
│   └─────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                                  OUTPUT LAYER                                        │
│                                                                                      │
│   ┌────────────────┐  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐   │
│   │ GraphQL API    │  │ MCP Tools      │  │ Portal UI      │  │ Export Formats │   │
│   │ (queries)      │  │ (LLM agents)   │  │ (human review) │  │ (court filings)│   │
│   └────────────────┘  └────────────────┘  └────────────────┘  └────────────────┘   │
│                                                                                      │
│   • Timeline generation          • Factor analysis (MCL 722.23)                      │
│   • Pattern reports              • Contradiction evidence                            │
│   • Chain of custody audit       • Gaslighting/deceit detection                     │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Data Ingestion Pipeline

### Hash-First Order of Operations

**CRITICAL: SHA-256 hashing happens BEFORE any transformation.**

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              INGESTION (HASH-FIRST ORDER)                             │
│                                                                                       │
│   Raw Evidence Arrives                                                               │
│        │                                                                              │
│        ▼                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────────────┐    │
│   │  IMMEDIATE SHA-256 (Before ANY transformation)                              │    │
│   │                                                                              │    │
│   │  evidence_sha256 = sha256(original_bytes)                                   │    │
│   │  evidence_id = uuidv7()                                                      │    │
│   │                                                                              │    │
│   │  Store: { id: evidence_id, hash: evidence_sha256, timestamp: now() }        │    │
│   │  IN DUCKDB BEFORE ANY OTHER OPERATION                                        │    │
│   └─────────────────────────────────────────────────────────────────────────────┘    │
│        │                                                                              │
│        ▼                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────────────┐    │
│   │  DUCKDB (TIER 1) - FORENSIC LEDGER                                           │    │
│   │                                                                              │    │
│   │  ingestion_log:                                                              │    │
│   │  ┌──────────────┬──────────────────────────┬─────────────────────┐          │    │
│   │  │ evidence_id  │ sha256_hash              │ original_filename   │          │    │
│   │  ├──────────────┼──────────────────────────┼─────────────────────┤          │    │
│   │  │ 018f3b2a-... │ a1b2c3d4e5f6...          │ sms_export_2024.zip │          │    │
│   │  └──────────────┴──────────────────────────┴─────────────────────┘          │    │
│   │                                                                              │    │
│   │  provenance_chain:                                                           │    │
│   │  ┌──────────────┬──────────────┬──────────────┬───────────────────┐        │    │
│   │  │ evidence_id  │ operation    │ input_hash   │ output_hash       │        │    │
│   │  ├──────────────┼──────────────┼──────────────┼───────────────────┤        │    │
│   │  │ 018f3b2a-... │ INGEST       │ NULL         │ a1b2c3d4e5f6...   │        │    │
│   │  │ 018f3b2a-... │ OCR_EXTRACT  │ a1b2c3d4...  │ b2c3d4e5f6a7...   │        │    │
│   │  │ 018f3b2a-... │ ENTITY_EXTRACT│ b2c3d4e5... │ c3d4e5f6a7b8...   │        │    │
│   │  └──────────────┴──────────────┴──────────────┴───────────────────┘        │    │
│   │                                                                              │    │
│   └─────────────────────────────────────────────────────────────────────────────┘    │
│        │                                                                              │
│        ▼                                                                              │
│   NOW Safe to Process (OCR, Entity Extraction, etc.)                                │
│        │                                                                              │
│        ├─── OCR Extraction ─────┐                                                   │
│        │    (creates NEW hash    │                                                   │
│        │     references original)│                                                   │
│        │                          ▼                                                   │
│        │                    LanceDB (binary + hash chain)                            │
│        │                                                                              │
│        ├─── Entity Extraction (Semantica)                                            │
│        │    (creates NEW hash, references original)                                  │
│        │            │                                                                 │
│        │            ▼                                                                 │
│        │    PostgreSQL + Neo4j (with hash chain)                                     │
│        │                                                                              │
│        └─── Vector Embedding                                                          │
│             (creates NEW hash, references original)                                   │
│                    │                                                                  │
│                    ▼                                                                  │
│             LanceDB (vectors + hash chain)                                           │
│                                                                                       │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

### Hash Chain Schema

```typescript
// Every piece of evidence has a hash chain
interface EvidenceProvenance {
  // Original (immutable)
  evidence_id: UUIDv7;
  original_hash: SHA256;        // Hash of raw bytes BEFORE any processing
  original_filename: string;
  ingestion_timestamp: DateTime;
  ingestion_method: 'CMS' | 'Portal' | 'LLM' | 'Bucket' | 'API' | 'Manual';
  
  // Transformations (append-only chain)
  transformations: [
    {
      operation: 'OCR_EXTRACT';
      input_hash: SHA256;         // Hash of input (original_hash for first op)
      output_hash: SHA256;        // Hash of extracted text
      timestamp: DateTime;
      tool: 'tesseract' | 'pandoc' | 'docling';
      parameters: { language: 'eng', ... };
    },
    {
      operation: 'ENTITY_EXTRACT';
      input_hash: SHA256;         // Hash of OCR output
      output_hash: SHA256;        // Hash of entities JSON
      timestamp: DateTime;
      tool: 'semantica';
      parameters: { model: 'gpt-4', ... };
    }
  ];
  
  // Verification (anytime)
  // sha256(current_file_bytes) should match output_hash of last transformation
}
```

### Verification Query (Court-Admissible)

```graphql
query VerifyEvidenceChain($evidenceId: UUIDv7!) {
  evidence(id: $evidenceId) {
    id
    originalHash
    originalFilename
    ingestionTimestamp
    ingestionMethod
    
    # Full provenance chain
    provenanceChain {
      operation
      inputHash
      outputHash
      timestamp
      tool
      parameters
    }
    
    # Instant verification
    verificationStatus {
      originalIntact        # SHA256(original) == originalHash
      chainIntact           # All transformations verifiable
      lastVerified
      canReproduce          # Can re-run transformations get same result
    }
  }
}
```

---

## UUIDv7 Binding Strategy

### Cross-Tier Linking

Every piece of evidence gets a **UUIDv7** that ties everything together:

```
Evidence Item (DuckDB)     → UUIDv7: 018f3b2a-4c5d-7e8f-9a0b-1c2d3e4f5a6b
  ├── Raw file (LanceDB)   → Same UUIDv7 (binary shard)
  ├── Message row (PG)     → Same UUIDv7 (relational)
  ├── Entity node (Neo4j)  → Same UUIDv7 (graph)
  └── Vector (LanceDB)     → Same UUIDv7 (embedding)

Platform-hopping conversation:
  Message_1 (SMS)      → UUIDv7: 018f3b2a-0001-...
  Message_2 (iMessage) → UUIDv7: 018f3b2a-0002-...
  Message_3 (Email)    → UUIDv7: 018f3b2a-0003-...
  ↓
  Conversation UUIDv7  → 018f3b2a-convo-...
  (Links all message UUIDv7s via temporal edges in Neo4j)
```

### UUIDv7 Benefits

| Feature         | UUIDv4                | UUIDv7                     |
| --------------- | --------------------- | -------------------------- |
| Time-sortable   | ❌ No                | ✅ Yes (48-bit timestamp) |
| Collision-safe  | ✅ Yes                | ✅ Yes                     |
| Database-index  | Random I/O            | Sequential I/O (faster)    |
| Forensic-audit  | No temporal context   | Self-documenting timeline  |

---

## Semantica Integration

### Why Semantica Replaces Graphiti

**Graphiti is DEPRECATED.** Semantica already has ALL temporal knowledge graph capabilities plus more:

| Feature                       | Graphiti (Deprecated) | Semantica                                                     |
| ----------------------------- | --------------------- | ------------------------------------------------------------- |
| Temporal Knowledge Graphs     | ✅                    | ✅ `10_Temporal_Knowledge_Graphs.ipynb`                        |
| Entity/Relation Extraction    | ✅                    | ✅ `05_Entity_Extraction.ipynb` + `06_Relation_Extraction.ipynb` |
| Neo4j Storage                 | ✅                    | ✅ `09_Graph_Store.ipynb`                                      |
| Conflict Detection            | ✅                    | ✅ `17_Conflict_Detection_and_Resolution.ipynb`                |
| **MCP Integration**               | ❌                    | ✅ **`MCPIngestor` - already implemented!**                     |
| GraphRAG                      | ❌                    | ✅ `01_GraphRAG_Complete.ipynb`                                |
| Vector Store                  | ❌                    | ✅ `13_Vector_Store.ipynb` (FAISS, Pinecone, pgvector)         |
| Pipeline Orchestration        | ❌                    | ✅ `07_Pipeline_Orchestration.ipynb`                           |
| Multi-Source Data Integration | ❌                    | ✅ `06_Multi_Source_Data_Integration.ipynb`                    |
| Forensic Use Case             | ❌                    | ✅ `01_Criminal_Network_Analysis.ipynb` - **PERFECT FIT!**         |

### Semantica Pipeline for Forensic Evidence

```python
# From cookbook integration - already tested!
from semantica import (
    MCPIngestor,           # Ingest from MCP tools
    FileIngestor,          # File-based ingestion
    EntityExtractor,       # NER: people, places, dates, amounts
    RelationExtractor,     # who-said-what-to-whom
    TemporalKG,            # Temporal knowledge graphs
    ConflictDetector,      # Gaslighting/contradiction detection
    GraphRAG,              # Retrieve context from graph
    Neo4jStore,            # Persist to Neo4j
)

# Full pipeline initialization
class ForensicEvidencePipeline:
    def __init__(self, neo4j_uri: str, postgres_uri: str, duckdb_path: str):
        self.ingestor = MCPIngestor()
        self.entity_extractor = EntityExtractor(model="gpt-4")
        self.relation_extractor = RelationExtractor()
        self.temporal_kg = TemporalKG(neo4j_uri)
        self.conflict_detector = ConflictDetector()
        self.graph_rag = GraphRAG(neo4j_uri, embedding_model="nomic-embed-text")
        
    async def process_evidence(self, evidence_id: UUIDv7, content: bytes):
        # 1. Hash-first (already done in DuckDB)
        original_hash = sha256(content)
        
        # 2. OCR if needed
        text = await self.ocr_extract(content)
        text_hash = sha256(text.encode())
        
        # 3. Entity extraction (Semantica)
        entities = await self.entity_extractor.extract(text)
        entities_hash = sha256(json.dumps(entities).encode())
        
        # 4. Relation extraction (Semantica)
        relations = await self.relation_extractor.extract(text, entities)
        
        # 5. Build temporal knowledge graph (Semantica)
        await self.temporal_kg.add_evidence(
            evidence_id=evidence_id,
            entities=entities,
            relations=relations,
            timestamp=datetime.utcnow(),
            original_hash=original_hash,
        )
        
        # 6. Conflict detection (Semantica)
        conflicts = await self.conflict_detector.detect(
            evidence_id=evidence_id,
            entities=entities,
            relations=relations,
        )
        
        # 7. Store with UUIDv7 linking
        await self.store_all_tiers(
            evidence_id=evidence_id,
            original_hash=original_hash,
            text_hash=text_hash,
            entities_hash=entities_hash,
            entities=entities,
            relations=relations,
            conflicts=conflicts,
        )
```

### Semantica GraphRAG for Retrieval

```python
# Retrieve context for contradiction detection
async def find_contradictions(self, case_id: UUIDv7, entity_name: str):
    # Semantic search across all evidence
    similar_statements = await self.graph_rag.search(
        query=f"What did {entity_name} say about custody?",
        case_id=case_id,
        k=20,  # Top 20 similar statements
    )
    
    # Graph traversal for relationships
    network = await self.temporal_kg.get_entity_network(
        entity_name=entity_name,
        depth=3,  # 3 hops
    )
    
    # Temporal comparison
    statements_over_time = await self.temporal_kg.get_temporal_facts(
        entity_name=entity_name,
        time_range=(start_date, end_date),
    )
    
    # Detect contradictions
    contradictions = []
    for i, stmt1 in enumerate(statements_over_time):
        for stmt2 in statements_over_time[i+1:]:
            if self.is_contradictory(stmt1, stmt2):
                contradictions.append({
                    'statement_1': stmt1,
                    'statement_2': stmt2,
                    'evidence_ids': [stmt1.evidence_id, stmt2.evidence_id],
                    'temporal_gap': stmt2.timestamp - stmt1.timestamp,
                })
    
    return contradictions
```

---

## GraphQL Federation Layer

### GraphQL Over MCP (Unified Tool Interface)

**Key Architecture Decision**: GraphQL queries are served as MCP tools. This unifies the entire platform under MCP:

```
MCP Gateway (Tool Discovery + Invocation)
    ├── Query Tools
    │   └── query_graphql(graphql_query) → Executes GraphQL against all 6 tiers
    ├── Processing Tools
    │   ├── pandoc_convert
    │   ├── tesseract_ocr
    │   └── docling_extract
    ├── NLP Tools
    │   ├── semantica_extract_entities
    │   ├── semantica_extract_relations
    │   └── semantica_detect_conflicts
    ├── Storage Tools
    │   ├── duckdb_query
    │   ├── lancedb_search
    │   ├── neo4j_traverse
    │   └── postgres_query
    └── Forensics Tools
        ├── sha256_hash
        ├── verify_chain_of_custody
        └── export_evidence_package
```

LLM agents (MCP clients) call `query_graphql` tool with GraphQL queries. Portal UI calls GraphQL directly. Both paths unified under one schema.

### Cross-Tier Query Architecture

GraphQL serves as the **federation layer** that reads from ALL 6 tiers:

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                                    GRAPHQL API                                        │
│                                                                                       │
│   Query: "Show me the network around Person X and what patterns they exhibited"      │
│                                                                                       │
│   ┌─────────────────────────────────────────────────────────────────────────────┐    │
│   │                         RESOLVER COORDINATION                                │    │
│   └─────────────────────────────────────────────────────────────────────────────┘    │
│           │              │              │              │              │               │
│           ▼              ▼              ▼              ▼              ▼               │
│   ┌───────────┐   ┌───────────┐   ┌───────────┐   ┌───────────┐   ┌───────────┐      │
│   │  DuckDB   │   │  LanceDB  │   │   Neo4j   │   │ PostgreSQL│   │   MySQL   │      │
│   │  (T1)     │   │   (T2)    │   │ (T3 & T4) │   │   (T5)    │   │   (T6)    │      │
│   └───────────┘   └───────────┘   └───────────┘   └───────────┘   └───────────┘      │
│                                                                                       │
│   Analytics:      Vectors:        Graph:         Messages:      App Data:           │
│   • Patterns      • Similarity    • Networks     • Content      • Users             │
│   • Stats         • Search        • Temporal     • Metadata     • Workflows         │
│   • Timeline      • Embeddings    • PROV-O       • FTS          • Patterns          │
│                                                                                       │
│   UUIDv7 binds all results together                                                 │
│                                                                                       │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

### GraphQL Schema (Key Types)

```graphql
# ============================================
# CORE EVIDENCE TYPE (UUIDv7-bound across all tiers)
# ============================================

type Evidence {
  id: UUIDv7!
  originalHash: SHA256!          # Hash BEFORE any transformation
  currentHash: SHA256!           # Hash of current state
  originalFilename: String!
  fileSize: Int!
  mimeType: String!
  
  # Ingestion metadata
  ingestionTimestamp: DateTime!
  ingestionMethod: IngestionMethod!
  ingestedBy: String!
  
  # Chain of custody (DuckDB)
  provenanceChain: [Transformation!]!
  custodyChain: [CustodyEvent!]!
  
  # Content (PostgreSQL - from existing schemas)
  extractedText: ExtractedText
  entities: [Entity!]!           # Semantica extraction
  patterns: [Pattern!]!          # Behavioral patterns
  factorMappings: [FactorMapping!]!  # MCL 722.23
  
  # Binary storage (LanceDB)
  binaryShard: BinaryShard
  
  # Vector search (LanceDB)
  embeddings: [Embedding!]!
  
  # Relations (PostgreSQL + Neo4j)
  case: Case!
  conversation: Conversation
  relatedEvidence: [EvidenceRelation!]!
  
  # Network (Neo4j - Semantica)
  networkPosition: NetworkPosition
  
  # Verification
  verificationStatus: VerificationStatus!
}

# ============================================
# CASE & CONVERSATION (Platform-Hopping Aware)
# ============================================

type Case {
  id: UUIDv7!
  name: String!
  description: String
  status: CaseStatus!
  created: DateTime!
  updated: DateTime!
  
  # Parties
  parties: [Party!]!
  
  # Evidence (PostgreSQL)
  evidence: [Evidence!]!
  evidenceCount: Int!
  
  # Conversations (platform-hopping aware)
  conversations: [Conversation!]!
  
  # Timeline (DuckDB)
  timeline: Timeline!
  
  # Analysis (Semantica)
  patterns: [Pattern!]!
  contradictions: [Contradiction!]!
  
  # Network (Neo4j)
  networkGraph: NetworkGraph!
  
  # MCL 722.23 Analysis
  factorAnalysis: FactorAnalysis!
}

type Conversation {
  id: UUIDv7!
  caseId: UUIDv7!
  
  # Participants
  participants: [Party!]!
  
  # Platform spanning (KEY FEATURE)
  platforms: [Platform!]!
  platformHops: [PlatformHop!]!
  
  # Temporal range
  startDate: DateTime!
  endDate: DateTime!
  duration: String!
  
  # Messages (PostgreSQL - existing schema)
  messages: [Message!]!
  messageCount: Int!
  
  # Semantica analysis
  detectedPatterns: [Pattern!]!
  sentimentTrend: SentimentTrend!
  
  # Evidence linkage
  linkedEvidence: [Evidence!]!
}

type PlatformHop {
  id: UUIDv7!
  conversationId: UUIDv7!
  fromPlatform: Platform!
  toPlatform: Platform!
  timestamp: DateTime!
  participant: Party!
  context: String!
}

enum Platform {
  SMS
  IMESSAGE
  EMAIL
  FACEBOOK
  WHATSAPP
  INSTAGRAM
  TELEGRAM
  SIGNAL
  GOOGLE_CHAT
  GOOGLE_MEET
  GOOGLE_PHOTOS
  SNAPCHAT
  OTHER
}

# ============================================
# MESSAGE (Existing Schema Integration)
# ============================================

type Message {
  id: UUIDv7!
  conversationId: UUIDv7!
  
  # Content (existing fields from message-schemas.ts)
  sender: String!
  senderNormalized: String     # E.164 format
  recipient: String
  recipientNormalized: String
  body: String
  timestamp: DateTime!
  platform: Platform!
  
  # Chain of custody
  contentHash: SHA256!
  sourceEvidenceId: UUIDv7!
  
  # Semantica extraction
  entities: [Entity!]!
  relations: [EntityRelation!]!
  
  # Analysis (existing fields)
  preliminarySentiment: String
  preliminarySeverity: Int
  preliminaryPatterns: [String!]!
  preliminaryReasoning: String
  
  # Behaviors (existing schema)
  behaviors: [Behavior!]!
  hasBehaviors: Boolean!
  behaviorCount: Int!
  
  # Attachments
  attachments: [Attachment!]!
}

# ============================================
# ENTITY & RELATIONS (Semantica Output)
# ============================================

type Entity {
  id: UUIDv7!
  type: EntityType!
  value: String!
  normalizedValue: String
  confidence: Float!
  
  # Source (UUIDv7 bound)
  sourceMessageId: UUIDv7
  sourceEvidenceId: UUIDv7!
  extractionMethod: String!    # "semantica"
  
  # Graph (Neo4j)
  relations: [EntityRelation!]!
  networkPosition: NetworkPosition
  
  # Temporal
  firstSeen: DateTime!
  lastSeen: DateTime!
  occurrenceCount: Int!
}

enum EntityType {
  PERSON
  ORGANIZATION
  LOCATION
  DATE
  TIME
  MONEY
  PHONE
  EMAIL
  URL
  AGREEMENT
  PROMISE
  THREAT
  CUSTODY_ARRANGEMENT
  VISITATION_SCHEDULE
  PICKUP_LOCATION
  DROPOFF_LOCATION
  MEDICAL_APPOINTMENT
  SCHOOL_EVENT
  OTHER
}

type EntityRelation {
  id: UUIDv7!
  fromEntity: Entity!
  toEntity: Entity!
  relationType: String!       # "said_to", "agreed_with", "contradicts", etc.
  confidence: Float!
  
  # Evidence (UUIDv7 bound)
  sourceMessageId: UUIDv7!
  sourceEvidenceId: UUIDv7!
  
  # Temporal (Semantica)
  validFrom: DateTime
  validTo: DateTime
  
  # Properties
  properties: JSONB
}

# ============================================
# PATTERN DETECTION (Behavioral Analysis)
# ============================================

type Pattern {
  id: UUIDv7!
  type: PatternType!
  category: PatternCategory!
  
  # Detection
  confidence: Float!
  detectionMethod: String!    # "semantica" | "regex" | "llm"
  detectedAt: DateTime!
  
  # Evidence (UUIDv7 bound)
  evidenceMessages: [Message!]!
  evidenceEntities: [Entity!]!
  
  # Temporal
  firstOccurrence: DateTime!
  lastOccurrence: DateTime!
  occurrenceCount: Int!
  
  # MCL mapping
  mappedFactors: [MCLFactor!]!
  
  # Description
  description: String!
  severity: Severity!
  excerpt: String!
}

enum PatternType {
  # Deceit
  GASLIGHTING
  LYING
  CONTRADICTION
  DENIAL_OF_REALITY
  
  # Manipulation
  DARVO
  TRIANGULATION
  FLYING_MONKEY
  LOVE_BOMBING
  
  # Control
  COERCIVE_CONTROL
  ISOLATION
  FINANCIAL_ABUSE
  PARENTAL_ALIENATION
  
  # Communication
  STONEWALLING
  BLAME_SHIFTING
  VICTIM_PLAYING
  PROJECTION
  
  # Custody-specific
  CUSTODY_INTERFERENCE
  VISITATION_SABOTAGE
  MEDICAL_NEGLECT
  EDUCATIONAL_NEGLECT
}

# ============================================
# MCL 722.23 FACTORS (Michigan Best Interest)
# ============================================

type MCLFactor {
  id: String!               # A through L
  code: String!
  label: String!
  description: String!
  
  # Evidence (UUIDv7 bound)
  evidenceItems: [Evidence!]!
  evidenceCount: Int!
  supportingPatterns: [Pattern!]!
  
  # Analysis
  strength: FactorStrength!
  analysis: FactorAnalysisDetail!
}

enum FactorStrength {
  STRONG_SUPPORTING
  MODERATE_SUPPORTING
  NEUTRAL
  MODERATE_OPPOSING
  STRONG_OPPOSING
}

# ============================================
# NETWORK GRAPH (Neo4j - Semantica)
# ============================================

type NetworkGraph {
  caseId: UUIDv7!
  
  # Nodes and edges
  nodes: [NetworkNode!]!
  edges: [NetworkEdge!]!
  
  # Semantica analytics
  centralityScores: JSONB!
  communities: [Community!]!
  
  # Platform overlap
  platformDistribution: [PlatformDistribution!]!
}

type NetworkNode {
  id: UUIDv7!
  entityId: UUIDv7!
  entityType: EntityType!
  label: String!
  
  # Graph metrics (Semantica)
  betweennessCentrality: Float!
  closenessCentrality: Float!
  degreeCentrality: Int!
  
  # Evidence
  evidenceCount: Int!
  messageCount: Int!
}

# ============================================
# QUERY ROOT
# ============================================

type Query {
  # Case queries
  case(id: UUIDv7!): Case
  cases(filter: CaseFilter, limit: Int, offset: Int): CaseList!
  
  # Evidence queries
  evidence(id: UUIDv7!): Evidence
  evidenceSearch(query: String!, filter: EvidenceFilter, limit: Int): EvidenceList!
  
  # Network queries (Neo4j via Semantica)
  person(id: UUIDv7!): Person
  network(caseId: UUIDv7!, depth: Int): NetworkGraph!
  networkAnalysis(personId: UUIDv7!, caseId: UUIDv7!): NetworkAnalysis!
  
  # Temporal queries (Neo4j T4)
  timeline(caseId: UUIDv7!, filter: TimelineFilter): Timeline!
  temporalFacts(entityName: String!, timeRange: TimeRange!): [TemporalFact!]!
  
  # Pattern queries
  patterns(caseId: UUIDv7!, filter: PatternFilter): PatternList!
  pattern(id: UUIDv7!): Pattern
  
  # Factor queries
  factorAnalysis(caseId: UUIDv7!): FactorAnalysis!
  factor(id: String!): MCLFactor
  
  # Contradiction queries (Semantica)
  contradictions(caseId: UUIDv7!): [Contradiction!]!
  findContradictions(entityName: String!, caseId: UUIDv7!): [Contradiction!]!
  
  # Semantic search (LanceDB + Semantica GraphRAG)
  semanticSearch(caseId: UUIDv7!, query: String!, limit: Int): [SimilarityResult!]!
  
  # Verification
  verifyEvidenceChain(evidenceId: UUIDv7!): VerificationStatus!
  auditCustodyChain(evidenceId: UUIDv7!): [CustodyEvent!]!
  
  # Analytics (DuckDB)
  analytics: AnalyticsQueries!
}

# ============================================
# MUTATION ROOT
# ============================================

type Mutation {
  # Ingestion (hash-first!)
  ingestEvidence(input: IngestEvidenceInput!): IngestEvidenceResult!
  ingestBatch(input: IngestBatchInput!): IngestBatchResult!
  
  # Processing
  extractEntities(evidenceId: UUIDv7!): ExtractionResult!
  extractRelations(evidenceId: UUIDv7!): ExtractionResult!
  detectPatterns(caseId: UUIDv7!): PatternDetectionResult!
  mapFactors(evidenceId: UUIDv7!, factorIds: [String!]!): FactorMappingResult!
  
  # Conversation reconstruction
  reconstructConversation(caseId: UUIDv7!, participantIds: [UUIDv7!]!): Conversation!
  linkPlatformHops(conversationId: UUIDv7!): [PlatformHop!]!
  
  # Export
  exportCase(caseId: UUIDv7!, format: ExportFormat!): ExportResult!
  exportTimeline(caseId: UUIDv7!, format: ExportFormat!): ExportResult!
  exportFactorAnalysis(caseId: UUIDv7!, format: ExportFormat!): ExportResult!
  
  # Chain of custody
  verifyEvidence(evidenceId: UUIDv7!): VerificationStatus!
  addCustodyEvent(input: CustodyEventInput!): CustodyEvent!
}

# Custom scalars
scalar UUIDv7
scalar SHA256
scalar DateTime
scalar JSONB
scalar Upload
```

---

## Existing Schema Analysis

The existing `message-schemas.ts` already has significant thought put into it. Here's how it integrates with this architecture:

### Existing Schema Strengths

| Table                                 | Purpose                                               | Integration Point                      |
| ------------------------------------- | ----------------------------------------------------- | -------------------------------------- |
| `sms_messages`, etc.                  | Platform-specific messages                            | PostgreSQL (Tier 5) - preserve as-is  |
| `messaging_documents`                 | Chain of custody                                      | DuckDB provenance_chain augmentation  |
| `messaging_conversations_enhanced`    | Platform-hopping awareness                            | Neo4j temporal edges                   |
| `messaging_messages`                  | Core forensic record with behavior flags              | Semantica pattern detection input      |
| `messaging_behaviors`                 | Pattern matches (already structured)                  | Semantica conflict detection input     |
| `mcl_factors`                         | MCL 722.23 factor definitions                         | Factor mapping output                  |
| `behavior_categories`                 | 18 behavioral pattern types                           | Pattern classification                 |
| `content_hash`, `file_hash` fields    | SHA-256 chain of custody                              | Already hash-first!                    |

### Fields to Preserve

```typescript
// These existing fields align perfectly with the architecture:
messaging_messages.contentHash          // SHA-256 of message body
messaging_messages.conversationId       // Platform-hopping grouping
messaging_messages.senderNormalized     // E.164 format
messaging_messages.fileHash             // Chain of custody
messaging_messages.hasBehaviors         // Pattern flag
messaging_messages.behaviorCategories   // Pattern types
messaging_documents.fileHash            // SHA-256 of source file
messaging_documents.acquiredBy         // Chain of custody
messaging_documents.acquiredDate       // Chain of custody
messaging_documents.verifiedBy         // Chain of custody
```

### Fields to Add (UUIDv7 binding)

```sql
-- Add UUIDv7 columns to existing tables
ALTER TABLE messaging_documents ADD COLUMN evidence_id UUID;
ALTER TABLE messaging_messages ADD COLUMN evidence_id UUID;
ALTER TABLE messaging_conversations_enhanced ADD COLUMN evidence_id UUID;

-- Link to DuckDB master record
ALTER TABLE messaging_documents ADD COLUMN duckdb_record_id TEXT;
ALTER TABLE messaging_messages ADD COLUMN duckdb_record_id TEXT;
```

---

## Implementation Phases

### Phase 1: Hash-First Ingestion (Week 1-2)

- [ ] Implement DuckDB ingestion_log table
- [ ] Implement DuckDB provenance_chain table
- [ ] Create UUIDv7 generation utility
- [ ] Create SHA-256 hashing pipeline
- [ ] Integration with existing `messaging_documents` schema

### Phase 2: GraphQL Foundation (Week 2-3)

- [ ] Define GraphQL schema (as documented above)
- [ ] Implement resolvers for PostgreSQL (Tier 5)
- [ ] Implement resolvers for DuckDB (Tier 1)
- [ ] Implement resolvers for MySQL (Tier 6)

### Phase 3: Semantica Integration (Week 3-5)

- [ ] Install Semantica library (`pip install semantica[all]`)
- [ ] Configure Neo4j connection (Tiers 3 & 4)
- [ ] Implement EntityExtractor pipeline
- [ ] Implement RelationExtractor pipeline
- [ ] Implement TemporalKG for temporal memory
- [ ] Implement ConflictDetector for gaslighting detection

### Phase 4: GraphQL + Semantica Integration (Week 5-6)

- [ ] Implement Neo4j resolvers via Semantica
- [ ] Implement LanceDB resolvers for vector search
- [ ] Connect GraphRAG for semantic retrieval
- [ ] Platform-hopping detection via temporal edges

### Phase 5: Factor Analysis (Week 6-7)

- [ ] Map patterns to MCL 722.23 factors
- [ ] Implement factor strength scoring
- [ ] Create factor analysis reports
- [ ] Export to court-ready formats

### Phase 6: Platform-Hopping Reconstruction (Week 7-8)

- [ ] Implement conversation clustering across platforms
- [ ] Temporal edge creation in Neo4j
- [ ] Platform hop detection
- [ ] Unified timeline generation

---

## Key Architecture Decisions

### ADR-001: UUIDv7 Over UUIDv4

**Decision**: Use UUIDv7 for all primary keys.

**Rationale**:
- Time-sortable without additional index
- Sequential I/O for database performance
- Self-documenting timeline in the ID itself
- Forensic audit trail benefit

### ADR-002: Semantica Over Graphiti

**Decision**: Use Semantica for all knowledge graph operations.

**Rationale**:
- Graphiti is deprecated
- Semantica has MCP integration already
- Semantica includes GraphRAG (Graphiti did not)
- Semantica includes conflict detection
- Criminal Network Analysis cookbook is a perfect match

### ADR-003: GraphQL Federation Over Hasura/Trino

**Decision**: Build custom GraphQL resolvers for each tier.

**Rationale**:
- Full control over query coordination
- No external dependencies for self-hosted deployment
- Direct Neo4j query capability
- Lower operational complexity

### ADR-004: Hash-First Pipeline

**Decision**: SHA-256 hash BEFORE any transformation.

**Rationale**:
- Court admissibility requires chain of custody from first touch
- Immutable reference point for all derivations
- Content-addressed deduplication
- Forensic audit trail

---

## Appendix: DuckDB postgres Extension

### Cross-Database Query

```sql
-- Install extension
INSTALL postgres;
LOAD postgres;

-- Attach PostgreSQL database
ATTACH 'host=localhost port=5432 dbname=mcp_evidence user=postgres password=xxx' AS pg (TYPE postgres);

-- Query PostgreSQL from DuckDB
SELECT 
    d.evidence_id,
    d.sha256_hash,
    m.sender,
    m.body,
    m.timestamp
FROM duckdb_ingestion_log d
JOIN pg.public.messaging_messages m ON d.evidence_id = m.evidence_id
WHERE m.platform = 'sms'
ORDER BY m.timestamp DESC;
```

### Benefits

- **All-in-one router**: DuckDB can query PostgreSQL directly
- **Hybrid analytics**: OLAP (DuckDB) + OLTP (PostgreSQL)
- **No federation layer needed**: Single query across tiers
- **Simpler architecture**: Reduces GraphQL resolver complexity

---

## Summary

This architecture provides:

1. **Forensic Integrity**: SHA-256 hash-first, UUIDv7 binding, complete provenance chain
2. **Platform-Hopping Support**: Temporal edges link conversations across SMS, iMessage, Email, etc.
3. **Semantica Maximized**: Entity extraction, relation extraction, conflict detection, GraphRAG, temporal KG
4. **GraphQL Federation**: Single API querying all 6 storage tiers with UUIDv7 binding
5. **Existing Schema Compatibility**: Preserves and enhances `message-schemas.ts` design
6. **Court-Admissible**: No black boxes, explainable transformations, complete audit trail

**Next Step**: Begin Phase 1 implementation with hash-first ingestion pipeline.