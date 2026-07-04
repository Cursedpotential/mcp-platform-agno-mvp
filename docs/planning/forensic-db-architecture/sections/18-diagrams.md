## Diagrams

> _Byline: Claude Code · Opus 4.8 (1M) · 2026-06-30_
>
> All diagrams below are **descriptive of the locked architecture**, not a blank-slate proposal. They visualize decisions already ratified in the ADRs and the crosswalk (see CONTEXT_PACK §2–3): the four-resource data tier (ADR-0013/0027/0014/0024), the Milvus embedding contract (ADR-0010/0011/0026/0027), the Neo4j+Graphiti bitemporal cognition substrate (ADR-0014/0018/0031), the salem_v3 ontology adoption, the TraceIQ timeline/geocode adaptation, and the cross-cutting lane discipline (raw → extracted → inferred → analytical → legal-conclusion). Where a node is adopted from prior work it is annotated with its provenance.
>
> **Reading the diagrams.** Every diagram uses a consistent colour/lane convention so a non-developer can follow the flow and a developer can implement it:
>
> | Lane | Meaning | Mutability | Diagram tag |
> |---|---|---|---|
> | RAW | Original evidence, byte-preserved | Immutable / append-only | `RAW` |
> | EXTRACTED | Machine-derived facts (OCR, geocode, parse) | Append-only, versioned by run | `EXT` |
> | INFERRED | Model/heuristic conclusions (anomalies, home-base, dedup) | Versioned, never overwrites prior | `INF` |
> | ANALYTICAL | Views, scores, contradiction sets | Recomputable from lower lanes | `ANL` |
> | LEGAL | Court-relevance / abuse-pattern labels | **HITL-gated**, append-only | `LEGAL` |
> | HITL | Human-in-the-loop review gate | Blocking | `HITL` |
>
> Mermaid validity note: every label that contains `(`, `+`, `/`, `:` or `,` is wrapped in quotes so the diagrams parse cleanly in mermaid-cli / mermaid.live.

---

### 18.1 System architecture diagram

End-to-end view of the platform: object store → ingestion → the four persistence resources → cognition/analysis → human review → court-facing exports. The four data-tier resources are drawn as **independently restartable** boxes (CONTEXT_PACK §1, the HARD CONSTRAINT).

```mermaid
flowchart TB
    subgraph SRC["Sources & object store"]
        R2["Cloudflare R2 (ADR-0007)<br/>buckets: nexus, casebible-*"]
        RAWDEV["Raw device exports<br/>SMS/XML, Takeout, iMessage PDF,<br/>FB/IG, Snapchat, GVoice, call logs"]
    end

    subgraph REACH["Reach / federation (ADR-0030/0032)"]
        RCLONE["rclone bucket mount<br/>(file ingest)"]
        PGDUCK_S3["pg_duckdb account-wide<br/>S3 secret (SQL/forensic reads)"]
    end

    subgraph GW["Gateways & compute (ADR-0015/0025)"]
        CF["IBM ContextForge<br/>MCP tool gateway (0.8.0)"]
        LITELLM["LiteLLM :4000"]
        LLM["Ollama Cloud glm-5.1 (PRIMARY)<br/>NIM embed/rerank (backup)"]
        LOCALLLM["Local CPU LLM ≤4B<br/>(evidence-content extraction only)"]
    end

    subgraph AGENTS["Agno agents (agno-gateway)"]
        ING["Ingestion agent"]
        ANA["Analysis agent"]
        FDA["Forensic-data agent"]
        RGK["Review-gatekeeper agent (HITL writes)"]
    end

    subgraph DATATIER["DATA TIER — four independently-restartable resources"]
        PG["RESOURCE 1 (unified, ADR-0013)<br/><b>Postgres 18 + PostGIS + pg_duckdb</b><br/>agno-postgres:18-duckdb<br/>relational + spatial + analytical"]
        MILVUS["RESOURCE 2 (ADR-0027)<br/><b>Milvus</b> — vectors/ANN"]
        NEO["RESOURCE 3 (ADR-0014)<br/><b>Neo4j</b> + Graphiti + Semantica<br/>bitemporal cognition"]
        SURREAL["RESOURCE 4 (ADR-0024)<br/><b>SurrealDB</b> — analysis sink<br/>(Phase D, ratified)"]
    end

    subgraph OUT["Human review & exports"]
        HITLQ["HITL review queue<br/>(doc-intel approvals table)"]
        PKG["Court-facing evidence package<br/>(vw_forensic_evidence_package)"]
    end

    RAWDEV --> R2
    R2 --> RCLONE --> ING
    R2 -. "SQL reads" .-> PGDUCK_S3 --> PG
    ING --> CF --> AGENTS
    AGENTS --> LITELLM --> LLM
    ING -. "evidence content" .-> LOCALLLM
    ING --> PG
    ING --> MILVUS
    ANA --> NEO
    FDA --> PG
    PG -- "PG→Surreal pipeline" --> SURREAL
    NEO --> ANA
    MILVUS --> ANA
    ANA --> RGK --> HITLQ
    HITLQ -- "approved" --> PKG
    PG --> PKG
    NEO --> PKG

    classDef raw fill:#fde8e8,stroke:#c0392b;
    classDef res fill:#e8f0fe,stroke:#1a5fb4,stroke-width:2px;
    classDef hitl fill:#fff3cd,stroke:#b8860b,stroke-width:2px;
    class RAWDEV,R2 raw;
    class PG,MILVUS,NEO,SURREAL res;
    class RGK,HITLQ hitl;
```

