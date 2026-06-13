---
title: Proposed Architecture - ContextForge + DIAL Integration
version: 1.0.0
created: 2026-03-16 17:30
modified: 2026-03-16 17:30
author: thinking@opencode
project: dial-stack
status: draft
---

# Proposed Architecture: ContextForge + DIAL Integration

## Executive Summary

This document analyzes the proposed architecture where:
- **ContextForge** sits as the **primary gateway** (API, backend)
- **DIAL** acts as **internal orchestrator + chat frontend**
- **Direct access** (React app, admin) available alongside DIAL
- **Semantica** is MVP-critical and must function properly

---

## Proposed Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           EXTERNAL ACCESS LAYER                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐          │
│  │   DIAL Chat     │    │   React App     │    │   API Clients   │          │
│  │   (port 3000)   │    │  (port 5173)    │    │   (external)    │          │
│  │                 │    │                 │    │                 │          │
│  │ • Chat UI       │    │ • HITL Review   │    │ • Scripts       │          │
│  │ • Orchestrator  │    │ • Admin Portal  │    │ • Integrations  │          │
│  │ • Workflows     │    │ • Direct Access │    │ • Third-party   │          │
│  └────────┬────────┘    └────────┬────────┘    └────────┬────────┘          │
│           │                      │                      │                    │
│           └──────────────────────┼──────────────────────┘                    │
│                                  │                                           │
│                                  ▼                                           │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                    CONTEXTFORGE GATEWAY (port 4444)                   │  │
│  │                                                                       │  │
│  │  ┌─────────────────────────────────────────────────────────────────┐  │  │
│  │  │                    PLUGIN PIPELINE                               │  │  │
│  │  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐   │  │  │
│  │  │  │   PII   │→│Secrets  │→│Content  │→│ Policy  │→│  Cache  │   │  │  │
│  │  │  │ Filter  │ │Detect   │ │Moderate │ │ (Cedar) │ │(Redis)  │   │  │  │
│  │  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘   │  │  │
│  │  └─────────────────────────────────────────────────────────────────┘  │  │
│  │                                                                       │  │
│  │  ┌─────────────────────────────────────────────────────────────────┐  │  │
│  │  │                  PROTOCOL TRANSLATION                           │  │  │
│  │  │  • MCP Federation (TS/Py/JS servers)                            │  │  │
│  │  │  • REST-to-MCP (court APIs, external services)                  │  │  │
│  │  │  • gRPC-to-MCP (forensic services)                              │  │  │
│  │  │  • A2A Protocol (agent federation)                              │  │  │
│  │  └─────────────────────────────────────────────────────────────────┘  │  │
│  │                                                                       │  │
│  │  ┌─────────────────────────────────────────────────────────────────┐  │  │
│  │  │                    OBSERVABILITY                                │  │  │
│  │  │  OpenTelemetry → Phoenix/Jaeger → Chain of Custody Audit        │  │  │
│  │  └─────────────────────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                  │                                           │
└──────────────────────────────────┼───────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           INTERNAL MCP LAYER                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐  │
│  │   TS MCP Server     │  │   Py MCP Server     │  │   JS MCP Server     │  │
│  │   (port 8081)       │  │   (port 8082)       │  │   (port 8083)       │  │
│  │                     │  │                     │  │                     │  │
│  │ ┌─────────────────┐ │  │ ┌─────────────────┐ │  │ • Format Detector   │  │
│  │ │ Parsers         │ │  │ │ **SEMANTICA**   │ │  │ • Text Utilities    │  │
│  │ │ • SMS XML       │ │  │ │ (MVP CRITICAL)  │ │  │ • API Adapters      │  │
│  │ │ • Facebook JSON/HTML │ │  │ └──────────────┘ │  │ • Custom Logic     │  │
│  │ │ • WhatsApp TXT  │ │  │                     │  └─────────────────────┘  │
│  │ │ • PDF iMessage  │ │  │ ┌─────────────────┐ │                           │
│  │ └─────────────────┘ │  │ │ Vector Search   │ │                           │
│  │                     │  │ │ (LanceDB)       │ │                           │
│  │ ┌─────────────────┐ │  │ └─────────────────┘ │                           │
│  │ │ DuckDB Vault    │ │  │                     │                           │
│  │ │ (Tier 1)        │ │  │ ┌─────────────────┐ │                           │
│  │ └─────────────────┘ │  │ │ Graph Builder   │ │                           │
│  │                     │  │ │ (Neo4j)         │ │                           │
│  │ ┌─────────────────┐ │  │ └─────────────────┘ │                           │
│  │ │ PostgreSQL      │ │  │                     │                           │
│  │ │ Write           │ │  │ ┌─────────────────┐ │                           │
│  │ └─────────────────┘ │  │ │ DPK Tools       │ │                           │
│  └─────────────────────┘  │ │ • HAP Score     │ │                           │
│                           │ │ • PII Redact    │ │                           │
│                           │ │ • Lang ID       │ │                           │
│                           │ └─────────────────┘ │                           │
│                           └─────────────────────┘                           │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           STORAGE TIERS                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌───────────────┐  ┌──────────────┐  ┌────────────────┐  ┌──────────────┐  │
│  │ DuckDB        │  │ LanceDB      │  │ Neo4j          │  │ PostgreSQL   │  │
│  │ (Tier 1)      │  │ (Tier 2)     │  │ (Tier 3)       │  │ (Tier 4)     │  │
│  │               │  │              │  │                │  │              │  │
│  │ • SHA-256     │  │ • Embeddings │  │ • Temporal KG  │  │ • Evidence   │  │
│  │ • Master      │  │ • Multimodal │  │ • PROV-O       │  │ • App Data   │  │
│  │   Clock       │  │   Vault      │  │ • Entities     │  │ • Auth       │  │
│  │ • Dedup       │  │              │  │ • Relations    │  │              │  │
│  └───────────────┘  └──────────────┘  └────────────────┘  └──────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Workflow Simulations

