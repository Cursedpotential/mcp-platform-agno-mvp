## Overview

> _Naming: written before the 2026-09-05 rename (D-137..D-141); see docs/NAMING.md for the old->new glossary._

This analysis cross-references the project's existing eDiscovery/forensic research (`edisc.md`, `conversation_ingestion_system_design.md`, `archive-triage-parser-schema-lineage-2026-08-09.md`, `VLEX-RESEARCH-PROMPTS.md`) against three live GitHub repositories — `mcp-platform-agno-mvp` (the evidence spine), `Legal-Workspace` (the sibling legal-strategy app), and `sbv-forensic` (the SMS Backup Viewer) — to identify concrete gaps, redundancies, and near-term opportunities specific to document handling, searching, and evidence bundling for the Salem v. Kinzel matter.[^1][^2]

The three repositories represent a deliberately split architecture: `mcp-platform-agno-mvp` owns evidence ingestion, custody, and the bitemporal analysis schema; `Legal-Workspace` owns legal strategy, drafting, and filing preparation and explicitly consumes evidence via API rather than a shared writable store; and `sbv-forensic` is a narrow, self-hosted SMS/MMS/call-log viewer that feeds the parser layer. This split is architecturally sound but currently produces integration seams that are the largest source of gaps identified below.

## Document Handling: What Exists vs. What Is Missing

The evidence spine already inventories an unusually complete document-intelligence layer through the dial-stack donor corpus: eleven OCR/format engines (Tesseract, Docling, docTR, OCRopus, Pandoc, Unstructured, GLM-OCR, LlamaParse, AWS Textract, Google DocAI, IBM watsonx) behind a unified `DocumentEngine`/`EngineRegistry` abstraction with cost-tier and locality-based fallback chains. Five of these (Tesseract, Docling, docTR, Pandoc, Unstructured) are fully functional without cloud credentials, which matters for a case where data sovereignty and cost control are priorities.

| Capability | Status | Location |
|---|---|---|
| Multi-engine OCR/document intelligence | Designed, not yet wrapped as callable MCP service | dial-stack donor corpus |
| SMS/MMS/iMessage/Facebook parsing with custody hashing | Live, committed 2026-08-07 | `server/tools/parsers/` in agno-mvp[^3] |
| AI-chat transcript parsing (ChatGPT, Claude, Gemini, Perplexity) | Live, 12 registered parsers, API bug fixed | vendored `chatminer`[^3] |
| Generic document parsing (PDF, DOCX, HTML, email, JSON, CSV, XML, Excel, PPTX) | Built but has zero runtime call sites | vendored `semantica`[^3] |
| WhatsApp/.txt or media-zip import | Not built anywhere across archives or live repo | Confirmed gap[^3] |
| Native `chat.db` SQLite parser (iOS Messages) | Not built | Confirmed gap[^3] |
| Standalone call-log parser (independent of SMS-XML lane) | Not built | Confirmed gap[^3] |
| Deleted-message recovery from WAL journals | Built (`sqlite_wal_parser.py`), not yet ported to live repo | dial-stack donor, flagged "forensic gold" |

The Semantica parser is the single biggest wasted asset in the document-handling layer: it is the most feature-complete document parser in the entire codebase (15 formats) yet has no runtime caller anywhere outside its own vendored tree. Wiring it into the ingestion pipeline would close most residual "we can't ingest this file type" risk without writing new parser code.[^3]

Separately, `sbv-forensic` — while functionally solid as a standalone SMS/MMS/call viewer with FTS5 full-text search, per-user SQLite isolation, and media handling for HEIC/3GP — stores media as base64 BLOBs inside a general-purpose `messages` table with no evidentiary hash field, no chain-of-custody column, and no export path into the `analysis.normalized_record` bitemporal schema that the rest of the project standardized on. Its own documentation flags a 100,000-message practical limit and Android-only support, meaning it functions today as a human-facing browsing tool rather than an evidence-pipeline component, and there is no visible bridge connecting SBV's SQLite output to the Go `internal/custody.go` hashing module the parser layer already uses.[^3]

## Search: What Exists vs. What Is Missing

The retrieval layer described in `edisc.md` proposes multi-layered, dual-granularity embeddings (isolated-fact plus surrounding-context chunks) with similarity-deviation cutoffs, directly citing a 2024 study showing this approach captures 37.86% of essential content chunks versus 16.39% for flat chunking. This design exists only on paper; none of the three repositories show an implemented retrieval-time filtering layer wired to a live vector store for the custody corpus specifically.[^1]