**Notes.** Evidence *content* is only ever extracted by the **local CPU LLM (≤4B)** — never by cloud LLMs or external entity-extracting tools (CONTEXT_PACK §4, hardware constraint). The cloud `glm-5.1` path is used for orchestration/reasoning over already-extracted, non-sensitive facts. Every agent *write* is routed through the **review-gatekeeper** (HITL on every write).

---

### 18.2 Evidence ingestion pipeline

From a raw device export to durable, provenance-stamped rows across the four stores. The pipeline enforces lane discipline and the **UUIDv7 + SHA-256 chain-of-custody** column contract (adopted from the salvaged doc-intelligence design, CONTEXT_PACK §3).

```mermaid
flowchart TB
    A["RAW export lands in R2<br/>(verbatim, byte-preserved)"]:::raw
    B["Compute SHA-256 + mint UUIDv7<br/>chain-of-custody anchor"]:::ext
    C["Format detect<br/>schema-resolver.ts AI field-mapping<br/>for unknown formats"]:::ext

    subgraph PARSE["Parser bank (adopted, CONTEXT_PACK §3)"]
        P1["enhanced-xml-chunker<br/>(call logs + base64 imgs)"]
        P2["sms_backup_parser<br/>(blocked-call type 5/6)"]
        P3["GVoice / iMessage-PDF / FB"]
        P4["location / Takeout / Snapchat"]
    end

    D["Land in normalized_messages<br/>raw_data JSON (universal landing)"]:::raw
    E["Typed projection -> messages (V4.1)<br/>people / screenshots / social_action"]:::ext
    F["Extraction pass (local LLM ≤4B)<br/>OCR screenshots, NER, body text"]:::ext
    G["Geocode (dual-provider)<br/>geocode_resolution + geocode_audit<br/>disagreement_flag / tie_break_reason"]:::ext
    H["Timestamp normalization<br/>TEXT -> timestamptz + precision class"]:::ext

    I["Embed bodies<br/>(text 2048-d / code 1536-d)"]:::ext
    J{"is_private OR sensitive?"}:::hitl

    K1["Postgres+PostGIS+pg_duckdb<br/>messages, timeline_event, people,<br/>location_key, geom"]:::res
    K2["Milvus<br/>1 collection / embedder"]:::res
    K3["Neo4j (Graphiti/Semantica)<br/>Person/Statement/Evidence nodes"]:::res

    L["provenance + custody log<br/>(append-only: source_hash, run_id,<br/>prompt_ver, ontology_ver, schema_ver)"]:::ext
    M["Review gate before sensitive labels"]:::hitl

    A --> B --> C --> PARSE --> D --> E --> F --> G --> H
    H --> I
    H --> J
    J -- "yes" --> M
    J -- "no" --> K1
    M -- "approved" --> K1
    I --> K2
    E --> K3
    K1 --> L
    K2 --> L
    K3 --> L

    classDef raw fill:#fde8e8,stroke:#c0392b;
    classDef ext fill:#e6f4ea,stroke:#1e7e34;
    classDef res fill:#e8f0fe,stroke:#1a5fb4,stroke-width:2px;
    classDef hitl fill:#fff3cd,stroke:#b8860b,stroke-width:2px;
```

