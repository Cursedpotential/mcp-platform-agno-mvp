# AI-chat ingestion: current vs OpenCode vs ADR-aligned design

> _Byline: Codex · GPT-5 · 2026-08-13_

This is a visual decision aid, not an accepted architecture record. It compares:

1. **Current/live design** — migrations 0021-0023 and the code on `main` before the
   uncommitted OpenCode rewrite.
2. **OpenCode proposal** — the uncommitted migration 0024 and related Python changes.
3. **ADR-aligned recommendation** — a proposed refinement that preserves ADR-0050,
   ADR-0051, ADR-0052, D-048, and D-054. This third state is not implemented yet.

## One-screen comparison

```mermaid
graph LR
    subgraph current["CURRENT ON MAIN"]
        direction TB
        C1["One context table"]
        C2["NormalizedRecord contract"]
        C3["Lane fixed to context"]
        C4["Pending-row polling"]
        C5["Chunk during projection"]
        C1 --> C2 --> C3 --> C4 --> C5
    end

    subgraph opencode["OPENCODE PROPOSAL"]
        direction TB
        O1["Conversation and message tables"]
        O2["Second ChatMessage contract"]
        O3["Five replacement lanes"]
        O4["Human review flag on messages"]
        O5["Polling flags remain"]
        O1 --> O2 --> O3 --> O4 --> O5
    end

    subgraph aligned["ADR-ALIGNED RECOMMENDATION"]
        direction TB
        A1["Context record remains canonical"]
        A2["Optional conversation metadata"]
        A3["Derived segments after chunking"]
        A4["Accepted six-lane vocabulary"]
        A5["Outbox and per-sink cursors"]
        A1 --> A2 --> A3 --> A4 --> A5
    end

    current -->|"OpenCode replaces"| opencode
    current -->|"Recommended evolution"| aligned

    style C1,C2,C3,C4,C5 fill:#e7f5ff,stroke:#1971c2,stroke-width:2px
    style O1,O2,O3,O4,O5 fill:#ffe3e3,stroke:#c92a2a,stroke-width:2px
    style A1,A2,A3,A4,A5 fill:#d3f9d8,stroke:#2f9e44,stroke-width:2px
```

Blue is current, red is the uncommitted OpenCode replacement, and green is the
recommended destination.

## Workflow before: current implementation

```mermaid
graph TB
    F["AI chat file or archive"] --> D["Detect format once"]
    D --> E{"Parser coverage and override"}
    E -->|"Go decoder available"| G["SBV Go parser"]
    E -->|"No Go decoder or fallback"| P["Python parser registry"]
    G --> N["NormalizedRecord list"]
    P --> N
    N --> R[("working.context_record")]
    R --> Q{"Pending sync stamp is null"}
    Q --> W["Chunk and project to platform_context"]
    Q --> X["Chunk and project to Graphiti CASE"]
    W --> WS["Set weaviate_synced_at"]
    X --> GS["Set graphiti_synced_at"]

    style F,D fill:#d3f9d8,stroke:#2f9e44,stroke-width:2px
    style E fill:#ffe8cc,stroke:#d9480f,stroke-width:2px
    style G,P,N fill:#e5dbff,stroke:#5f3dc4,stroke-width:2px
    style R fill:#fff4e6,stroke:#e67700,stroke-width:3px
    style Q fill:#ffe3e3,stroke:#c92a2a,stroke-width:2px
    style W,X,WS,GS fill:#c5f6fa,stroke:#0c8599,stroke-width:2px
```

Current strengths:

- PG is written before Weaviate or Graphiti.
- Both parsers produce the same `NormalizedRecord` contract.
- Vector and graph data are rebuildable projections.
- Archive metadata/assets already have separate context tables.

Current gaps:

- `context_record.lane` is fixed to `context`, so downstream chunks cannot express
  multiple knowledge lanes.
- Sync stamps are a Phase-0 polling mechanism, not ADR-0052's durable outbox/cursor spine.
- There is no explicit persisted segment/chunk review unit.
- Message ordering is implicit rather than a first-class column.

## Workflow after: OpenCode proposal as written

```mermaid
graph TB
    F["AI chat file or archive"] --> D["Detect and parse"]
    D --> N["NormalizedRecord list"]
    N --> A["Adapt into ChatConversation and ChatMessage"]
    A --> C[("working.chat_conversation")]
    A --> M[("working.chat_message")]
    M --> K["Classify each message"]
    K --> L["Set one of five new lanes"]
    L --> H{"lane_reviewed is true"}
    H -->|"Yes"| CH["Group messages by conversation and lane"]
    H -->|"No"| WAIT["Wait for review"]
    CH --> W["Project to lane Weaviate collection"]
    CH --> G["Project to Graphiti"]
    W --> WS["Set weaviate_synced_at"]
    G --> GS["Set graphiti_synced_at"]

    DROP["Migration drops working.context_record"] -.-> C

    style F,D fill:#d3f9d8,stroke:#2f9e44,stroke-width:2px
    style N,A,K,L,CH fill:#e5dbff,stroke:#5f3dc4,stroke-width:2px
    style C,M fill:#fff4e6,stroke:#e67700,stroke-width:3px
    style H fill:#ffe8cc,stroke:#d9480f,stroke-width:2px
    style WAIT fill:#f8f9fa,stroke:#868e96,stroke-width:2px
    style W,G,WS,GS fill:#c5f6fa,stroke:#0c8599,stroke-width:2px
    style DROP fill:#ffe3e3,stroke:#c92a2a,stroke-width:3px
```