The dial-stack donor material independently proves out most of the needed search primitives, but they remain unwrapped:

- BM25 keyword retrieval plus hybrid BM25+embedding search with supporting-span extraction (`retrieval.ts`)
- Dual-backend vector store (Chroma + FAISS) and a separate pluggable Qdrant/pgvector/Chroma store with tiered TTL
- Forensic text-mining router that dispatches ripgrep vs ugrep by content type, with timeline extraction from timestamps
- A storage-tier router (`systemRouter.ts`) that promotes data from Chroma (Tier 1, ephemeral) to Postgres (Tier 2) to LanceDB (Tier 3) to Neo4j (Tier 4)

None of these are visible as live endpoints in `Legal-Workspace`'s API layer, which currently exposes routing, citation-gating, redaction, Bates numbering, and an eyecite legal-citation adapter, but no evidence-search or full-text query endpoint of its own — consistent with its stated design of consuming evidence via API rather than owning search. This means a lawyer using `Legal-Workspace` today has no in-app way to search the custody corpus; that capability, if it exists at all, sits only in the evidence spine or in SBV's standalone FTS5 index, which is disconnected from case-tagged Best Interest Factor metadata.

The largest search-related gap identified in `edisc.md` itself is standards-level rather than architectural: no eDiscovery vendor or standards body publishes a statistical validation method for RAG citation grounding equivalent to Technology-Assisted Review's recall/precision/elusion framework established since *Da Silva Moore v. Publicis Groupe* (2012). The proposed elusion-sampling port (stratified sampling of "grounded" citations, human verification, per-stratum elusion-rate calculation with a 2-3% threshold before any output reaches a filing) is well-specified but not yet implemented as code anywhere in the three repositories.[^1]

## Evidence Bundling: What Exists vs. What Is Missing

Evidence bundling spans custody/chain-of-custody, statutory tagging, and courtroom-ready export. Here the split between `mcp-platform-agno-mvp` (custody authority) and `Legal-Workspace` (drafting/filing) is clearest, and also where the most consequential gaps sit.

**Chain of custody.** The live bitemporal schema (`sql/0001`–`0018`) implements `analysis.normalized_record` with `occurred_at`/`knowledge_time`/`disclosure_tier` and evidence hashing, and the spine's `custody.py` is the sole append-only writer to the evidence schema. However, the strongest custody design available — dial-stack's Ed25519-signed, hash-linked chain-of-custody with a `verify_custody_chain` plpgsql function — has not yet been ported into the live spine; it remains an "open decision" in the spine's own merge-map document. The current live custody is SHA-256 hash-based but does not yet carry cryptographic signatures, which is a meaningful gap if custody chains are ever challenged on authenticity grounds rather than just integrity.[^3]

**Statutory tagging and courtroom export.** `edisc.md` fully specifies a 12-factor MCL 722.23 tagging schema and an 8-column courtroom matrix export (date/time, category, Best Interest Factor, factual description, quote/evidence summary, exhibit ID, contradicting testimony, admissibility source), plus a ninth `context_thread_id` field. `Legal-Workspace`'s domain layer includes Bates numbering, redaction, and DOCX export services, but there is no visible service module implementing the specific 8/9-column Best-Interest-Factor matrix format `edisc.md` calls for — the drafting layer is generic legal-document tooling, not yet wired to the custody-specific export shape.[^1]