**Lane mapping.** `A/D` = RAW (never overwritten). `B/C/E/F/G/H/I/L` = EXTRACTED (append-only, stamped with `run_id`). `J/M` = HITL gates. `K1/K2/K3` = the destination resources. Google raw-export JSON shape is preserved verbatim as the RAW evidence contract (CONTEXT_PACK §3).

---

### 18.3 Temporal inference workflow

How a timestamp moves from a raw string to a court-usable temporal fact, carrying its **precision class** (the gap missing from ALL prior schemas — CONTEXT_PACK §3) and its bitemporal coordinates (valid-time + knowledge-time, ADR-0018/0031). Maps the Constraints requirement to distinguish exact / approximate / inferred / uncertain timestamps.

```mermaid
flowchart TB
    T0["Raw timestamp token<br/>(TEXT, any tz/format)"]:::raw
    T1["Parse + tz-resolve<br/>-> timestamptz"]:::ext
    T2{"Source quality?"}:::ext

    PE["precision = EXACT<br/>(device epoch, header date)"]:::ext
    PA["precision = APPROXIMATE<br/>(date only / coarse)"]:::ext
    PI["precision = INFERRED<br/>(derived from order, gaps,<br/>overnight/home_base heuristics)"]:::inf
    PU["precision = UNCERTAIN<br/>(conflicting/illegible)"]:::inf

    BT["Assign bitemporal coords<br/>valid_time = when it happened<br/>knowledge_time = when we learned it<br/>(Neo4j/Graphiti, ADR-0018/0031)"]:::res
    CONF{"Conflicts with existing<br/>timeline_event?"}:::anl

    NEWV["New version (append-only)<br/>preserve prior interpretation"]:::inf
    DISC["disclosure-tier multi-pass<br/>+ contradiction edge candidate"]:::anl

    TE["timeline_event<br/>(split raw vs enriched)<br/>+ precision_class column"]:::res
    HR["HITL review if precision in<br/>{INFERRED, UNCERTAIN} AND<br/>court-facing"]:::hitl

    T0 --> T1 --> T2
    T2 -- "device/header" --> PE
    T2 -- "date-only" --> PA
    T2 -- "heuristic" --> PI
    T2 -- "conflict/illegible" --> PU
    PE --> BT
    PA --> BT
    PI --> BT
    PU --> BT
    BT --> CONF
    CONF -- "no" --> TE
    CONF -- "yes" --> NEWV --> DISC --> TE
    TE --> HR

    classDef raw fill:#fde8e8,stroke:#c0392b;
    classDef ext fill:#e6f4ea,stroke:#1e7e34;
    classDef inf fill:#efe6fa,stroke:#7d3cc9;
    classDef anl fill:#e9eef2,stroke:#4a6072;
    classDef res fill:#e8f0fe,stroke:#1a5fb4,stroke-width:2px;
    classDef hitl fill:#fff3cd,stroke:#b8860b,stroke-width:2px;
```

| Precision class | Source signal | Lane | Court use |
|---|---|---|---|
| EXACT | Device epoch / message header | EXTRACTED | Direct |
| APPROXIMATE | Date-only / coarse window | EXTRACTED | Use with stated window |
| INFERRED | Ordering, gap, overnight/home-base heuristic | INFERRED | HITL + corroboration |
| UNCERTAIN | Conflicting or illegible source | INFERRED | Flag; not for standalone assertion |

Inferred timestamps **never overwrite** an earlier interpretation — a new append-only version is written, and the prior remains queryable via knowledge-time (Constraints: "never overwrite earlier interpretations").

---

### 18.4 Entity-resolution workflow

How candidate entities (people, locations, devices) from many sources are merged into canonical entities while preserving every alias and the merge decision. Adopts the salem_v3 `Person` MERGE rule and TraceIQ `location_key` dedup + `people` MERGE (CONTEXT_PACK §3). Merges are **append-only and reversible** — the system records *why* two records were joined, never silently collapsing them.

