# Layer 2 — Structure

> _Byline: Claude Code · Opus 4.8 · 2026-08-11._ Data model + component structure. Sources:
> ADR-0050 (six-lane KB), `server/tools/registry.py` (parser registry), `vendored/sbv/` (Go engine
> + `pkg/custodyhash`), ADR-0050 §7 (agent→lane).

## 1. Six-lane knowledge model (ADR-0050)

Each lane is its OWN Weaviate collection + Postgres contents table (schema `ai`) — isolation is
structural, not filter-dependent. One embedder for now (`nv-embed-v1`, 4096-d).

```mermaid
erDiagram
    LANE ||--|| WEAVIATE_COLLECTION : "one each"
    LANE ||--|| PG_CONTENTS_TABLE : "one each"
    LANE ||--o{ CHUNK : contains
    CHUNK }o--|| SOURCE : "derived from"
    LANE {
      string name "one of the six lanes"
    }
    CHUNK {
      string lane "exactly one of six"
      string doc_type "transcript doc note rubric motion sms chat"
      string source
      string case_id "always primary"
      string visible_from "evidence lane only, ADR-0045"
    }
    SOURCE {
      string sha256 "H1 custody"
      string original_filename
    }
```

Evidence lane is special: written ONLY by custody-approved records; read ONLY through the
horizon-gated seam (`server/evidence/retrieval.py`); no agent holds its raw handle.

## 2. Parser registry + dispatch

No central list — parsers self-register on import; the workflow resolves by capability.

```mermaid
flowchart TB
    REG["@register(id, capability, accept)"] --> RG["ToolRegistry (registry.py)"]
    LB["load_builtin_tools() — walks server/tools/"] --> RG
    RG -->|"resolve(capability, media_hint, size)"| DISP["parse_step: try primary → pause (no silent fallback)"]
    subgraph Parsers
      GO["SBV Go engine: 12 decoders<br/>(sms_xml, facebook_json, google_chat,<br/>google_voice_html, mbox, eml, ...)"]
      PYm["Python messaging: 9"]
      PYa["Python ai_chat: 11"]
      PYg["Python generic: 2"]
    end
    DISP --> GO
    DISP --> PYm
    DISP --> PYa
    DISP --> PYg
```

## 3. Custody hashing (decoupled — `pkg/custodyhash`)

One canonical construction; every caller binds to it (D-047).

```mermaid
flowchart LR
    subgraph pkg["pkg/custodyhash (canonical)"]
      H1["HashFileH1 (h1-rawbytes-v1)"]
      H2["HashRecordH2 (h2-rawelement-v1)"]
      H3["ChainH3 / Chain / FoldChain<br/>(h3-chain-sbv-genesisempty-v1)"]
    end
    INT["internal/custody.go (shims)"] --> pkg
    ENG["internal/engine.go (streaming fold)"] --> pkg
    PY["Python custody.py — H1 cross-check"] -. must agree .-> H1
    %% UNVERIFIED: non-Go callers (PG/DuckDB/FastAPI mirror) are a follow-up, not built
    FUT["PG/DuckDB/backup/FastAPI mirror<br/>follow-up, not built"] -. binds to .-> pkg
```

## 4. Agent → lane wiring (ADR-0050 §7)

One primary lane per family; cross-lane via team members, not custom retrievers.

```mermaid
flowchart LR
    LEGAL["Legal family"] --> Llegal["legal"]
    LEGAL --> Lev["+ Evidence Analyst (horizon-gated)"]
    LEGAL --> Lrt["+ relationship_timeline"]
    ANALYSIS["Analysis family"] --> Art["relationship_timeline"]
    ANALYSIS --> Aph["+ personal_history"]
    BUILDER["Builder/Dev"] --> Bp["platform"]
    DIGEST["Digest/Recall"] --> Dc["context"]
```

## Open Questions
- `%% UNVERIFIED` non-Go custodyhash callers (PG/DuckDB/FastAPI mirror) — follow-up, not built.
- Agent→lane wiring is ADR-0050 Phase 4 — verify against `server/agents/factory.py` when shipped.