What improves:

- Conversation metadata and message order become explicit.
- Thinking, created works, and attachments get dedicated columns.
- A human-review flag exists before projection.
- Different messages from one conversation can route differently.

What regresses or conflicts:

- Classification happens per message before downstream chunking. ADR-0052 says the
  chunk output is what the lane classifier routes.
- Five new lanes replace ADR-0050's accepted six lanes.
- `ChatMessage` becomes a second canonical contract beside `NormalizedRecord`.
- Migration 0024 drops a live source-of-truth table and breaks current callers.
- The accepted outbox/cursor mechanism is not implemented.
- `search_weaviate.py` bypasses the horizon-gated retrieval boundary.

## Schema before: current tables and relationships

```mermaid
erDiagram
    CONTEXT_RECORD {
        uuid id PK
        text source
        text conversation_id
        text conversation_title
        text role
        jsonb participants
        text content
        timestamptz occurred_at
        timestamptz knowledge_time
        text content_hash UK
        jsonb attrs
        timestamptz weaviate_synced_at
        timestamptz graphiti_synced_at
    }

    CONTEXT_ARCHIVE {
        uuid id PK
        text source
        text archive_hash UK
        jsonb manifest
        jsonb metadata
    }

    CONTEXT_ASSET {
        uuid id PK
        uuid archive_id FK
        text conversation_id
        text category
        text content_hash UK
        text blob_path
        text inline_text
    }

    CONTEXT_ARCHIVE ||--o{ CONTEXT_ASSET : contains
    CONTEXT_RECORD }o--o{ CONTEXT_ASSET : references_by_external_id
```

The dotted conceptual weakness is represented by `references_by_external_id`: assets can
carry a conversation ID, but there is no relational conversation parent and no foreign key
from a record to an archive or asset.

## Schema after: OpenCode tables as written

```mermaid
erDiagram
    CHAT_CONVERSATION {
        uuid id PK
        text source
        text conversation_id UK
        text title
        timestamptz created_at
        text file_path
        int message_count
        timestamptz first_message_at
        timestamptz last_message_at
        jsonb attrs
        timestamptz weaviate_synced_at
        timestamptz graphiti_synced_at
    }

    CHAT_MESSAGE {
        uuid id PK
        uuid conversation_id FK
        int message_index UK
        text role
        text content
        timestamptz timestamp
        text thinking
        jsonb artifacts
        jsonb attachments
        text lane
        boolean lane_reviewed
        text content_hash UK
        jsonb attrs
        timestamptz weaviate_synced_at
        timestamptz graphiti_synced_at
    }

    CHAT_CONVERSATION ||--|{ CHAT_MESSAGE : contains
```

This is a cleaner chat-shaped relational model in isolation, but it removes the shared
record contract and still mixes source rows, classification state, human review state,
and projection delivery state in `chat_message`.

## Recommended workflow: preserve raw truth, derive reviewed segments

```mermaid
graph TB
    F["AI chat file or archive"] --> D["Detect format once"]
    D --> E{"Go decoder coverage"}
    E -->|"Covered"| G["SBV Go parser"]
    E -->|"Uncovered or logged failure"| P["Python parser registry"]
    G --> N["NormalizedRecord list"]
    P --> N
    N --> TX["One PG transaction"]
    TX --> C[("Optional context_conversation")]
    TX --> R[("working.context_record")]
    TX --> O[("working.context_record_event")]
    O --> CDC["CDC worker reads after cursor"]
    CDC --> CH["Turn-aware and semantic chunking"]
    CH --> CL["Six-lane segment classifier"]
    CL --> S[("working.context_segment")]
    S --> HITL{"Human reviews segment lane"}
    HITL -->|"Approved"| SO[("working.context_segment_event")]
    HITL -->|"Corrected"| CL
    SO --> W["Lane-specific Weaviate projection"]
    SO --> X["Optional Graphiti subscriber"]
    SO --> EX["Entity and claim extraction tools"]
    W --> CW[("Per-sink cursor")]
    X --> CG[("Per-sink cursor")]
    EX --> CE[("Per-sink cursor")]

    style F,D fill:#d3f9d8,stroke:#2f9e44,stroke-width:2px
    style E,HITL fill:#ffe8cc,stroke:#d9480f,stroke-width:2px
    style G,P,N,CH,CL,CDC fill:#e5dbff,stroke:#5f3dc4,stroke-width:2px
    style C,R,O,S,SO,CW,CG,CE fill:#fff4e6,stroke:#e67700,stroke-width:3px
    style TX fill:#ffe3e3,stroke:#c92a2a,stroke-width:2px
    style W,X,EX fill:#c5f6fa,stroke:#0c8599,stroke-width:2px
```