### Workflow 1: Evidence Ingestion (Happy Path)

**User Action**: Analyst uploads SMS export file via React app

```
Step 1: Upload
┌─────────────┐
│ React App   │ ──► User selects "sms_export.xml"
│ (port 5173) │     Clicks "Upload Evidence"
└─────────────┘
       │
       ▼
Step 2: Gateway Entry
┌─────────────────────┐
│ ContextForge        │ ──► Request intercepted
│ (port 4444)         │     JWT token validated (Keycloak)
│                     │     Plugin pipeline starts
└─────────────────────┘
       │
       ▼
Step 3: Plugin Pipeline (Pre-Processing)
┌─────────────────────┐
│ Plugin Pipeline     │ ──► PII Filter: Scans for SSN, emails
│                     │     Secrets Detection: Checks for API keys
│                     │     Content Moderation: Flags abuse/hate
│                     │     Policy (Cedar): Checks upload permission
│                     │     ✓ All pass → Continue
└─────────────────────┘
       │
       ▼
Step 4: Tool Routing
┌─────────────────────┐
│ ContextForge        │ ──► Identifies tool: parse_sms_xml
│                     │     Routes to: TS MCP Server (8081)
│                     │     Invokes via MCP protocol
└─────────────────────┘
       │
       ▼
Step 5: TS MCP Server Processing
┌─────────────────────┐
│ TS MCP Server       │ ──► parse_sms_xml tool executes
│ (port 8081)         │     XML parsed → messages extracted
│                     │     SHA-256 fingerprint generated
│                     │     DuckDB: Master clock entry
│                     │     PostgreSQL: Evidence records
└─────────────────────┘
       │
       ▼
Step 6: Return to ContextForge
┌─────────────────────┐
│ ContextForge        │ ──► Result received from TS MCP
│ (port 4444)         │     Plugin pipeline (post-processing)
│                     │     Cache: Store result (Redis)
│                     │     Observability: Log trace (OTLP)
└─────────────────────┘
       │
       ▼
Step 7: Response to User
┌─────────────┐
│ React App   │ ◄── "Uploaded 1,247 messages"
│ (port 5173) │     Evidence ID: ev_abc123
└─────────────┘     SHA-256: a1b2c3...
```

**Latency Breakdown**:
- ContextForge overhead: ~15-25ms
- Plugin pipeline: ~10-20ms (parallel execution)
- TS MCP parsing: ~50-200ms (depends on file size)
- Database writes: ~20-50ms
- **Total**: ~95-295ms (acceptable for ingestion)

---

