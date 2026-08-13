---
plan name: chat-ingest-pipeline
plan description: Five-lane, PG-first AI-chat and multimodal-work ingestion
plan status: implementation
---

> _Byline: Codex · GPT-5 · 2026-08-13_

## Accepted target

Ingest a chat export as one unit: preserve its original archive, ordered conversations,
messages, generated works, and attachments; create message-safe chunks; classify each chunk
into zero or more of `platform`, `legal`, `personal_history`, and `context`; then project
durably. AI chat cannot route to `evidence`.

Classification happens after chunking. A multi-lane chunk is stored once and embedded once;
the vector is reused in each eligible collection. Ambiguity or failure remains searchable in
`context` and is queued for selective HITL. Relationship history is part of
`personal_history`; normalized tags supply finer search facets.

## Implementation status

- [x] Explicit conversation, message, chunk, provenance, lane-review, embedding, projection,
  tag, multimodal-asset, outbox/cursor/dead-letter, and investigation-register schema in
  additive migration 0024.
- [x] Coverage-based Go/Python parse route and strict operator overrides.
- [x] Deterministic message-window baseline plus optional Chonkie semantic and TeraflopAI
  challengers.
- [x] Post-chunk multi-label keyword baseline with confidence-driven context fallback.
- [x] One-vector/multi-collection Weaviate projection using Agno-compatible object fields.
- [x] Whole-archive asset materialization and lightweight-first text extraction seam.
- [x] Optional Docling extractor; VLM provider deliberately configurable and not selected yet.
- [ ] Apply migration 0024 to a disposable validation database, then owner-approved live DB.
- [ ] Implement the always-on CDC worker, replay tool, dead-letter alert, and review UI.
- [ ] Evaluate chunker/classifier/OCR variants against human-labeled representative samples.
- [ ] Add entity/claim/time/event extraction and investigation-register UI.
- [ ] Design as-experienced versus hindsight walk tables/views after timeline population.

## Operator entry

`uv run --no-sync python scripts/ingest_context_chat.py <export-or-zip> --dry-run`

Remove `--dry-run` only after migration 0024 is applied. Use `--no-project` to land PG truth
without draining projections. Colab through MCP is a backup execution target, not a runtime
dependency. See ADR-0053.