The important boundary is that raw parsed records remain immutable source truth. Chunking,
lane assignment, review, extraction, and delivery are downstream derived state.

## Recommended schema: responsibility separated by table

```mermaid
erDiagram
    CONTEXT_CONVERSATION {
        uuid id PK
        text source
        text external_id UK
        text title
        timestamptz created_at
        uuid archive_id FK
        jsonb attrs
    }

    CONTEXT_RECORD {
        uuid id PK
        uuid conversation_id FK
        int record_index UK
        text record_type
        text role
        text content
        timestamptz occurred_at
        timestamptz knowledge_time
        text content_hash UK
        jsonb attrs
    }

    CONTEXT_RECORD_EVENT {
        bigint event_id PK
        uuid record_id FK
        text operation
        jsonb full_row
        timestamptz committed_at
    }

    CONTEXT_SEGMENT {
        uuid id PK
        uuid conversation_id FK
        int segment_index UK
        text content
        text lane
        text review_status
        text chunker_version
        text classifier_version
        text content_hash UK
    }

    SEGMENT_RECORD {
        uuid segment_id FK
        uuid record_id FK
        int ordinal
    }

    CONTEXT_SEGMENT_EVENT {
        bigint event_id PK
        uuid segment_id FK
        text operation
        jsonb full_row
        timestamptz committed_at
    }

    CDC_CURSOR {
        text sink_id PK
        text event_table
        bigint last_event_id
        timestamptz updated_at
    }

    CONTEXT_ARCHIVE ||--o{ CONTEXT_CONVERSATION : packages
    CONTEXT_CONVERSATION ||--|{ CONTEXT_RECORD : contains
    CONTEXT_RECORD ||--|{ CONTEXT_RECORD_EVENT : publishes
    CONTEXT_CONVERSATION ||--o{ CONTEXT_SEGMENT : derives
    CONTEXT_SEGMENT ||--|{ SEGMENT_RECORD : traces_to
    CONTEXT_RECORD ||--o{ SEGMENT_RECORD : contributes
    CONTEXT_SEGMENT ||--|{ CONTEXT_SEGMENT_EVENT : publishes
    CONTEXT_RECORD_EVENT }o--o{ CDC_CURSOR : consumed_by
    CONTEXT_SEGMENT_EVENT }o--o{ CDC_CURSOR : consumed_by
```

`CONTEXT_ARCHIVE` already exists; it is shown to make the intended lineage visible.
The exact names and columns in the green design remain subject to the owner decision and a
new append-only migration. No existing table is dropped by this recommendation.

## Table responsibility comparison

| Concern | Current | OpenCode proposal | ADR-aligned recommendation |
|---|---|---|---|
| Raw parsed truth | `context_record` | `chat_message` | `context_record` |
| Canonical code contract | `NormalizedRecord` | `NormalizedRecord` then `ChatMessage` | `NormalizedRecord` only |
| Conversation metadata | Repeated on records/attrs | `chat_conversation` | Optional `context_conversation` parent |
| Ordering | Timestamp/implicit order | `message_index` | `record_index` |
| Lane grain | Fixed table lane | One lane per message | One lane per derived segment |
| Lane vocabulary | `context` only here | Five replacement lanes | ADR-0050 six lanes |
| Human review | None for lane | Boolean on message | Review status on derived segment |
| Chunk provenance | Recomputed, not persisted | Message IDs inside projection chunk | Segment-to-record join table |
| Change delivery | Per-row sync timestamps | Per-row sync timestamps | Full-row outbox + per-sink cursor |
| Rebuild | Clear timestamps | Clear timestamps | Reset one sink cursor |
| Horizon safety | Retrieval seam required | Direct search script bypasses seam | Every subscriber tested; retrieval seam mandatory |
| Migration safety | Live current state | Drops source table | Additive migration; no drop |

## Decision points made visible

```mermaid
graph TB
    Q1{"What remains canonical"}
    Q1 -->|"Existing intent"| A1["NormalizedRecord and context_record"]
    Q1 -->|"OpenCode change"| B1["ChatMessage and chat_message"]

    Q2{"Where lane belongs"}
    Q2 -->|"ADR-0052"| A2["Derived segment after chunking"]
    Q2 -->|"OpenCode change"| B2["Raw message before chunking"]

    Q3{"How changes propagate"}
    Q3 -->|"ADR-0052"| A3["Transactional outbox and cursors"]
    Q3 -->|"OpenCode change"| B3["Nullable sync timestamps"]

    Q4{"Migration posture"}
    Q4 -->|"Recommended"| A4["Additive and reversible"]
    Q4 -->|"OpenCode change"| B4["Drop and replace"]

    style Q1,Q2,Q3,Q4 fill:#ffe8cc,stroke:#d9480f,stroke-width:2px
    style A1,A2,A3,A4 fill:#d3f9d8,stroke:#2f9e44,stroke-width:2px
    style B1,B2,B3,B4 fill:#ffe3e3,stroke:#c92a2a,stroke-width:2px
```

The recommended answers are the green path. Choosing a red path is possible, but each one
would require explicitly superseding an accepted owner ruling rather than silently changing
the implementation underneath it.