### Workflow 2: Semantica Entity Extraction (MVP Critical)

**User Action**: Analyst requests entity extraction for case evidence

```
Step 1: Request
┌─────────────┐
│ DIAL Chat   │ ──► User: "Extract entities from case_123 evidence"
│ (port 3000) │     DIAL Core receives request
└─────────────┘
       │
       ▼
Step 2: DIAL Orchestration
┌─────────────────────┐
│ DIAL Core           │ ──► Determines: This is a tool call
│ (port 8080)         │     Tool: extract_entities
│                     │     Routes to: ContextForge gateway
└─────────────────────┘
       │
       ▼
Step 3: ContextForge Gateway
┌─────────────────────┐
│ ContextForge        │ ──► Receives tool call request
│ (port 4444)         │     Plugin pipeline (pre)
│                     │     Routes to: Py MCP Server (8082)
└─────────────────────┘
       │
       ▼
Step 4: Py MCP Server - Semantica
┌─────────────────────────────────────────────────────────────┐
│ Py MCP Server                                               │
│ (port 8082)                                                 │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ SEMANTICA NLP ENGINE (MVP CRITICAL)                   │  │
│  │                                                       │  │
│  │ 1. Load evidence from PostgreSQL                     │  │
│  │    SELECT * FROM evidence WHERE case_id = 'case_123' │  │
│  │                                                       │  │
│  │ 2. NER Processing (spaCy-based)                      │  │
│  │    • Person names: "John Smith", "Jane Doe"          │  │
│  │    • Locations: "123 Main St, Flint, MI"             │  │
│  │    • Organizations: "Genesee County Court"           │  │
│  │    • Dates: "March 15, 2024", "2024-03-15"           │  │
│  │    • Money: "$5,000", "five thousand dollars"        │  │
│  │                                                       │  │
│  │ 3. Entity Linking                                    │  │
│  │    • "John Smith" → Entity::person_abc123            │  │
│  │    • "J. Smith" → same entity (dedup)                │  │
│  │                                                       │  │
│  │ 4. Relationship Extraction                           │  │
│  │    • John Smith -- CALLED --> Jane Doe               │  │
│  │    • John Smith -- PAID --> $5,000                   │  │
│  │                                                       │  │
│  │ 5. Temporal Fact Extraction                          │  │
│  │    • Event: Payment                                  │  │
│  │    • Time: March 15, 2024                            │  │
│  │    • Actor: John Smith                               │  │
│  │                                                       │  │
│  │ 6. Graph Construction (Neo4j)                        │  │
│  │    • CREATE (e:Event {type: 'Payment'})              │  │
│  │    • CREATE (p:Person {name: 'John Smith'})          │  │
│  │    • CREATE (p)-[:PARTICIPATED_IN]->(e)              │  │
│  │                                                       │  │
│  │ 7. Vector Embedding (LanceDB)                        │  │
│  │    • Generate embeddings for semantic search         │  │
│  │                                                       │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
       │
       ▼
Step 5: Return Path
┌─────────────────────┐
│ ContextForge        │ ◄── Result: 47 entities, 23 relationships
│ (port 4444)         │     Plugin pipeline (post)
│                     │     PII check on entity names
│                     │     Cache result
└─────────────────────┘
       │
       ▼
Step 6: DIAL Response
┌─────────────┐
│ DIAL Chat   │ ◄── "Extracted 47 entities from case_123:
│ (port 3000) │     - 12 people (John Smith, Jane Doe...)
│             │     - 8 locations
│             │     - 15 dates
│             │     - 12 organizations
│             │     Graph updated in Neo4j"
└─────────────┘
```

**Latency Breakdown**:
- DIAL routing: ~5ms
- ContextForge overhead: ~15ms
- Semantica processing: ~500-2000ms (depends on evidence volume)
- Neo4j writes: ~50-100ms
- LanceDB embeddings: ~100-300ms
- **Total**: ~670-2420ms (acceptable for batch processing)

---

### Workflow 3: DIAL-Initiated Workflow (Orchestration)

**User Action**: Analyst asks DIAL to analyze a timeline

