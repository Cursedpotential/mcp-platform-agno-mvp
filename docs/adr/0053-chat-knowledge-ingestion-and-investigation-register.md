# ADR-0053: Five-lane chat knowledge ingestion, selective review, and investigation register

> _Byline: Codex · GPT-5 · 2026-08-13_

- Status: **Accepted** — owner rulings across the 2026-08-13 design review
- Date: 2026-08-13
- Supersedes in part: ADR-0050 (six-lane taxonomy), ADR-0051 (AI-chat landing and
  classification details), ADR-0052 (the `context_record` realization for AI chat)
- Preserves: ADR-0044 evidence/context boundary, ADR-0045 horizon-at-agent-layer,
  ADR-0052 transactional outbox + NOTIFY + per-sink cursor design

## Context

The first PG-first AI-chat implementation proved parsing and projection, but stored
messages in a generic `working.context_record` table and treated the whole chat as one
context lane. A subsequent OpenCode proposal improved conversation/message structure but
mixed raw content, classification, review, and projection state, classified before
chunking, and retained a six-lane taxonomy whose relationship and personal-history lanes
were too difficult to distinguish consistently.

The platform first needs to ingest a very large, messy body of chats and created works so
the owner can determine what happened and when. As-experienced versus hindsight walks are
a later analytical design. Extraction may read everything but forms no beliefs, and raw AI
chat is never evidence.

## Decision

### 1. Five global knowledge lanes

The canonical lane vocabulary is:

| Lane | Purpose | AI-chat auto-routing |
|---|---|---|
| `platform` | platform design, code, operations | yes |
| `legal` | law, procedure, strategy, created legal work | yes |
| `personal_history` | personal and relationship history | yes |
| `context` | general, ambiguous, or unclassified chat knowledge | yes |
| `evidence` | custody-approved primary material only | **never** |

`relationship_timeline` is retired as a destination and merged into
`personal_history`. Relationship-specific concepts remain expressible through normalized
tags and later entity/event extraction.

### 2. Raw chat landing is explicit and horizon-neutral

`working.chat_conversation` is the parent and `working.chat_message` is the ordered child.
Messages retain `role`; a separate participants model is not stored. Neither raw table
carries a lane, horizon, disclosure, as-experienced, or hindsight judgment.

The original archive bytes and all attachments/generated works are retained through
`working.context_archive` and `working.context_asset`. R2 holds original bytes; PG holds
identity, provenance, extraction state, and links to messages.

### 3. Chunk first, then classify; multi-label without duplicate canonical content

Message-safe chunks are persisted in `working.chat_chunk` with exact message provenance in
`working.chat_chunk_message`. Classification happens after chunking because one chat and
one chunk may cross several domains. `working.chat_chunk_lane` stores one or more lane
assignments per chunk.

A chunk that crosses two lanes is not duplicated in PG and is not embedded twice. Its
content is embedded once per embedder; the same vector is projected into each eligible
lane collection. Separate Weaviate collections remain a structural isolation boundary,
especially for evidence.

### 4. Selective HITL by confidence

Classification status is one of `auto_accepted`, `pending_review`, `human_approved`,
`human_corrected`, or `classification_failed`.

- High-confidence assignments are projected automatically and may enter sampled audit.
- Ambiguous assignments are immediately searchable in `context` and queued for review.
- Classifier failures also land in `context` with an error/review record.
- Nothing is discarded because a classifier is uncertain or unavailable.

The initial keyword classifier is a deterministic baseline, not the final semantic model.
Remote or LLM classifiers plug into the same versioned seam and must be evaluated against a
human-labeled set before replacing the baseline.

### 5. Tags are normalized search facets

Broad lanes answer “which corpus?”; tags answer “what is this about?”. Tags live in
`reference.knowledge_tag` and assignments in join tables with provenance, confidence, and
review state. Tags are not comma-separated strings and are not only unvalidated JSON.

### 6. Created works and attachments are multimodal sources

All archive payloads are inventoried and materialized, including provider files outside an
`assets/` directory. Each asset keeps modality, MIME type, source archive, hash, and message
links. Searchable representations are derived assets linked to their originals.

The extraction ladder is provider-plural and resource-aware:

1. native/lightweight text extraction or OCR first;
2. Docling for layout-aware documents, tables, and harder OCR;
3. a vision-capable model for unresolved/low-confidence material;
4. Google Colab through MCP only as an operator-triggered backup, never a runtime dependency.

No Mistral, Kimi, GLM, or other OCR/VLM provider is locked by this ADR. Provider, version,
confidence, and derivation provenance are recorded. Audio/video follow the same pattern via
transcript and keyframe representations. Multimodal embeddings are projections, not a
replacement for preserved originals and extracted text.

### 7. Extraction and investigation are asynchronous, human-governed stages

Entity, claim, time, and event-candidate extraction runs after landing/chunking through the
ADR-0052 CDC spine. It is not required to finish ingestion and does not promote facts by
itself. Bulk timeline consolidation comes after enough material is ingested.

`working.investigation_event` is a human-curated register for concerns or candidate events
worth investigating. It links to chat chunks/candidates, evidence needs, primary evidence,
and tags. Only an explicit human act may promote an entry to `analysis.timeline_event`.

As-experienced versus hindsight walk tables/views are deliberately deferred to their own
design. The horizon remains an agent retrieval permission/filter, never an extraction lane.

### 8. Delivery remains durable and replayable

Each source table gets a full-row transactional outbox. PostgreSQL `NOTIFY` is only a
wakeup. Every sink advances an independent durable cursor. Failures enter a dead-letter
table with replay state and must be visible to operators. Weaviate horizon filters remain
dict pre-filters; direct unrestricted search utilities are prohibited.

## Consequences

- The landing model matches the source without premature beliefs.
- Relationship and personal material no longer require an unreliable forced distinction.
- Cross-lane routing increases vector objects but not embedding computation.
- Ambiguous knowledge stays discoverable while preserving a review trail.
- OCR/VLM costs are controlled by escalation instead of applying the heaviest model to every
  asset.
- Timeline and horizon work can evolve without rewriting the original chat corpus.

## Deferred work

- Build the always-on CDC worker, replay command, dead-letter alert, and sampled audit UI.
- Evaluate Chonkie message-safe semantic chunking and the optional TeraflopAI endpoint against
  the deterministic baseline; VPS CPU is primary and hosted/Colab inference is optional.
- Select and benchmark OCR/VLM providers, including privacy/cost/quality on representative
  owner data.
- Implement entity/claim/time/event candidates and the human investigation-register UI.
- Design the as-experienced versus hindsight walk after temporal extraction is populated.