```mermaid
flowchart TB
    S1["Candidate entity mentions<br/>(messages.people, call logs,<br/>geocode points, screenshots OCR)"]:::ext
    S2["Blocking / candidate generation<br/>(name, handle, phone, email,<br/>location_key, geom proximity)"]:::ext
    S3["Pairwise similarity<br/>deterministic keys + fuzzy<br/>(pg_trgm) + vector (Milvus)"]:::anl
    S4{"Score >= auto-merge<br/>threshold?"}:::anl

    AUTO["Auto-merge candidate"]:::inf
    REVIEW["Send to HITL<br/>(ambiguous / cross-party)"]:::hitl
    REJECT["Keep separate<br/>(record non-match reason)"]:::inf

    MERGE["MERGE into canonical entity<br/>(salem Person / location_key)<br/>keep ALL aliases as alias rows"]:::res
    PROV["entity_resolution_log (append-only)<br/>method, score, decider (auto/human),<br/>run_id, ontology_ver, timestamp"]:::ext

    PGN["Postgres canonical entity tables<br/>(people, location_key, devices)"]:::res
    NEON["Neo4j node MERGE<br/>(mirror PG canonical id)"]:::res

    S1 --> S2 --> S3 --> S4
    S4 -- ">= auto" --> AUTO --> MERGE
    S4 -- "ambiguous" --> REVIEW
    S4 -- "< no-match" --> REJECT
    REVIEW -- "approve" --> MERGE
    REVIEW -- "reject" --> REJECT
    MERGE --> PGN
    MERGE --> NEON
    MERGE --> PROV
    REJECT --> PROV

    classDef ext fill:#e6f4ea,stroke:#1e7e34;
    classDef inf fill:#efe6fa,stroke:#7d3cc9;
    classDef anl fill:#e9eef2,stroke:#4a6072;
    classDef res fill:#e8f0fe,stroke:#1a5fb4,stroke-width:2px;
    classDef hitl fill:#fff3cd,stroke:#b8860b,stroke-width:2px;
```

**Reversibility.** Because every merge is logged with its decider and score, a later human can split a wrongly-merged entity by superseding the merge row — the canonical id is stable but the membership is versioned. Cross-party merges (linking the user and the partner to a shared person/location) are always HITL, since they can carry strategic weight.

---

### 18.5 Data-store responsibility diagram

**This diagram is mandated to show the exact four-resource topology** (CONTEXT_PACK §1 / §6 HARD CONSTRAINT): **ONE unified box** "Postgres + PostGIS + pg_duckdb", and **three separate boxes** Milvus / Neo4j / SurrealDB — each labeled **independently restartable** (no shared lifecycle, separate bind-mounted volumes). DuckDB and PostGIS are drawn *inside* the unified box and are never standalone deployables.

```mermaid
flowchart TB
    subgraph R1["RESOURCE 1 — INDEPENDENTLY RESTARTABLE (bind-mounted volume)"]
        direction TB
        PGCORE["PostgreSQL 18 (agno-postgres:18-duckdb)<br/>relational SSOT: messages, timeline_event,<br/>people, evidence, provenance, custody,<br/>approvals, entity_resolution_log"]
        POSTGIS["PostGIS (in-image)<br/>geometry/geography, location_key geom,<br/>spatial joins"]
        PGDUCK["pg_duckdb (in-image)<br/>analytical/OLAP + R2/S3 file & Parquet reads<br/>(account-wide S3 secret)"]
        PGCORE --- POSTGIS
        PGCORE --- PGDUCK
    end

    subgraph R2B["RESOURCE 2 — INDEPENDENTLY RESTARTABLE (bind-mounted volume)"]
        MILVUS["Milvus (ADR-0027)<br/>vectors/ANN: 1 collection per embedder<br/>hybrid dense + sparse/BM25<br/>code index + Case Bible + evidence text"]
    end

    subgraph R3["RESOURCE 3 — INDEPENDENTLY RESTARTABLE (bind-mounted volume)"]
        NEO["Neo4j community (ADR-0014)<br/>bitemporal cognition graph<br/>writers: Graphiti MCP + Semantica<br/>valid+knowledge-time, disclosure-tier"]
    end

    subgraph R4["RESOURCE 4 — INDEPENDENTLY RESTARTABLE (bind-mounted volume)"]
        SURREAL["SurrealDB (ADR-0024, Phase D)<br/>consolidated analysis sink<br/>native bitemporal multi-model<br/>(PG -> Surreal downstream)"]
    end

    R1 -. "no shared lifecycle" .- R2B
    R2B -. "no shared lifecycle" .- R3
    R3 -. "no shared lifecycle" .- R4

    classDef res fill:#e8f0fe,stroke:#1a5fb4,stroke-width:2px;
    classDef inner fill:#f4f8ff,stroke:#1a5fb4,stroke-dasharray:3 3;
    class MILVUS,NEO,SURREAL res;
    class PGCORE inner;
    class POSTGIS,PGDUCK inner;
```