```
Step 1: User Request
┌─────────────┐
│ DIAL Chat   │ ──► User: "Build a timeline of all communications
│ (port 3000) │              between John and Jane in case_123"
└─────────────┘
       │
       ▼
Step 2: DIAL Core - LLM Processing
┌─────────────────────────────────────────────────────────────────┐
│ DIAL Core                                                       │
│ (port 8080)                                                     │
│                                                                 │
│ 1. Send to LLM (via OpenRouter)                                │
│    Prompt: "User wants timeline of communications..."          │
│                                                                 │
│ 2. LLM Response: Tool Call Plan                                │
│    a. search_entities(name: "John Smith")                      │
│    b. search_entities(name: "Jane Doe")                        │
│    c. get_communication_history(person1, person2)              │
│    d. build_timeline(events)                                   │
│                                                                 │
│ 3. DIAL executes tools via ContextForge                        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
       │
       ├──────────────────────────────────────────────────┐
       ▼                                                  ▼
Step 3a: Entity Search                           Step 3b: Comm History
┌─────────────────────┐                         ┌─────────────────────┐
│ ContextForge        │                         │ ContextForge        │
│ ──► Py MCP          │                         │ ──► TS MCP          │
│ ──► LanceDB         │                         │ ──► PostgreSQL      │
│                     │                         │                     │
│ Result:             │                         │ Result:             │
│ entity_id: abc123   │                         │ 47 messages         │
│ (John Smith)        │                         │ 23 calls            │
└─────────────────────┘                         └─────────────────────┘
       │                                                  │
       └──────────────────────────────────────────────────┘
                                  │
                                  ▼
Step 4: Timeline Construction
┌─────────────────────────────────────────────────────────────────┐
│ DIAL Core                                                       │
│                                                                 │
│ 1. Combine results from tools                                  │
│ 2. LLM synthesizes timeline:                                   │
│                                                                 │
│    Timeline: John Smith ↔ Jane Doe                             │
│    ─────────────────────────────────────────                   │
│    2024-01-15 09:23  SMS: "Hi Jane, about the hearing..."      │
│    2024-01-15 10:45  Call: 12 min                              │
│    2024-01-16 14:30  SMS: "See you tomorrow"                   │
│    2024-01-17 08:00  Call: 5 min                               │
│    ...                                                          │
│                                                                 │
│ 3. Return to user                                              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
       │
       ▼
Step 5: Response
┌─────────────┐
│ DIAL Chat   │ ◄── Timeline displayed with:
│ (port 3000) │     • Interactive timeline UI
│             │     • Evidence links
│             │     • Entity highlights
└─────────────┘
```

---

## Identified Issues & Mitigations

### Issue 1: Double Hop Latency

**Problem**: DIAL → ContextForge → MCP adds extra hop

```
Current:  DIAL ──► MCP Server         (1 hop, ~5ms)
Proposed: DIAL ──► ContextForge ──► MCP  (2 hops, ~20ms)
```

**Mitigation**:
- Accept ~15ms overhead for governance benefits
- Use ContextForge caching for repeated queries
- Bypass ContextForge for read-only queries via direct React app access

**Impact**: LOW - Evidence processing is batch-oriented, not latency-sensitive

---

### Issue 2: Semantica Dependency Chain

**Problem**: Semantica is MVP-critical but depends on multiple layers

```
React/DIAL → ContextForge → Py MCP → Semantica → Neo4j/LanceDB
     ↑            ↑            ↑          ↑           ↑
   UI Layer   Gateway    Python Env   NLP Model   Storage
```

**Failure Points**:
1. ContextForge plugin blocks request → Semantica never runs
2. Py MCP server down → No entity extraction
3. Neo4j connection fails → Graph not updated
4. LanceDB write fails → Embeddings lost

**Mitigation**:
```yaml
# ContextForge config - ensure Semantica tools bypass aggressive plugins
plugins:
  - name: PIIFilterPlugin
    conditions:
      - tools: ["!extract_entities", "!build_graph", "!semantic_search"]
        # Semantica tools bypass PII filter (handled internally)
  
  - name: ContentModerationPlugin
    mode: "permissive"  # Don't block, just flag
    conditions:
      - tools: ["!extract_entities"]  # Bypass for entity extraction
```

**Fallback Architecture**:
```
Primary:  DIAL → ContextForge → Py MCP → Semantica
Fallback: DIAL → Direct Py MCP → Semantica (if ContextForge fails)
```

---

