> _Byline: Claude Code · Opus 5 · 2026-08-23_
> _Naming: written before the 2026-09-05 rename (D-137..D-141); see docs/NAMING.md for the old->new glossary._

# Phase 0 Requirements Register — Document Handling, Search, Evidence Bundling

Normalized requirements register built from eight reference documents (nine source files — two PDFs form one whitepaper pair from the same vendor). Feeds the cross-repo gap analysis on document handling, search, and evidence bundling for the legal-evidence platform.

---

## 1. Mary Technology Whitepaper — "Building the Future of Law: A Legal Data Infrastructure"

**What it argues.** Law firms suffer from "Fact Chaos" — key facts scattered across unstructured, inconsistently labeled documents — which degrades both human and AI performance; RAG systems alone still misstate facts in 17–33% of complex legal responses. The paper proposes a "Legal Fact Layer," built via a "Fact Management System" (FMS), that extracts and centralizes facts (parties, events, clauses, obligations) with provenance, reliability, and legal-relevance metadata, distinguishing verified statements of truth from mere claims/allegations. It argues this fact-centric, knowledge-graph-inspired layer — not bigger context windows or RAG alone — is the precondition for reliable legal AI, and positions the FMS as complementary to (not a replacement for) practice-management systems.

**Concrete requirements/recommendations:**
1. Extract and centralize key facts (parties, events, clauses, obligations) into one continuously updated repository rather than leaving them buried in static documents.
2. Store each fact with contextual metadata — source, reliability/provenance, legal relevance — and explicitly distinguish "claim/allegation" from "verified statement of truth."
3. Track fact versions and disputes: flag contested/superseded/updated facts in real time, and retain the full mention-history of a fact (e.g., every place an incorrect date was repeated, and by whom, before correction).
4. Apply a consistent labeling/tagging schema (dates, names, events) across parties, events, clauses, and communications so practitioners, staff, and AI all reference data the same way.
5. Automate ingestion: split PDFs, extract relevant text, de-duplicate files, and identify unique facts (treated like nodes in a knowledge graph).
6. Auto-generate dynamic chronologies from the fact layer rather than compiling them manually.
7. Provide interactive dashboards that highlight missing information and track case progress against a single source of truth.
8. Feed AI drafting/summarization only from the curated, verified fact layer — not raw unstructured text — to get repeatable, deterministic outputs for a given query against a given dataset.
9. Model facts using a knowledge-graph-inspired entity/relationship structure (parties, events, clauses, communications as nodes/edges) to act as a retrieval booster and consistency check.
10. Combine RAG retrieval with the structured knowledge/fact layer (hybrid strategy) rather than relying on RAG alone or on expanding context-window size, since longer context amplifies contradictions when the underlying data isn't structured.
11. Make every AI-generated statement traceable back to its underlying source fact (transparency requirement).
12. Position the Fact Management System as complementary to, not a replacement for, existing Practice Management / Document Management systems.

---

## 2. Mary Technology Whitepaper — "Verification in Legal AI Is a Design Problem"

**What it argues.** Citing the May 2025 $31,100 sanction over a brief with invented authorities (built through paid, purpose-built legal research tools, not a consumer chatbot) and Damien Charlotin's hallucination database (1,922 cases as of August 2026), the paper argues that "be more careful" fails predictably because verification was left to individual vigilance rather than built into the workflow. It reframes verification as a design problem: legal AI output must be cheap and structurally easy to check, because if checking costs as much as redoing the work (the "verification tax"), review is the first thing cut under deadline pressure. It prescribes five concrete workflow controls and insists that responsibility for a filed or signed work product is a "non-delegable signature" that no tool, vendor, or workflow can absorb.

**Concrete requirements/recommendations:**
1. Provide five distinct checkable-workflow controls: (a) show the source and its context; (b) show gaps and scope limits; (c) use a checking method capable of disagreeing with the generator; (d) define what happens when support fails; (e) require review before consequential use.
2. Material findings must open to the exact source page/location plus enough surrounding material for the reviewer to judge meaning — a bare highlighted sentence can mislead when context sits outside the excerpt.
3. Report what the system did **not** have, search, or resolve (missing document periods, unsupported findings, expected-but-unavailable material, unanswered requests, unresolved conflicts) as a first-class "scope report," not only what it found.
4. The independent checker must use a genuinely different method than the generator (a different retrieval pass, deterministic source validation, a differently constrained model, or human review) — a second prompt to the same model is not independent verification.
5. Explicitly define the response when support fails: block the output, produce a warning, or require escalation — never silently absorb an unsupported claim into polished prose.
6. Require a UI-enforced mandatory review step before a material finding is adopted, signed, exported, or a filing released; a passive source link does not by itself prevent a cursory glance (cites cognitive-forcing-function research).
7. Evaluate any legal-AI product with a "known-matter test": run it on a matter the firm's own lawyers already know, then score what it surfaces against the five controls — benchmark scores and general "grounded" claims do not answer whether a lawyer can adopt a specific output.
8. Preserve real opportunities for unassisted work, especially for junior lawyers, to avoid skill decay from over-reliance on AI output (analogized to FAA manual-flying-practice guidance and an endoscopy-deskilling study) — without imposing an arbitrary quota.
9. Address five distinct failure modes with five distinct controls rather than one generic "accuracy" fix: unsupported claims, silent omission, self-confirmation, unresolved conflict, and automatic/uncritical acceptance.
10. Responsibility for a filed or signed work product is non-delegable to a model, vendor, junior lawyer, or firm system — the review/sign step must be a real, addressed action tied to the specific output, not a formality.

