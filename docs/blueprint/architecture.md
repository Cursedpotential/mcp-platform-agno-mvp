# Layer 1 — Architecture

> _Byline: Claude Code · Opus 4.8 · 2026-08-11 · reverse+forward, hybrid;
> drift-fix 2026-08-12 (Claude Code · Kimi K3): "PG change-detection not built" claims updated — partially built per D-048._
> Stable architecture (ADR-0051 target, ADR-0050 lanes, deploy topology) is drawn as the primary
> view. Build STATUS moves daily — for live phase status see `docs/COORDINATION.md` (war-room) and
> `docs/DECISION_LOG.md`, not this diagram.

## 1. System context

Who and what feeds the platform, and what it produces.

```mermaid
flowchart LR
    subgraph Sources
      EV["Evidence files<br/>(SMS/MMS, email, docs)"]
      AC["AI-chat exports<br/>(ChatGPT/Claude/Gemini)"]
      R2["Cloudflare R2 lakehouse<br/>(wiring unverified)"]
      %% UNVERIFIED: R2 -> PG/DuckDB wiring is owner-stated, not confirmed in code
    end
    OP(["Operator<br/>(single user, HITL)"])
    subgraph Platform["Agno-MCP-Platform"]
      ING["Ingest pipeline"]
      KB["Six-lane knowledge"]
      TL["Timeline / entities"]
      AG["Agent families"]
    end
    EV --> ING
    AC --> ING
    R2 -. bulk via pg_duckdb .-> ING
    ING --> KB
    ING --> TL
    OP -- approves/verifies --> ING
    AG -- query --> KB
    AG -- query --> TL
    OP -- asks --> AG
```

## 2. Data-flow — TARGET pipeline (ADR-0051)

The intended flow. One pipeline for everything; custody tier is the only evidence/context branch.

```mermaid
flowchart TB
    F["source file (any format)"] --> DD["DuckDB: cache + UUID + catalog link"]
    DD --> SBV["SBV: parse + PREVIEW (Go fork) — then HANDS OFF"]
    SBV --> PG[("Postgres<br/>working.normalized_record<br/>(source of truth)")]
    %% Updated 2026-08-12 (D-048): partially built — the context lane's change-detection-SHAPED
    %% consumer (`ingest.context-drain`, pending-row polling) exists; the full trigger/outbox/
    %% cursor CDC spine stays DEFERRED (ADR-0051 invariant 4; spine design = ADR-0052, queued)
    PG -->|"PG change-detection (partial — pending-row polling, D-048; full CDC spine deferred)"| FAN{{"fan-out triggered"}}
    FAN --> CH["chunk (Chonkie via chunking_policy)"]
    CH --> EX["multipass extract + artifacts (Semantica)"]
    EX --> EN["entities + timeline (Graphiti/Neo4j)"]
    CH --> WV["embed → six Weaviate lanes"]
    EN --> HITL["HITL verify (native @approval)"]
    WV --> HITL
    HITL --> CANON["canonical knowledge + timeline, per lane"]
```

## 3. Data-flow — CURRENT state (dated snapshot 2026-08-11)

What exists today differs from the target: two lanes of work, converging. **Live status is in the
war-room, not here.**

```mermaid
flowchart TB
    subgraph KBLane["KB-structure lane (Lane D) — Phases 1-3 shipped"]
      W1["custody → parse → store → knowledge"]
      W1 --> SIX["six lanes registered + lane vocab live<br/>(platform/legal re-ingested)"]
    end
    subgraph PCLane["Parser/chunking lane (this chat)"]
      P1["SBV = primary parser (ADR-0049)"]
      P2["Chonkie chunkers → Agno (chunking_policy seam, WIRED by Lane D)"]
      P3["custody hashing decoupled → pkg/custodyhash"]
    end
    GAP["NOT built yet: full CDC spine (context-lane pending-row polling shipped 2026-08-12, D-048) · Semantica wired · AI-chat Go decoders beyond ChatGPT · HITL-after-extract"]
    KBLane -. converging on ADR-0051 .-> GAP
    PCLane -. converging on ADR-0051 .-> GAP
```

## 4. Deployment topology (live 2026-08-11)

Two OVH boxes over Tailscale + Coolify. ⚠ statuses change — verify against Coolify/`COORDINATION.md`.

```mermaid
flowchart LR
    subgraph ovhapp["ovh-app 100.72.169.40 (exec tier)"]
      API["agentos-api"]
      SBVc["platform-tools (SBV)"]
      CF["contextforge (MCP gateway)"]
      PK["portkey (model gateway)"]
    end
    subgraph ovhfiles["ovh-files 100.91.190.107 (data tier)"]
      DB[("agentos-db / Postgres")]
      WV[("Weaviate — 6 lanes")]
      NEO[("Neo4j + Graphiti")]
      MV[("Milvus — DOWN, deliberate")]
    end
    API --> DB
    API --> WV
    API --> SBVc
    API --> NEO
    API --> CF
    API --> PK
```

## Open Questions
- `%% UNVERIFIED` R2 lakehouse → PG/DuckDB wiring mechanism (owner-stated; not confirmed in code).
- ~~`%% UNVERIFIED` PG change-detection — does not exist yet; forward-only (ADR-0051).~~ **Updated 2026-08-12 (D-048):** partially built — the context lane's projection is change-detection-SHAPED (`ingest.context-drain` reads rows `WHERE <sink>_synced_at IS NULL` and stamps them; CLI + registered tool). The generic trigger/outbox/cursor spine for ALL paths remains DEFERRED (ADR-0051 invariant 4; spine design = ADR-0052, queued/not yet drafted).
- exec-tier (ovh-app) was DOWN 2026-08-10 (VPS/bill) — topology shows intended state; verify live.