**Behavioral-pattern reconciliation.** A significant asset exists but its deployment status is unverified: `docs/planning/forensic-db-reconciliation/migrations/0006_behavior_seed.sql` already merges nine fragmented behavioral-detection iterations (including the project's own TTL ontology files and `zep_salem_ontology_v3_final.py`), but the reconciliation report explicitly states this is still "DRAFT / paper-only... Nothing here has been applied or diffed against the running DB". This is flagged as the single most actionable next step across the entire archive triage — not re-extraction, but a live-database verification of what's actually deployed.[^3]

**Trained behavioral ML ("Tether").** The project's own trained abuse-detection models (18-label abuse classifier, DARVO regressor, boundary-health scorer, 140+ motif regexes under `SamanthaStorm/tether-*`) exist inside the dial-stack donor tree under a deliberately deferred `utilities/` directory and are not yet connected to the live pattern-analysis pipeline; the `user_detection.py` wrapper in the live-adjacent code is a placeholder, not the real model. This is a bundling gap in the sense that pattern-of-behavior evidence — the core of a coercive-control custody case — currently relies on a much thinner default rule set (four hardcoded regex patterns in `behavior-service.ts`) than the trained models that already exist but sit unwired.

**Legal citation verification.** `Legal-Workspace` has an `eyecite_adapter.py` and `citation_gate.py`, giving it native legal-citation parsing and gating. This should be treated as the natural home for extending the vLex verification-status taxonomy (`VERIFIED_PRIMARY`, `MIRROR_ONLY`, `BLOCKED`, `CONFLICTED`, etc.) from pure legal citations into RAG-generated factual claims about case evidence, as `edisc.md` recommends, but no evidence that this extension has been implemented was found in the repository.[^2][^1]

## Cross-Cutting Architectural Gaps

Several gaps span all three pillars rather than fitting cleanly into one:

- **No live bridge from SBV to the custody schema.** SBV is a complete, working viewer, but its SQLite output is architecturally isolated from `analysis.normalized_record`; messages viewed in SBV are not automatically evidence-hashed, Best-Interest-Factor-tagged, or searchable from `Legal-Workspace`.[^3]
- **Semantica and the dial-stack MCP plugin catalog (~100 tools) are inventoried but unwrapped.** The spine's own merge map treats wrapping dial-stack capabilities as MCP services as the confirmed target architecture, but as of the most recent triage this remains a design decision, not a shipped integration.
- **`Legal-Workspace` explicitly disclaims court-safety.** Its README states outright: "Do not treat this as court-safe," and flags its privilege-detection module (`PRIV`) as "keyword-only hypothesized markers, not a legal conclusion". This is an appropriate and honest caveat, but it means the elusion-sampling validation loop specified in `edisc.md` is a prerequisite — not an optional enhancement — before any bundled evidence output from this stack should be relied upon in a filing.[^1]
- **Duplicate/overlapping parser lineages remain unreconciled in places** (Gemini/Perplexity chat parser variants across ChatMiner and dial-stack, and a second FB/SMS/PDF loader set in `server/mcp/loaders/` that duplicates the more complete `ts-mcp-server` versions), representing low-risk technical debt rather than missing capability.[^3]

## Prioritized Opportunities

Ranked by leverage relative to effort, based on what is already built but unconnected versus what still needs to be built from scratch:

1. **Verify and, if needed, apply `0006_behavior_seed.sql` against the live database** — this is a verification task, not new development, and unblocks Best-Interest-Factor tagging for every downstream evidence record.[^3]
2. **Wrap the multi-engine document-intelligence registry and Semantica as MCP-callable services** — both already exist in full; the gap is purely integration, closing the document-handling coverage hole in one move.[^3]
3. **Build the SBV-to-custody bridge** — export SBV's parsed SMS/MMS records (or bypass SBV and feed its underlying XML directly into the existing `sbv_sms.py`/custody-hashing lane) so message data reaches `analysis.normalized_record` with proper hashing rather than living only in an isolated viewer database.[^3]
4. **Implement the elusion-sampling citation-grounding validator** as a release gate inside `Legal-Workspace`'s existing `citation_gate.py`, extending it from legal-citation checking to evidentiary-claim checking per the vLex verification-status taxonomy.[^2][^1]
5. **Port the Ed25519 signed chain-of-custody** from the dial-stack design into the spine's `custody.py` to harden authenticity guarantees beyond hash-only integrity checks.
6. **Connect the trained Tether behavioral models** to replace the four-pattern placeholder in `behavior-service.ts`, since these models already exist and materially outperform the current default rule set for coercive-control pattern detection.
7. **Build the 8/9-column Best-Interest-Factor courtroom export** as a new `Legal-Workspace` service module, consuming the tagged evidence records once items 1 and 3 are in place.[^1]

---

## References

1. [Claude - chat pipeline for PostgreSQL - Claude.md](Claude - chat pipeline for PostgreSQL - Claude.md)

2. [VLEX-RESEARCH-PROMPTS.md](VLEX-RESEARCH-PROMPTS.md)

3. [archive-triage-parser-schema-lineage-2026-08-09.md](archive-triage-parser-schema-lineage-2026-08-09.md)