### Issue 3: ContextForge Single Point of Failure

**Problem**: If ContextForge goes down, all tool access is blocked

**Mitigation**:
```yaml
# Deploy ContextForge with high availability
services:
  contextforge:
    deploy:
      replicas: 2
      update_config:
        parallelism: 1
        delay: 10s
      restart_policy:
        condition: on-failure
        max_attempts: 3
```

**Alternative Access Paths**:
```
┌─────────────────────────────────────────────────────────────┐
│                     ACCESS MATRIX                            │
├─────────────────┬───────────────────┬───────────────────────┤
│ Access Method   │ Via ContextForge  │ Direct (Fallback)     │
├─────────────────┼───────────────────┼───────────────────────┤
│ DIAL Chat       │ Yes (primary)     │ Yes (if CF down)      │
│ React App       │ Yes (primary)     │ Yes (admin bypass)    │
│ API Clients     │ Yes (primary)     │ Yes (service account) │
│ WunderGraph     │ No (internal)     │ Yes (direct to DBs)   │
└─────────────────┴───────────────────┴───────────────────────┘
```

---

### Issue 4: Plugin Pipeline Overhead on Semantica

**Problem**: Semantica processes large evidence volumes; plugin overhead accumulates

**Example**:
```
Evidence batch: 10,000 messages
PII filter: 5ms per message × 10,000 = 50 seconds
Content moderation: 3ms per message × 10,000 = 30 seconds
Total overhead: 80 seconds
```

**Mitigation**:
```yaml
# Batch processing mode for Semantica
plugins:
  - name: PIIFilterPlugin
    batch_mode: true  # Process in batches, not per-message
    batch_size: 100
    timeout: 300  # 5 minutes for large batches
    
  - name: ContentModerationPlugin
    mode: "disabled"  # Disable for batch Semantica operations
    conditions:
      - tools: ["extract_entities", "build_graph"]
```

**Architecture Decision**:
- **Real-time queries**: Full plugin pipeline
- **Batch Semantica**: Minimal plugins (PII only), rest handled internally

---

### Issue 5: DIAL as "Internal Orchestrator" vs "Chat Frontend"

**Problem**: DIAL has two roles that may conflict

**Role 1: Chat Frontend**
- User conversations
- Natural language to tool calls
- Streaming responses

**Role 2: Internal Orchestrator**
- Workflow management
- Multi-tool coordination
- State management

**Conflict Example**:
```
User: "Analyze all evidence in case_123"
DIAL starts orchestration...
  Tool 1: extract_entities (running)
  Tool 2: build_timeline (queued)
  Tool 3: detect_conflicts (queued)
User: "Cancel that, just show me the first document"
DIAL: ??? (orchestration in progress, but user wants something else)
```

**Mitigation**:
```
┌─────────────────────────────────────────────────────────────┐
│                    DUAL-MODE DIAL                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────┐       ┌─────────────────────────────┐  │
│  │ CHAT MODE       │       │ ORCHESTRATOR MODE           │  │
│  │ (port 3000)     │       │ (internal)                  │  │
│  │                 │       │                             │  │
│  │ • Conversations │       │ • Workflow engine           │  │
│  │ • Quick queries │       │ • Multi-tool coordination   │  │
│  │ • Streaming     │       │ • State management          │  │
│  │                 │       │ • Background jobs           │  │
│  └─────────────────┘       └─────────────────────────────┘  │
│           │                           │                     │
│           └───────────┬───────────────┘                     │
│                       │                                     │
│                       ▼                                     │
│           ┌─────────────────────┐                          │
│           │ ContextForge        │                          │
│           │ (Unified Gateway)    │                          │
│           └─────────────────────┘                          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Implementation**:
- Chat mode: Immediate responses, single tool calls
- Orchestrator mode: Background jobs, progress tracking
- User can switch between modes
- Cancel button for orchestrator jobs

---

### Issue 6: ContextForge Plugin Configuration Complexity

**Problem**: 40+ plugins with interdependencies

**Example Conflict**:
```yaml
# Wrong order - PII filter runs after content moderation
plugins:
  - name: ContentModerationPlugin
    priority: 50  # Runs first
  - name: PIIFilterPlugin
    priority: 60  # Runs second
