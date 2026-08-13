# AI-chat ingestion: before and after ADR-0053

> _Byline: Codex · GPT-5 · 2026-08-13_

The interactive companion is
[`mockups/designs/chat_ingest_comparison/index.html`](../../mockups/designs/chat_ingest_comparison/index.html).

## Workflow

```mermaid
flowchart LR
  subgraph BEFORE[Before: main / migrations 0021-0023]
    B1[Archive or file] --> B2[Parse to NormalizedRecord]
    B2 --> B3[(working.context_record)]
    B3 --> B4[Poll nullable sync stamps]
    B4 --> B5[Chunk during projection]
    B5 --> B6[context Weaviate + Graphiti]
  end
  subgraph AFTER[After: migration 0024 + ADR-0053]
    A1[Archive + every payload] --> A2[Coverage route: Go or Python]
    A2 --> A3[(conversation + ordered message)]
    A1 --> A4[(original assets in R2 + PG index)]
    A3 --> A5[(message-safe canonical chunk)]
    A5 --> A6{post-chunk multi-label classifier}
    A6 -->|high confidence| A7[auto accepted]
    A6 -->|ambiguous or failed| A8[context + review queue]
    A7 --> A9[one embedding reused per lane]
    A8 --> A9
    A9 --> A10[platform / legal / personal_history / context]
    A5 --> A11[async entity / claim / time / event candidates]
    A11 --> A12[human investigation register]
    A12 -->|explicit human promotion| A13[analysis.timeline_event]
  end
```

## Schema responsibility shift

| Concern | Before | After |
|---|---|---|
| Raw chat truth | generic `working.context_record` | `chat_conversation` → `chat_message` |
| Ordering | implicit/timestamp | `message_index` |
| Role | retained | retained |
| Participants | optional normalized field | not stored in chat landing |
| Chunk | computed during projection | canonical `chat_chunk` + provenance join |
| Classification | context only | post-chunk multi-label `chat_chunk_lane` |
| Taxonomy | six-lane docs / context implementation | five global lanes; chat uses four |
| Uncertainty | no classification review | selective confidence HITL; context fallback |
| Embedding | repeated by Agno insert calls | once per chunk/embedder, reused across lanes |
| Tags | ad hoc metadata | normalized vocabulary + reviewed assignments |
| Assets | inventoried/basic index | every payload, message links, derivations, OCR state |
| Delivery | polling/sync stamps | per-table outbox + NOTIFY + cursors + dead letter |
| Candidate events | no curated intermediate | human investigation register |
| Horizons | absent from chat rows | still absent; agent retrieval/walk design later |

## Five-lane boundary

```mermaid
flowchart TB
  C[AI-chat chunk] --> P[platform]
  C --> L[legal]
  C --> H[personal_history incl. relationships]
  C --> X[context / ambiguity fallback]
  E[Custody-approved primary source] --> V[evidence]
  C -. forbidden .-> V
```

The migration is additive and is not applied to a live database by this branch. See
ADR-0053 for the governing decision and the HTML report for expandable table maps.