| Resource | Owns (system of record for) | Reads from | Restart blast radius |
|---|---|---|---|
| **1. Postgres + PostGIS + pg_duckdb** (unified) | Relational SSOT, spatial geometry, OLAP/Parquet/R2 SQL reads, provenance & custody, approvals | R2 via pg_duckdb S3 secret | Self only — Milvus/Neo4j/Surreal keep running |
| **2. Milvus** (separate) | Dense+sparse vectors / ANN search | Raw docs (source of truth) | Self only |
| **3. Neo4j** (separate) | Bitemporal cognition graph (entities, edges, contradictions) | PG canonical ids; written by Graphiti + Semantica | Self only |
| **4. SurrealDB** (separate, Phase D) | Consolidated bitemporal analysis sink | PG→Surreal pipeline | Self only |

A crash or rebuild of any one box **must never** tear down the others — this is the corrective to the prior single-Coolify-app coupling (CONTEXT_PACK §1, infra split decision).

---

### 18.6 Multi-pass analysis flow

The disclosure-tier multi-pass model (ADR-0031): evidence is analyzed in escalating passes, each pass adding interpretation **without overwriting** lower passes, and each sensitive escalation gated by human review. Mirrors the lane discipline raw → extracted → inferred → analytical → legal.

```mermaid
flowchart TB
    P0["PASS 0 — RAW intake<br/>byte-preserved evidence + custody anchor"]:::raw
    P1["PASS 1 — EXTRACTION<br/>parse, OCR, NER, geocode, timestamp+precision"]:::ext
    P2["PASS 2 — STRUCTURING<br/>entity resolution, timeline_event, relational links"]:::ext
    P3["PASS 3 — INFERENCE<br/>anomalies, home_base, gaps, relationship-cycle phase<br/>(positive/neutral/love-bombing/repair AND negative)"]:::inf
    P4["PASS 4 — ANALYTICAL<br/>contradiction sets (CONTRADICTS edges),<br/>confidence tiers HIGH/MED/LOW,<br/>both-parties conduct in temporal context"]:::anl
    G1{"Sensitive label proposed?<br/>(gaslighting, coercive control,<br/>alienation, weaponization,<br/>reactive abuse)"}:::hitl
    P5H["PASS 5 — HITL legal review<br/>hypothesis stays hypothesis until approved<br/>court-safe wording, MCL factor mapping"]:::hitl
    P5["PASS 5 — LEGAL labeling<br/>evidence-linked relevance labels<br/>(append-only, versioned)"]:::legal
    EXP["Court-facing export<br/>vw_forensic_evidence_package"]:::legal

    P0 --> P1 --> P2 --> P3 --> P4 --> G1
    G1 -- "yes" --> P5H -- "approved" --> P5
    G1 -- "no / neutral fact" --> P5
    P5 --> EXP

    P1 -. "preserves" .-> P0
    P2 -. "preserves" .-> P1
    P3 -. "preserves" .-> P2
    P4 -. "preserves" .-> P3

    classDef raw fill:#fde8e8,stroke:#c0392b;
    classDef ext fill:#e6f4ea,stroke:#1e7e34;
    classDef inf fill:#efe6fa,stroke:#7d3cc9;
    classDef anl fill:#e9eef2,stroke:#4a6072;
    classDef legal fill:#dceffb,stroke:#0b6aa2,stroke-width:2px;
    classDef hitl fill:#fff3cd,stroke:#b8860b,stroke-width:2px;
```

**Guarantees encoded here.** (1) Each pass is append-only and points back to the pass it was derived from (`preserves` edges) → full artifact lineage to source evidence, prompt/ontology/schema version, and review decision. (2) The relationship-cycle (positive/neutral/love-bombing/repair) is modeled in Pass 3 alongside negative incidents — sentiment is never one-sided. (3) Both parties' conduct, including the user's own reactions/escalations/apologies, is evaluated in temporal context in Pass 4. (4) No hypothesis becomes a legal label without passing the Pass-5 HITL gate.

