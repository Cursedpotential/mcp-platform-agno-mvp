# Layer 3 — Features

> _Byline: Claude Code · Opus 4.8 · 2026-08-11; ADR-0053 amendment Codex · GPT-5 ·
> 2026-08-13._ User-facing flows + feature hierarchy. Backend
> platform (SBV has its own GUI); no wireframes. Knowledge-base-first is the sequencing (ADR-0051).

## 1. Primary flow — one conversation becomes a timeline

The owner's north star: process a conversation → build the timeline → learn what evidence to find.

```mermaid
sequenceDiagram
    actor Op as Operator
    participant SBV as SBV (parse+preview)
    participant PG as Postgres (records)
    participant EX as Extract (chunk→entities)
    participant TL as Graphiti timeline
    participant Op2 as Operator (HITL)
    Op->>SBV: upload conversation export
    SBV->>SBV: parse + preview (custody: light tier)
    SBV->>PG: normalized_record per message
    PG->>EX: (triggered) chunk + multipass extract
    EX->>TL: entities + events → timeline
    EX-->>Op2: candidates for verification
    Op2->>TL: approve / correct (native @approval)
    TL-->>Op: queryable timeline → "what evidence do I need?"
```

## 2. Feature hierarchy

```mermaid
mindmap
  root((Platform))
    Ingest
      SBV parse plus preview
      one pipeline - custody tier is the only branch
      knowledge-base FIRST, evidence second
    Knowledge
      five lanes platform legal personal_history context evidence
      one chat maps to many lanes at segment level
      chunking via Chonkie and chunking_policy
    Timeline_and_entities
      Graphiti and Neo4j
      multipass extraction via Semantica
    Custody_and_trust
      H1 H2 H3 canonical in pkg custodyhash
      HITL verify before canonical
      audit-everything ledger
    Access
      agents per lane - CLI to MCP to agents
      Timeline and Takeout PARKED
```

## 3. The evidence/context branch (custody tier)

The single fork in the pipeline — everything else is shared.

```mermaid
flowchart TB
    ANY["any material"] --> Q{"evidence or context?"}
    Q -->|evidence| FULL["FULL custody chain (H1/H2/H3)<br/>evidence lane, horizon-gated"]
    Q -->|context| LIGHT["LIGHT custody<br/>context + domain lanes"]
    FULL --> SHARED["same parse → chunk → extract → verify"]
    LIGHT --> SHARED
```

## Open Questions
- HITL-after-extraction gate — the extraction stage it verifies is not built yet (ADR-0051).
- Segment→lane classification (the multipass step that makes "one chat → many lanes" real) is the
  gap the current single-lane context ingest still has (D-045). It consumes the chunks from the
  `chunking_policy` seam.