# Result: PII leaked to content moderation logs!
```

**Mitigation**:
```yaml
# Correct order with explicit dependencies
plugins:
  - name: PIIFilterPlugin
    priority: 10  # ALWAYS FIRST
    mode: enforce
    
  - name: SecretsDetectionPlugin
    priority: 20
    mode: enforce
    
  - name: ContentModerationPlugin
    priority: 50
    mode: permissive
    
  - name: PolicyPlugin
    priority: 100  # AFTER security checks
    mode: enforce
```

**Validation Script**:
```python
# Validate plugin order before deployment
def validate_plugin_order(plugins: list) -> bool:
    """Ensure security plugins run before content plugins."""
    security_plugins = ["PIIFilterPlugin", "SecretsDetectionPlugin"]
    content_plugins = ["ContentModerationPlugin", "HarmfulContentDetectorPlugin"]
    
    security_priorities = [
        p["priority"] for p in plugins if p["name"] in security_plugins
    ]
    content_priorities = [
        p["priority"] for p in plugins if p["name"] in content_plugins
    ]
    
    return max(security_priorities) < min(content_priorities)
```

---

## Semantica MVP Checklist

### Critical Requirements

| Requirement | Status | Notes |
|-------------|--------|-------|
| Entity extraction works | ✅ | spaCy NER + custom patterns |
| Entity linking works | ✅ | Deduplication by name similarity |
| Neo4j graph writes | ✅ | PROV-O provenance |
| LanceDB embeddings | ✅ | Semantic search |
| Temporal fact extraction | ✅ | Date/event parsing |
| Direct DB access | ⚠️ | Need fallback path |
| Bypass ContextForge | ⚠️ | Configure in DIAL |

### Configuration for Semantica Priority

```yaml
# ContextForge config - Semantica tools have priority
servers:
  - name: py-mcp-server
    transport: stdio
    command: uv run mcp-server
    priority: 100  # Higher priority than other servers
    tools:
      - name: extract_entities
        timeout: 300  # 5 minutes for large batches
        retry: 3
      - name: build_graph
        timeout: 120
      - name: semantic_search
        timeout: 60

plugins:
  # Minimal plugins for Semantica tools
  - name: PIIFilterPlugin
    conditions:
      - tools: ["extract_entities", "build_graph"]
        mode: "permissive"  # Don't block, just log
  
  - name: ContentModerationPlugin
    conditions:
      - tools: ["extract_entities", "build_graph"]
        mode: "disabled"  # Skip for Semantica
```

---

## Recommended Implementation Order

### Phase 1: Foundation (Week 1)
1. Deploy ContextForge (Docker)
2. Configure Keycloak auth
3. Register MCP servers (stdio transport)
4. Test basic tool routing

### Phase 2: Plugin Pipeline (Week 2)
1. Enable PII filter (enforce mode)
2. Enable secrets detection (enforce mode)
3. Configure content moderation (permissive mode)
4. Test plugin order

### Phase 3: Semantica Priority (Week 3)
1. Configure Semantica bypass rules
2. Test entity extraction through ContextForge
3. Benchmark performance
4. Add fallback direct path

### Phase 4: DIAL Integration (Week 4)
1. Configure DIAL to route through ContextForge
2. Test chat mode vs orchestrator mode
3. Implement workflow cancellation
4. Add progress tracking

### Phase 5: Production Hardening (Week 5)
1. High availability deployment
2. Monitoring and alerting
3. Backup direct access paths
4. Load testing

---

## Summary

### Architecture Benefits
✅ Unified gateway for all tool access
✅ Plugin pipeline for security/governance
✅ OpenTelemetry for chain of custody
✅ DIAL as orchestrator + chat frontend
✅ Direct access paths for admin/fallback

### Architecture Risks
⚠️ Double hop latency (~15ms overhead)
⚠️ ContextForge as SPOF (mitigated with HA)
⚠️ Plugin configuration complexity
⚠️ Semantica dependency chain

### Mitigations
✅ Caching for repeated queries
✅ HA deployment with replicas
✅ Validation scripts for plugin order
✅ Direct fallback paths for Semantica
✅ Minimal plugins for batch operations

### Verdict
**Proceed with proposed architecture** with:
1. Semantica bypass configuration
2. Direct fallback paths
3. HA deployment
4. Plugin validation