---

## 3. edisc.md — Defensible eDiscovery/RAG/Evidence-Bundling Build Plan (Salem v. Kinzel)

**What it specifies.** A synthesized build sequence for a Michigan family-court custody matter's evidence pipeline, tying every architectural choice to an authoritative standard (EDRM, Sedona Conference, NIST SP 800-86) or to infrastructure the project already has (bitemporal Postgres schema, custody-hashing parser layer, ingestion pipeline design). Its central contribution is porting TAR's (Technology-Assisted Review's) statistical elusion-sampling validation methodology onto RAG citation-grounding validation — the one area it finds has no existing industry standard — plus a concrete 9-stage corpus-timeline pipeline mapped to Michigan's 12 statutory Best Interest Factors.

**Concrete requirements/recommendations:**
1. Adopt EDRM technical interchange formats — metadata XML schemas, Opticon `.opt`/`.log`, Concordance `.dat` load files — for cross-platform evidence production/export.
2. Apply NIST SP 800-86 forensic acquisition standards: SHA-256/MD5 hashing at point of capture; preserve filesystem/EXIF metadata without altering access timestamps; use the NIST NSRL reference set to filter known non-evidentiary files ("de-NISTing").
3. Validate generative-AI/RAG citation grounding with a TAR-style statistical elusion-sampling framework: split output into "grounded" (Bucket A) vs. "flagged/uncertain" (Bucket B) populations, further stratify Bucket A by citation type and retrieval-confidence band, and draw stratified samples for review.
4. Classify every sampled citation as `CONFIRMED_GROUNDED`, `HALLUCINATED`, `MISGROUNDED`, or `AMBIGUOUS`, checking independently whether the source exists, whether the pinpoint supports the claim, and whether the characterization is accurate (not merely present).
5. Set a numeric elusion-rate gate — under 2–3% — before any output is used in a filing, with zero tolerance for unreviewed AI output in court-facing documents regardless of measured elusion rate.
6. Auto-escalate any citation category exceeding its threshold to mandatory human review, and log every gate decision and elusion calculation with a timestamp and methodology version.
7. Assign every source document a deterministic evidence ID (e.g., `EX-2021-04-TEXT-01`) so every downstream extracted event traces to an exact page or message.
8. Chunk the corpus chronologically into monthly/quarterly batches (roughly 50–100 pages) to stay within model context limits during extraction.
9. Produce dual-granularity extraction output per event: a flat structured JSON record (date, time, parties, event type, mapped statutory factor, factual summary, verbatim quote, source ID, impact assessment) plus a contextual embedding chunk carrying the surrounding exchange, tagged to a parent-thread ID.
10. Extraction prompts must instruct the model to record objective facts and exact quotes rather than interpret feelings, and to ignore routine content unless it demonstrates a legally relevant pattern.
11. Use multi-layered/hierarchical embedding indexing (full document, thread/session, batch, message/exchange, clause-level) rather than flat uniform chunking — cites a study finding hierarchical indexing retrieved 37.86% of essential chunks vs. 16.39% for flat chunking.
12. Embed each extracted event twice — once isolated (for precise matching) and once with surrounding conversational context attached — so retrieval preserves tone/pattern context rather than an isolated stripped line.
13. Apply retrieval-time filtering: a similarity-deviation cutoff (~25% from the top match), a per-response token budget, and de-duplication of overlapping parent/child context.
14. Map every extracted event to one of the 12 Michigan MCL 722.23 Best Interest Factors as structured metadata.
15. Export the finalized chronology as a structured multi-column matrix (date/time, category, statutory factor, factual description, quote/evidence summary, exhibit/source ID, contradicting-testimony flag, admissibility/witness source, `context_thread_id`) rather than narrative prose.
16. Store extracted events and their embeddings in the project's existing bitemporal PostgreSQL schema (with custody hashing already built in) rather than a separate tool — a parallel storage system would fragment an already-engineered custody trail.
17. Use a closed-world citation constraint architecture: the model may only cite passages it actually retrieved; backend regex extraction checks cited identifiers against a database.
18. Re-run elusion/quality sampling as a mandatory release gate after any change to retrieval, prompting, or verification logic, before deploying the change.
19. Use a normalized verification-status tag vocabulary (`VERIFIED_PRIMARY`, `VERIFIED_OFFICIAL_METADATA_ONLY`, `MIRROR_ONLY`, `BLOCKED`, `CONFLICTED`, `STALE`, `SUPERSEDED`, `PROVISIONAL_CURRENCY_NOT_CLEARED`, `ATTORNEY_REVIEW`) for every legal proposition before it's trusted, and extend the same protocol to RAG-generated factual claims about case evidence.

---

## 4. The Complete Guide to Legal Fact Management (Mary Technology blog)

**What it argues.** A short practitioner-facing piece distinguishing document storage/eDiscovery (which holds and retrieves files) from legal fact management (identifying people, events, dates, conflicts, and gaps across those files). It argues search alone is insufficient because many litigation questions require identifying an event before a query can even be formed, and that AI can propose factual structure faster than manual review but does not remove the need for review.

**Concrete requirements/recommendations:**
1. Extract factual statements while preserving the source and surrounding context — do not strip provenance in the process of structuring facts.
2. Normalize people and dates across documents so the same entity or date is recognized despite being described differently in an email, witness statement, or attachment.
3. Connect related events across documents (cross-document linking) rather than treating each source in isolation.
4. Record contradictions and missing material as explicit, first-class attributes of the factual record.
5. Allow lawyers to correct the factual record, and persist those corrections so later outputs (chronologies, summaries, drafting) reuse the corrected fact rather than the original extraction.
6. A factual record should capture: what happened, who was involved, when, which document supports the statement, whether accounts conflict, whether expected material is missing, and whether a lawyer has reviewed/corrected the entry.
7. Evaluate a fact-management system on a closed matter with a lawyer-reviewed reference record, measuring factual support, material omissions, source-review time, corrections required, and whether later outputs use the corrected facts — and avoid relying on a generic accuracy number without the task and scoring method behind it.

---

## 5. conversation_ingestion_system_design.md — Conversation/Log Ingestion System Design

**What it specifies.** A five-iteration architecture evolution (from a linear pipeline to a "chunk-first, schema-aware, transform-during-ingestion, preview-before-commit" pipeline) for ingesting large conversation/log files of varying formats into PostgreSQL, developed specifically for the Salem v. Kinzel forensic case. It is the settled design doc distilled from the raw chat transcript (source 9).

**Concrete requirements/recommendations:**
1. Chunk large files before format detection or parsing — chunking must be format-agnostic and happen first, enabling processing of files larger than RAM.
2. Validate each chunk's structural integrity after chunking (JSON well-formed, CSV column-consistent, etc.) and repair structure only — never delete or modify actual data; an incomplete record at a chunk boundary is deferred to the next chunk rather than dropped.
3. Check ingested samples against a library of known schemas (fingerprint + similarity score — Jaccard on field names plus type matching, >85% match threshold) before running full schema discovery, to save time and build institutional knowledge.
4. Provide interactive field-mapping (CLI first, web GUI later) from discovered fields to the target Postgres schema, with auto-suggested mappings the user confirms or edits, and mappings saved for reuse.
5. Apply enrichment transformations during ingestion, not after: timezone normalization (add local-timezone columns, e.g. Eastern for a Michigan court, alongside UTC), categorical code decoding (e.g., `1=read, 2=unread, 3=blocked`) to human-readable labels, with configurations saved and reusable as templates.
6. Provide a mandatory preview mode showing the first ~10 transformed/mapped records before committing to full processing, with options to continue, preview another batch, modify mappings/transforms, or enter an interactive fix session (skip/default-value/manual-entry/apply-to-all-similar) for detected issues.
7. Persist ingestion-run metadata and per-chunk processing status in dedicated tables (`ingestion_runs`, `chunk_status`) including validation status, repair log, records processed, and errors, for audit purposes.
8. Compute and store SHA-256 hashes at the chunk level as chain-of-custody metadata, alongside transformation logs and preserved original chunks, with a full audit trail of all modifications.
9. Preserve full conversational nuance rather than over-summarizing individual messages — explicitly named the "nuance IS the abuse" principle for this forensic use case — requiring context-preserving chunking rather than flattening.
10. Document validation steps, repair decisions, and preserve source-data integrity with timestamped processing logs as an explicit "Court Admissibility" requirement.

---

## 6. archive-triage-parser-schema-lineage-2026-08-09.md — Parser & Schema Lineage Triage

**What it specifies.** A cross-reference of nine archived zip files against the live `mcp-platform-agno-mvp` repo to determine which parser and schema implementations are current vs. superseded. Its headline finding is that none of the archives contain the newest lineage — the live repo (committed 2026-08-07) already supersedes almost everything in them — and it documents which parser/schema generations are canonical, which are dead, and which gaps remain unfilled by either.

**Concrete requirements/recommendations:**
1. Maintain a single canonical, actively-committed parser lineage per data/file type, and explicitly mark superseded parser generations as dead rather than letting multiple parallel implementations coexist (live messaging parsers at `server/tools/parsers/messaging/`; live AI-chat parsers via vendored `chatminer`; a comprehensive but zero-call-site "Semantica" generic-document parser flagged as a standing dead-end/gap despite being feature-complete on paper).
2. Preserve forensic custody hashing as a separately tracked parser lane (a "shadow" parser with Go-backed H1/H2/H3 hashing) alongside a non-forensic pure-Python fallback for the same format, so custody-hash capability is not silently lost when the primary/shadow assignment changes.
3. Explicitly document known parser coverage gaps rather than silently failing: no WhatsApp/.txt parser, no native `chat.db` SQLite parser, no standalone call-log parser (calls only ride the SMS-XML lane), and MMS binary media is dropped if the custody-hashing backend (SBV) is down.
4. Consolidate fragmented ontology/behavioral-detection schema iterations (nine prior versions, including TTL ontology files and a "final" Python ontology) into one strictly-additive union migration rather than re-deriving from raw source files each time.
5. Treat a schema/ontology reconciliation as "DRAFT / paper-only" until its deployment status is verified against the live running database — file-level/design review alone cannot confirm what migrations are actually applied.
6. Use a single bitemporal schema spine (`occurred_at`/`knowledge_time`/`disclosure_tier`, evidence custody hashing, retrieval axes) as the one target schema for ingested records, treating earlier competing schema lineages (e.g., an abandoned Drizzle/TypeScript schema set) as dead, historical-reference-only artifacts.

---

## 7. VLEX-RESEARCH-PROMPTS.md — Michigan Custody-Guide Legal Research Verification Protocol

**What it specifies.** A set of structured research prompts and a global verification protocol for closing legal-accuracy gaps in a Michigan custody self-help guide, designed to be run through vLex and then reconciled against official Michigan sources. It is less about the underlying substantive law than about the *verification methodology* every legal-research output in the project must follow.

**Concrete requirements/recommendations:**
1. Every legal-research proposition must carry: full citation; issuing court/body; publication/precedential status; exact statutory/rule subsection or opinion pinpoint; quoted operative language; effective/amendment date; subsequent/negative/limiting/superseding treatment history; a stable document identifier or official-source URL; and any unresolved conflict.
2. Separate controlling authority from persuasive authority, agency guidance, local practice, and secondary explanation; never infer a rule from a headnote alone; never state a source is current merely because a link resolves.
3. Mark unsupported propositions explicitly as `UNSUPPORTED` with an explanation, rather than omitting them or guessing.
4. Require dual structured output for every research task: a source table and a proposition-to-pinpoint table.
5. Require a structured edit-audit format for any proposed correction to existing text: a CONCERNS table (location, exact current language, defect, severity, supporting authority) and a PROPOSED CHANGES table (location, exact old language, minimally corrected replacement, supporting authority, verification date, limitations) — never silently rewrite the supplied text.
6. Disambiguate case citations referenced only by informal/short name (e.g., "Hayes," "Duperon") by full case name, citation, docket number, court, date, and publication status before trusting any attributed proposition; if identification is insufficient, state what additional citation is needed rather than guessing.
7. Classify every proposition drawn from a case as holding, dicta, procedural fact, or later characterization, and report its current treatment (affirmance/reversal history, negative or limiting treatment).
8. For a semantic audit of disputed propositions, classify each as `SUPPORTED` / `PARTLY SUPPORTED` / `CONFLICTED` / `SUPERSEDED` / `UNSUPPORTED` with exact pinpoints, and supply the narrowest accurate replacement sentence plus the facts that could change the answer.
9. Preserve verification provenance for every saved research artifact: prompt number/exact query, retrieval date/time, database/document identifiers, complete citation and publication status, treatment-report date, the exported document exactly as received, official-source links, and a SHA-256 hash; never rename an original export after ingestion — work from copies and keep originals unchanged.

---

## 8. SocialListeningAPI.md — Vendor Dashboard Snapshot

**What it is.** A thin, non-technical clipping of a SocialListeningAPI account dashboard (credit balance, an example `curl` call, a pricing note), not a design or requirements document. Its only substantive content is that a credentialed third-party social-listening API exists as a potential evidence-ingest source, and it inadvertently exposes a live API key in plaintext within the clipped page.

**Concrete requirements/recommendations:**
1. Social-media evidence (LinkedIn, X, Reddit, Instagram, Facebook, Google results, etc.) can be sourced via a credentialed third-party API rather than manual collection, under a per-request/per-endpoint credit-billing model (e.g., Facebook search costs materially more credits than most other endpoint calls; failed requests are not billed).
2. Any credential used to integrate this or a similar source into the ingestion pipeline must be treated as a secret — kept out of tracked files and rotated if ever committed — since this specific clipping already contains a live key in plaintext.

*(Note: this document is a dashboard screenshot, not a specification. Its API key is not reproduced in this register per credential-handling policy; it should be treated as exposed and rotated by the account owner if not already tracked as such.)*

---

## 9. Claude — Chat Pipeline for PostgreSQL (raw transcript, skimmed for conclusions/decisions)

**What it is.** A ~4,350-line exported chat transcript documenting the live design conversation that produced document 5 (`conversation_ingestion_system_design.md`). The first ~2,150 lines iterate through the same five architecture revisions already captured above; the remainder (lines ~2,150–4,350) is the user's "export this thread" request, which reproduces the design doc and then appends a previously-supplied **"Salem MCP Gateway Server"** Python scaffold — a genuinely distinct architecture not present in document 5 — followed by a duplicate repetition of that same code (the export appears truncated mid-repetition). Only the MCP Gateway material adds requirements beyond documents 5 and 6.

**Concrete requirements/recommendations (beyond what's already captured in docs 5–6):**
1. Split storage by concern across four specialized systems, each reached through one MCP Gateway server layer rather than local per-client MCP servers: Supabase PostgreSQL (relational — `timeline_events`, `entities`, `files`, `command_log` tables), Neo4j Aura (entity-relationship knowledge graph, via Graphiti), Qdrant Cloud (vector search), and Cloudflare R2 (object storage, e.g. bucket `salem-legal-evidence`).
2. Timeline-event records carry legal-factor tagging and behavioral-pattern flags as first-class fields, not an afterthought layer: `description`, `date_raw`, `category`, `case_id`, `location`, `witnesses`, `is_significant`, `manipulation_pattern`, `legal_factors` (MCL 722.23 tags), `child_present`, `raw_quotes`, `source_app`.
3. Log every AI-tool/command execution against the platform to a dedicated audit table (`command_log`: command, source, agent, status, response) — independent of, and in addition to, evidence custody hashing.
4. Centralize document parsing and OCR through one shared service (a single `parse_document`/`ocr_image` tool backed by Unstructured) rather than per-app parsing logic.
5. Decouple long-running/batch workflows (Google Drive sync, deduplication, timeline regeneration, legal-factor tagging) from the interactive chat/tool-call path via asynchronous webhook triggers (n8n).
6. Support natural-language queries directly against the knowledge graph (entities and relationships), not only document/chunk similarity search.
7. Route embeddings and chat completions through a model gateway (LiteLLM) supporting both hosted (OpenAI `text-embedding-3-small`/`-large`) and local (Ollama `nomic-embed-text`) embedding models, with a defined provider fallback chain.
8. Provide a `get_case_summary` aggregate-status tool (counts of timeline events, entities, files) as a standing case-health check, distinct from the per-item audit log.

---

# Merged Requirements Register

| ID | Requirement (one line) | Domain | Source doc(s) | Why it matters |
|---|---|---|---|---|
| R01 | Chunk large files before format detection/parsing; chunking must be format-agnostic | ingest | conversation_ingestion_system_design.md; Claude chat pipeline | Enables processing files larger than RAM and decouples chunking from format-specific bugs |
| R02 | Validate chunk structural integrity after chunking; repair structure only, never delete/alter data — incomplete boundary records defer to the next chunk | ingest | conversation_ingestion_system_design.md; Claude chat pipeline | Prevents silent data loss at chunk boundaries, a common corruption source |
| R03 | Check ingested samples against a library of known schemas (fingerprint + similarity score, >85% threshold) before running full schema discovery | ingest | conversation_ingestion_system_design.md; Claude chat pipeline | Saves reprocessing cost and keeps mapping consistent across repeated source formats |
| R04 | Provide interactive field-mapping (CLI first, GUI later) from discovered fields to target schema, with mapping templates saved for reuse | ingest | conversation_ingestion_system_design.md; Claude chat pipeline | New/unknown export formats are common in messaging/log evidence and need a human-in-the-loop path |
| R05 | Apply enrichment transforms during ingestion, not after: timezone add-columns (normalized to the court's local timezone), categorical code decoding, ID enrichment, derived fields, PII hashing/redaction | ingest | conversation_ingestion_system_design.md; Claude chat pipeline | Output should be analysis-ready at write time; re-deriving these later is wasted, error-prone rework |
| R06 | Provide a mandatory preview-before-commit mode (~10 records) with interactive per-field fix-up before full ingestion runs | ingest | conversation_ingestion_system_design.md; Claude chat pipeline | Catches mapping/parsing errors before they propagate through thousands of records |
| R07 | Assign every source document a deterministic evidence ID so every downstream extracted event traces to an exact page/message | ingest; evidence-bundling | edisc.md | Foundational for exhibit citation and admissibility; without it, extracted facts can't be traced back |
| R08 | Chunk corpora chronologically into monthly/quarterly batches (~50–100 pages) to stay within model context limits during extraction | ingest | edisc.md | Keeps extraction prompts within reliable context budgets for an 8-year corpus |
| R09 | Produce dual-granularity extraction output per event: flat structured JSON record + contextual embedding chunk with parent-thread ID | ingest; search | edisc.md | Flat extraction alone strips the conversational context that gives a message its meaning |
| R10 | Extraction prompts must capture objective facts/exact quotes, not interpreted feelings, and ignore routine content unless it shows a legally relevant pattern | ingest; verification | edisc.md | Keeps extraction outputs closer to admissible fact and reduces AI editorializing |
| R11 | Automate ingestion: split PDFs, extract text, de-duplicate files, identify unique facts as the first step toward a fact layer | ingest | Mary Whitepaper 1 | De-duplication and text extraction are prerequisites to any fact-centric structure |
| R12 | Centralize document parsing/OCR through one shared service rather than per-app parsing logic | ingest; ops | Claude chat pipeline | Avoids drift between multiple bespoke parsers doing the same job |
| R13 | Maintain a single canonical, actively-committed parser lineage per data/file type; explicitly retire superseded generations | ingest; ops | archive-triage doc | Multiple live-but-stale parser generations create silent divergence and wasted maintenance |
| R14 | Preserve forensic custody hashing as a separately tracked "shadow" parser lane alongside a non-forensic fallback for the same format | ingest; evidence-bundling | archive-triage doc | Custody-hash capability must not be silently lost when a primary/fallback path is swapped |
| R15 | Explicitly document known parser/format coverage gaps rather than silently failing (e.g., no WhatsApp parser, no chat.db parser, MMS media dropped when hashing backend is down) | ingest; ops | archive-triage doc | Undocumented gaps become undetected evidence loss in a legal context |
| R16 | Social-media evidence can be sourced via credentialed third-party APIs (LinkedIn/X/Reddit/etc.), gated by per-endpoint credit billing | ingest | SocialListeningAPI.md | A viable ingest channel for social-media evidence, distinct from manual capture |
| R17 | Normalize people, dates, and other entities across documents so the same entity is recognized despite differing phrasing across sources | ingest; search | Complete Guide to Legal Fact Management | Without normalization, cross-document search and fact-linking both degrade |
| R18 | Store extracted events and embeddings in one existing bitemporal system-of-record schema (`occurred_at`/`knowledge_time`/`disclosure_tier` + custody hashing) rather than a parallel tool | storage | edisc.md; archive-triage doc | Prevents fragmenting an already-engineered custody trail across multiple stores — see Contradiction 2 |
| R19 | Persist ingestion-run and chunk-processing audit tables (`ingestion_runs`, `chunk_status`) with validation status, repair log, and error log | storage; ops | conversation_ingestion_system_design.md; Claude chat pipeline | Gives every ingestion run a reconstructable audit trail |
| R20 | Compute and store SHA-256/MD5 hashes at point of capture or chunk level as chain-of-custody metadata, alongside transformation logs and preserved originals | storage; evidence-bundling | conversation_ingestion_system_design.md; edisc.md (NIST SP 800-86) | Core forensic-integrity requirement for any evidence later offered in court |
| R21 | Preserve filesystem/EXIF metadata without altering access timestamps; filter known non-evidentiary files via NIST NSRL ("de-NISTing") | storage; evidence-bundling | edisc.md | Standard forensic acquisition practice; altering timestamps undermines authentication |
| R22 | Consolidate fragmented ontology/behavioral-detection schema iterations into one strictly-additive union migration | storage | archive-triage doc | Nine prior iterations already existed; re-deriving from raw sources duplicates completed work |
| R23 | Verify schema/ontology deployment status against the live running database as a distinct step from design review | storage; ops | archive-triage doc | A migration can be fully designed and merged in git yet unapplied to the live DB |
| R24 | Log every AI-tool/command execution against the platform to a dedicated audit table (command, source, agent, status, response) | storage; ops | Claude chat pipeline | Separate operational audit trail, independent of evidence custody hashing |
| R25 | (Contested — see Contradiction 2) Split storage by concern across a relational DB, graph DB, vector DB, and object store, reached through one gateway | storage | Claude chat pipeline | A defensible pattern in general software architecture, but conflicts with R18's single-system mandate for this case's custody trail |
| R26 | Use multi-layered/hierarchical embedding indexing (document, thread, batch, message, clause-level) rather than flat uniform chunking | search | edisc.md | Cited study found hierarchical indexing retrieves far more essential content with fewer wasted hits (37.86% vs 16.39%) |
| R27 | Embed each extracted event twice — isolated (precise matching) and with surrounding conversational context (parent-thread ID) | search | edisc.md | Preserves tone/pattern context that a stripped, isolated line loses |
| R28 | Apply retrieval-time filtering: similarity-deviation cutoff (~25% from top match), per-response token budget, de-duplication of overlapping parent/child context | search | edisc.md | Controls noise and cost in the retrieval layer at query time |
| R29 | Route embeddings through a model gateway supporting both hosted and local embedding models with provider fallback | search; ops | Claude chat pipeline | Avoids single-provider lock-in/outage risk for a core retrieval dependency |
| R30 | Combine RAG retrieval with a structured knowledge/fact layer (hybrid retrieval) rather than RAG-alone or long-context-alone | search | Mary Whitepaper 1 | Longer context alone amplifies contradictions when underlying data isn't structured |
| R31 | Support natural-language queries directly against the knowledge graph (entities/relationships), not only document/chunk similarity search | search | Claude chat pipeline | Entity-relationship questions (who is related to whom, how) aren't well served by chunk similarity alone |
| R32 | Provide five distinct checkable-workflow controls: source+context; gap/scope reporting; an independently-methoded checker; defined failure response; mandatory review gate | verification | Verification whitepaper | The paper's core prescription — each control covers a distinct failure mode no other control covers |
| R33 | Material findings must open to the exact source page/location plus enough surrounding context to judge meaning, not just a highlighted snippet | verification | Verification whitepaper; Complete Guide | A decontextualized excerpt can mislead even when technically "sourced" |
| R34 | Report what the system did NOT have, search, or resolve (a "scope report") as a first-class output, not only what it found | verification | Verification whitepaper; Complete Guide | Silent omission is a distinct, harder-to-detect failure mode than a wrong citation |
| R35 | The independent checker must use a genuinely different method than the generator — a repeated prompt to the same model is not independent verification | verification | Verification whitepaper | Agreement between a model and itself carries no evidentiary weight |
| R36 | Define explicit behavior when support fails: block, warn, or escalate — never silently absorb an unsupported claim into polished prose | verification | Verification whitepaper | Prevents unsupported material from reaching a filing undetected |
| R37 | Require a UI-enforced mandatory review step before any material finding is signed, filed, exported, or otherwise relied on | verification; UX | Verification whitepaper | A source link alone doesn't prevent a cursory glance; the interface must force the check |
| R38 | Evaluate any AI tool via a "known-matter test" — score against the five controls on a matter the firm already knows — rather than trusting benchmark/accuracy scores alone | verification | Verification whitepaper; Complete Guide | Aggregate accuracy numbers don't answer whether a specific output is safe to sign — see Contradiction 1 |
| R39 | Preserve opportunities for unassisted human work (especially junior staff) to avoid skill decay from AI over-reliance | verification; ops | Verification whitepaper | Cites an endoscopy-deskilling study; judgment atrophies without periodic unassisted practice |
| R40 | Validate RAG citation grounding using a TAR-style statistical elusion-sampling framework (stratified sampling by citation type/confidence, tri-state+ classification) | verification | edisc.md | Ports a legally battle-tested (Da Silva Moore-era) statistical validation method to a domain with no existing standard |
| R41 | Set a numeric elusion-rate gate (<2–3%) before AI output is used in a filing; zero tolerance for unreviewed AI output in court-facing documents | verification | edisc.md | Establishes a measurable, auditable release threshold — see Contradiction 1 for tension with per-instance review |
| R42 | Auto-escalate any citation category exceeding threshold to mandatory human review; log every gate decision and calculation with timestamp and methodology version | verification; ops | edisc.md | Makes the validation gate itself auditable and reproducible |
| R43 | Use a closed-world citation constraint: the model may only cite passages it actually retrieved, checked via backend regex extraction against a database | verification | edisc.md | Structurally prevents fabricated citations rather than only detecting them after the fact |
| R44 | Re-run elusion/quality sampling as a mandatory release gate after any change to retrieval, prompting, or verification logic | verification; ops | edisc.md | Treats a fresh validation measurement as a release gate, not a one-time check |
| R45 | Preserve each fact's source, reliability/provenance, and legal relevance; distinguish "claim/allegation" from "verified statement of truth" | verification | Mary Whitepaper 1 | Legal facts carry weight only in context of who said them, where, and why |
| R46 | Track fact versions and disputes; retain full mention-history of a later-corrected fact and who repeated it | verification | Mary Whitepaper 1 | Lets a reviewer answer "who relied on the wrong date, and when was it fixed" |
| R47 | Make every AI-generated statement traceable back to its underlying source fact end-to-end | verification | Mary Whitepaper 1; Complete Guide | Traceability is the mechanism that makes "verified" a checkable claim rather than an assertion |
| R48 | Allow reviewers to correct/annotate the factual record; persist corrections so downstream outputs reuse the corrected fact | verification | Complete Guide | Otherwise every regenerated summary/chronology repeats the same already-caught error |
| R49 | Record contradictions and missing material as explicit first-class fields on the factual record | verification | Complete Guide; Verification whitepaper | Conflicts and gaps need to be queryable, not buried in narrative text |
| R50 | Use a normalized verification-status tag vocabulary for legal propositions before any citation is trusted; extend the same protocol to factual RAG claims about case evidence | verification | edisc.md; VLEX-RESEARCH-PROMPTS.md | Gives every claim a machine-checkable state instead of an implicit binary trust/don't-trust |
| R51 | Every legal-research proposition must carry full citation, issuing body, status, exact pinpoint, quoted language, effective date, subsequent treatment, a stable identifier/URL, and any unresolved conflict | verification | VLEX-RESEARCH-PROMPTS.md | A link resolving is not evidence of currency; the paper explicitly warns against that shortcut |
| R52 | Separate controlling authority from persuasive authority, agency guidance, local practice, and secondary explanation; never infer a rule from a headnote alone | verification | VLEX-RESEARCH-PROMPTS.md | Conflating authority tiers is a common, high-consequence legal-research error |
| R53 | Mark unsupported propositions explicitly as UNSUPPORTED with an explanation, rather than omitting or guessing | verification | VLEX-RESEARCH-PROMPTS.md | Silence and a wrong guess are both worse than a labeled gap |
| R54 | Classify every case-derived proposition as holding, dicta, procedural fact, or later characterization, and report current treatment | verification | VLEX-RESEARCH-PROMPTS.md | Distinguishes binding law from persuasive or superseded material |
| R55 | Disambiguate citations referenced only by informal/short case name before trusting any attributed proposition; say what's missing rather than guessing | verification | VLEX-RESEARCH-PROMPTS.md | Prevents attributing a holding to the wrong case entirely |
| R56 | Export final chronologies/fact sets as a structured multi-column matrix rather than narrative prose | evidence-bundling; UX | edisc.md | Judges and FOC referees respond better to structured matrices than prose narrative |
| R57 | Map every extracted event to the applicable statutory factor schema (e.g., Michigan's 12 MCL 722.23 Best Interest Factors) as structured metadata | evidence-bundling | edisc.md; Claude chat pipeline | Statutory-factor tagging is what makes the corpus usable for a Best-Interest-Factor argument |
| R58 | Preserve full conversational nuance rather than over-summarizing when the pattern itself is the evidence ("nuance IS the abuse") | evidence-bundling; ingest | conversation_ingestion_system_design.md; edisc.md | Flattening/over-summarizing can erase the exact pattern the evidence is meant to show |
| R59 | Adopt EDRM technical interchange formats (metadata XML, Opticon `.opt`/`.log`, Concordance `.dat`) for cross-platform evidence production/export | evidence-bundling | edisc.md | Standard formats are required for interoperability with opposing counsel/court systems |
| R60 | Preserve verification provenance for every saved research/evidence artifact (query, retrieval date, source IDs, citation, exported document as received, SHA-256 hash); never rename originals | evidence-bundling | VLEX-RESEARCH-PROMPTS.md | Chain-of-custody for research artifacts, mirroring evidentiary chain-of-custody discipline |
| R61 | Require a structured edit-audit format (CONCERNS table + PROPOSED CHANGES table) for any correction to existing evidentiary/guide text; never silently rewrite | evidence-bundling; verification | VLEX-RESEARCH-PROMPTS.md | Makes every correction to case material independently reviewable |
| R62 | Responsibility for a filed or signed work product is non-delegable to the AI, vendor, junior lawyer, or firm system | evidence-bundling; verification | Verification whitepaper | Sets the legal ceiling that every other control in this register exists to support |
| R63 | Provide interactive dashboards surfacing missing information and case/matter progress as a single source of truth | UX | Mary Whitepaper 1 | Gives the team one place to see what's incomplete rather than re-deriving status ad hoc |
| R64 | Let users ask natural-language questions that resolve to a specific fact/version history, not just keyword search | UX; search | Mary Whitepaper 1; Complete Guide | The stated example ("which statements referenced the date before it was corrected") is not answerable by keyword search |
| R65 | Structured evidence matrices are preferred by judges/referees over narrative prose for courtroom consumption | UX; evidence-bundling | edisc.md | Directly informs the target output format for any court-facing export |
| R66 | Decouple long-running/batch workflows (source sync, deduplication, timeline regeneration, factor tagging) from the interactive chat/tool-call path via async triggers | ops | Claude chat pipeline | Keeps the interactive tool surface responsive while heavy jobs run in the background |
| R67 | Save/version transformation and mapping configurations for reuse across ingestion runs | ops; ingest | conversation_ingestion_system_design.md; Claude chat pipeline | Builds institutional knowledge instead of re-configuring the same source format repeatedly |
| R68 | Treat "design/migration complete" and "deployed to the live database" as two distinct, separately-verified states in project tracking | ops | archive-triage doc | A merged migration file is not evidence that the schema is live; this gap already occurred once |

---

# Contradictions Between Documents

**1. Statistical elusion-sampling gate vs. per-instance checkable-workflow controls (edisc.md vs. Verification whitepaper / Complete Guide to Legal Fact Management).**
edisc.md's central proposal is a TAR-derived *population-level* validation gate: stratify RAG output, sample it, and require an aggregate elusion rate under 2–3% (with escalation) before output may be used in a filing (R40–R42). Mary Technology's Verification whitepaper argues the opposite emphasis explicitly: *"Benchmark scores don't answer that question [whether a lawyer can adopt this output]. Neither does a general claim that a product is grounded... The system must present its sources, scope, conflicts, and unresolved points in a form the lawyer can review within the time available."* Its "known-matter test" scores a system against the five controls, not an accuracy number, and the Complete Guide independently states: *"Avoid relying on a generic accuracy number without the task and scoring method behind it."* Operationally these can conflict: a citation batch could satisfy a 2% aggregate elusion-rate gate while the *specific document* a lawyer is about to sign still contains an unflagged, unreviewed hallucination — which the Verification whitepaper's model treats as categorically unsafe regardless of the passing aggregate rate. The register treats these as complementary layers (R40–R44 as an automated first-pass triage; R32–R38 as the mandatory per-instance gate before signing) rather than resolving the tension, but a design decision is needed on which one is authoritative when they disagree.

**2. Single system-of-record vs. four-way split storage architecture (edisc.md/archive-triage doc vs. Claude chat pipeline transcript's "Salem MCP Gateway").**
edisc.md's consolidated build sequence is explicit: store extracted events and embeddings *"in the project's existing PostgreSQL bitemporal schema... rather than a separate tool like Airtable or standalone SQLite... Introducing a parallel storage system would fragment a custody trail that has already been engineered into the primary database."* This is echoed by the archive-triage doc, which names the bitemporal `sql/0001`–`sql/0018` spine as "the" target schema. The Claude chat-pipeline transcript's "Salem MCP Gateway Server" design — for the same underlying case/project — does the opposite: it splits data across four separate systems (Supabase PostgreSQL for relational records, Neo4j Aura for the entity-relationship graph, Qdrant Cloud for vector search, Cloudflare R2 for object storage), each with its own tool surface, coordinated only by an MCP gateway layer (R18 vs. R25). These directly conflict on whether the custody-hashed bitemporal Postgres schema is meant to be the *sole* system of record or one of several coordinated stores, and the register cannot resolve this without a current architectural decision from the project owner — it is flagged as R25 ("Contested") rather than merged into R18.

**3. Custody hashing as "shadow"/secondary vs. hashing-at-capture as a load-bearing requirement (archive-triage doc, internally, in tension with edisc.md and conversation_ingestion_system_design.md).**
The archive-triage doc reports that the SMS/MMS custody-hashing parser (`sbv_sms.py`) was *"recently demoted from PRIMARY to SHADOW"* in favor of a pure-Python fallback (`sms_xml.py`) with no custody hashing, and separately notes that *"MMS binary media is dropped if SBV is down."* This sits in tension with edisc.md's NIST SP 800-86 requirement that hashing occur "at point of capture" (R20) and with conversation_ingestion_system_design.md's chain-of-custody principle that every chunk carries a SHA-256 hash. If the custody-hashing lane is only a secondary/shadow path rather than the primary one, records ingested while it is unavailable receive no custody hash at all — a gap the archive-triage doc itself flags as a known coverage hole (R15) but does not reconcile against the hashing-at-capture requirement stated elsewhere.