---

### 18.7 Evidence-to-legal-issue mapping flow

How a piece of raw evidence becomes a court-facing claim tied to a legal issue (e.g., an MCL 722.23 best-interest factor) — with confidence, corroboration status, and strategic-risk flags surfaced explicitly. Uses the adopted `mcl_722_23.ttl` (12 MCL factors) and `vw_forensic_evidence_package` tiers (CONTEXT_PACK §3).

```mermaid
flowchart TB
    EV["Evidence node (RAW)<br/>provenance anchor + custody hash"]:::raw
    FACT["Extracted/structured fact<br/>(statement, event, location, message)"]:::ext
    CORR{"Corroborated?<br/>(>=2 independent sources)"}:::anl
    SUPPORT["Supports / contradicts links<br/>(CONTRADICTS edges for impeachment)"]:::anl
    ISSUE["Legal issue mapping<br/>mcl_722_23.ttl -> factor A..L<br/>(map-entities / mcl-factor-mapper)"]:::analytical
    TIER["Confidence tier<br/>HIGH / MED / LOW"]:::anl
    FLAGS["Strategic flags:<br/>- emotionally important, may not be legally useful<br/>- needs corroboration before use<br/>- dangerous without context (selective framing)"]:::anl
    HR["HITL legal-relevance review"]:::hitl
    PKG["vw_forensic_evidence_package<br/>(review-ready factual summary,<br/>court-safe wording, NOT legal advice)"]:::legal

    EV --> FACT --> CORR
    CORR -- "yes" --> SUPPORT
    CORR -- "no" --> FLAGS
    SUPPORT --> ISSUE --> TIER --> FLAGS --> HR
    HR -- "approved" --> PKG
    HR -- "hold / needs corroboration" --> FACT

    classDef raw fill:#fde8e8,stroke:#c0392b;
    classDef ext fill:#e6f4ea,stroke:#1e7e34;
    classDef anl fill:#e9eef2,stroke:#4a6072;
    classDef analytical fill:#e9eef2,stroke:#4a6072;
    classDef legal fill:#dceffb,stroke:#0b6aa2,stroke-width:2px;
    classDef hitl fill:#fff3cd,stroke:#b8860b,stroke-width:2px;
```

| Mapping attribute | Source | Purpose |
|---|---|---|
| Legal issue / factor | `mcl_722_23.ttl` (A–L) via mcl-factor-mapper | Ties evidence to a recognized best-interest factor |
| Confidence tier | `vw_forensic_evidence_package` (HIGH/MED/LOW) | Sets weight & disclosure posture |
| Corroboration status | ≥2 independent sources rule | Gates standalone assertion |
| Strategic-risk flag | Analytical pass | Surfaces "emotionally important but not legally useful" and "dangerous without context" |
| Court-safe wording | Pass-5 HITL | Favors "structure, safety, clarity, child stability" framing over blame |

The export is explicitly a **review-ready factual summary, not legal advice** — every mapped claim carries its confidence tier, corroboration status, and the human reviewer's sign-off (append-only), so any court-facing assertion is traceable back to the raw evidence and the decision that approved it.

---

### 18.8 Diagram-to-decision traceability

| Diagram | Primary ADR / source adopted | Key constraint satisfied |
|---|---|---|
| 18.1 System architecture | 0007/0013/0014/0015/0024/0025/0027/0030/0032 | Four-resource tier; cloud vs local-evidence split |
| 18.2 Ingestion pipeline | Salvaged parsers + normalized_messages + UUIDv7/SHA-256 (CONTEXT_PACK §3) | RAW preserved; provenance & custody on every row |
| 18.3 Temporal inference | TraceIQ timeline + ADR-0018/0031 | Exact/approx/inferred/uncertain precision class |
| 18.4 Entity resolution | salem_v3 Person MERGE + TraceIQ location_key | Reversible, logged, alias-preserving merges |
| 18.5 Data-store responsibility | CONTEXT_PACK §1 HARD CONSTRAINT | Unified PG box + 3 separate, independently restartable |
| 18.6 Multi-pass flow | ADR-0031 disclosure-tier + lane discipline | Append-only passes; HITL before sensitive labels |
| 18.7 Evidence→legal mapping | mcl_722_23.ttl + vw_forensic_evidence_package | Court-safe, corroboration-gated, lineage-preserving |
