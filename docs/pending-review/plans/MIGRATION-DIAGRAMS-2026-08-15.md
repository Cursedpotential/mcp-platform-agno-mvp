# Development and Migration Diagrams

> _Byline: Codex · GPT-5 · 2026-08-15_

## Target architecture

```mermaid
graph TB
    UI["Custom Workbench"] --> API["Framework-neutral Platform API"]
    API --> PY["Python domain and control plane"]
    API --> OC["Persistent OpenCode service"]
    PY --> ORCH["OrchestrationPort"]
    ORCH --> AG2["AG2 Network adapter"]
    ORCH -.-> AGNO["Legacy Agno adapter"]
    PY --> PG[("PostgreSQL authority")]
    GO["Go ingestion data plane"] --> PG
    SEM["Semantica VIP\nsemantic intelligence service"] --> PY
    PG --> GP["Graph projectors"]
    GP --> NEO[("Neo4j evidence and memory")]
    PG --> VP["Vector projector"]
    VP --> WV[("Weaviate")]
    API --> PR["ProviderRegistry"]
    PR --> PK["Portkey"]
    PR --> OCP["OpenCode provider"]
    PR -.-> DIRECT["Policy-gated direct providers"]
    style UI fill:#e7f5ff,stroke:#1971c2,stroke-width:2px
    style PG fill:#fff4e6,stroke:#e67700,stroke-width:2px
    style GO fill:#d3f9d8,stroke:#2f9e44,stroke-width:2px
    style ORCH fill:#e5dbff,stroke:#5f3dc4,stroke-width:2px
    style OC fill:#ffe8cc,stroke:#d9480f,stroke-width:2px
```

## Knowledge and experience separation

```mermaid
graph LR
    SRC["Original sources"] --> CUST["Custody and Go parsing"]
    CUST --> CANON["Canonical normalized knowledge"]
    CANON --> EXT["Horizon-blind extraction"]
    EXT --> CAND["Reviewed candidates"]
    CAND --> PROJ["Graph and vector projections"]
    CANON --> MAN["Immutable horizon manifest"]
    PROJ --> RET["Pre-filtered retrieval"]
    MAN --> RET
    RET --> AGENT["Horizon-bound agent"]
    AGENT --> BEL["PostgreSQL belief events"]
    BEL --> GRAPH["Run-scoped Graphiti belief graph"]
    BEL --> DELTA["Ignorant and hindsight delta"]
    style CANON fill:#fff4e6,stroke:#e67700,stroke-width:2px
    style MAN fill:#ffe3e3,stroke:#c92a2a,stroke-width:2px
    style BEL fill:#e5dbff,stroke:#5f3dc4,stroke-width:2px
    style DELTA fill:#c5f6fa,stroke:#0c8599,stroke-width:2px
```

## Strangler migration

```mermaid
graph TB
    START["Current Agno and AgentOS"] --> PORTS["Freeze platform ports"]
    PORTS --> ROUTE["Add provider routing facade"]
    ROUTE --> BELIEF["Add belief ledger and Graphiti adapter"]
    BELIEF --> SPIKE["Run AG2 coordination spike"]
    SPIKE --> DEC{ "Spike gates pass" }
    DEC -->|No| KEEP["Keep Agno adapter and repair gaps"]
    DEC -->|Yes| SHADOW["Shadow AG2 per workflow"]
    SHADOW --> CUT["Cut over agent by agent"]
    CUT --> QUAR["Quarantine superseded Agno surfaces"]
    QUAR --> DONE["Custom platform runtime"]
    style START fill:#f8f9fa,stroke:#868e96,stroke-width:2px
    style DEC fill:#ffe3e3,stroke:#c92a2a,stroke-width:2px
    style DONE fill:#d3f9d8,stroke:#2f9e44,stroke-width:2px
```

## Go bounded parallel pipeline

```mermaid
graph LR
    FILE["Input stream"] --> DECODER["Ordered format decoder"]
    DECODER --> HASH["Sequence and exact H2"]
    HASH --> QUEUE["Bounded work queue"]
    QUEUE --> W1["Normalize worker"]
    QUEUE --> W2["Repair worker"]
    QUEUE --> W3["Attachment worker"]
    W1 --> REORDER["Bounded reorder buffer"]
    W2 --> REORDER
    W3 --> REORDER
    REORDER --> COMMIT["Ordered H3 and DB committer"]
    COMMIT --> SUMMARY["Reconciliation summary"]
    style FILE fill:#d3f9d8,stroke:#2f9e44,stroke-width:2px
    style QUEUE fill:#e5dbff,stroke:#5f3dc4,stroke-width:2px
    style COMMIT fill:#ffe8cc,stroke:#d9480f,stroke-width:2px
    style SUMMARY fill:#c5f6fa,stroke:#0c8599,stroke-width:2px
```

## Research and implementation dependencies

```mermaid
graph TB
    R0["R0 Wave-1 audit"] --> R2["R2 Horizon engine"]
    R0 --> R1["R1 Go ingestion"]
    R2 --> R4["R4 Belief memory"]
    R2 --> R5["R5 AG2 bake-off"]
    R3["R3 Semantica"] --> R4
    R6["R6 Provider routing"] --> R5
    R6 --> R7["R7 OpenCode workspace"]
    R4 --> R8["R8 Workbench"]
    R5 --> R8
    R7 --> R8
    R1 --> INT["Integration and cutover"]
    R3 --> INT
    R8 --> INT
    style R0 fill:#ffe3e3,stroke:#c92a2a,stroke-width:2px
    style INT fill:#d3f9d8,stroke:#2f9e44,stroke-width:2px
```
