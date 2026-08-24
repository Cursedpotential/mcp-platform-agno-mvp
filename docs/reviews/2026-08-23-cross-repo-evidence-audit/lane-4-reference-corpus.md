# Lane 4 — Reference Corpus Recommendation Register

> _Byline: Claude Code · Fable 5 · 2026-08-23_
> Extracted from the reference corpus in `C:/Users/matts/Downloads/` for use as a benchmark
> against three codebases. This is an extraction pass only — no code was edited.

## Source inventory and reading notes

| Document | Nature | Depth |
|---|---|---|
| `Mary Technology Whitepaper.pdf` | Vendor thought-leadership whitepaper ("Building the Future of Law") | Full text extracted (12 pp) |
| `Mary Technology Whitepaper - Verification in Legal AI is a Design Problem.pdf` | Vendor thought-leadership whitepaper, heavily cited to case law/studies | Full text extracted (13 pp) |
| `The Complete Guide to Legal Fact Management.md` | Short marketing/blog clipping from marytechnology.com | Full text, thin (~500 words) |
| `edisc.md` | Internal synthesis report (Salem v. Kinzel matter) tying EDRM/Sedona/NIST/TAR standards to a proposed 8-year custody-corpus RAG pipeline | Full text |
| `conversation_ingestion_system_design.md` | Internal design-thread export for a chunk→validate→schema-match→transform→preview→ingest pipeline | Full text |
| `Claude - chat pipeline for PostgreSQL - Claude.md` | Raw chat transcript. Lines 2159–3087 are a **verbatim duplicate** of `conversation_ingestion_system_design.md`; lines 1–2158 are an earlier iteration of the same design conversation (no material decisions not already captured); lines 3094–4352 are unrelated LiteLLM/MCP-gateway infrastructure config, out of scope for this register | Skimmed structurally, no new recommendations beyond the design doc |
| `archive-triage-parser-schema-lineage-2026-08-09.md` | Internal lineage-triage report for parser/schema code across a specific repo | Full text |
| `VLEX-RESEARCH-PROMPTS.md` | **Thin on guidance.** A set of 14 research prompts to run against vLex for a Michigan custody-guide project, plus a save/retention protocol. It is a prompt kit, not a design or standards document — flagged rather than padded. |
| `SocialListeningAPI.md` | **Not a reference document.** A saved clipping of a SaaS dashboard page (API key, credit balance). Contains no actionable recommendation of any kind and is excluded from the register below. |

---

## 1. Document handling & ingest

**R1 — Chunk before format detection ("chunk first, ask questions later")**
Source: `conversation_ingestion_system_design.md`
Chunking should be format-agnostic and happen before parsing/schema work, so files larger than RAM can be processed and chunking isn't blocked on knowing the file's structure.
**SOFT** (design preference, not an evidentiary requirement)

**R2 — Validate and repair chunk structure without data loss**
Source: `conversation_ingestion_system_design.md`
After chunking, validate each chunk's structural integrity (unclosed JSON brackets, incomplete CSV rows at boundaries, unclosed XML tags) and repair *structure only*; never delete or modify actual data. An incomplete record at a chunk boundary stays for the next chunk to complete.
**SOFT**

**R3 — Check known schemas before running discovery**
Source: `conversation_ingestion_system_design.md`
Fingerprint incoming chunks and compare against a library of known schemas (Jaccard + type-matching similarity, >85% = match) before triggering full schema discovery. Saves time on repeated formats and builds institutional knowledge.
**SOFT**

**R4 — Transform/enrich during ingestion, not after**
Source: `conversation_ingestion_system_design.md`
Timezone normalization, code decoding, derived-field calculation, and PII handling should happen in the ingestion pipeline so the output lands analysis-ready, rather than as a later post-processing pass.
**SOFT**

**R5 — Preview before full commit**
Source: `conversation_ingestion_system_design.md`
Always show a sample batch (e.g. 10 records) with an interactive review loop (continue / next batch / modify / fix / quit) before running full ingestion. This is called out as a "critical addition" in the design's own iteration history.
**SOFT**

**R6 — Log ingestion runs and chunk status with hashes**
Source: `conversation_ingestion_system_design.md`
Maintain `ingestion_runs` (source file, schema, transformation config, status, error log) and `chunk_status` (per-chunk validation status, repair log, records processed, errors) tables; chunk metadata includes SHA-256 hashes and a full audit trail of modifications, explicitly framed as a "Court Admissibility" concern.
**SOFT** (self-imposed project discipline; the underlying hashing practice is grounded in a HARD standard — see R12)

**R7 — Plugin/registry architecture for parsers**
Source: `conversation_ingestion_system_design.md` (also `Claude - chat pipeline...md` lines 1–700, same design lineage)
New file formats should be addable as new parser classes registered against a central `ParserRegistry`, rather than hard-coded per-format logic.
**SOFT**

**R8 — Do not re-port superseded parser lineages; triage by live commit + runtime call-sites**
Source: `archive-triage-parser-schema-lineage-2026-08-09.md`
When multiple historical parser implementations exist (archived zips, dead branches, vendored libraries), determine the "winner" by checking what is actually live, registered, and committed on `main`, not by which artifact is newest-uploaded or most feature-complete on paper. A "feature-complete on paper but zero runtime call sites" parser (Semantica in this case) is flagged as a standing gap, not adopted.
**SOFT**

**R9 — Assign a deterministic evidence ID to every source document**
Source: `edisc.md`
Every source document should receive a deterministic evidence ID (e.g. `EX-2021-04-TEXT-01`) at ingest so every downstream extracted event traces back to an exact page or message.
**SOFT** (echoes Bates-numbering discipline but is not itself a codified numbering standard)

**R10 — Hash all evidence at point of capture**
Source: `edisc.md`, citing NIST SP 800-86
Apply SHA-256/MD5 hashing at point of capture and preserve filesystem/EXIF metadata without altering access timestamps; use the NIST NSRL reference set to filter known non-evidentiary files ("de-NISTing").
**HARD** (named federal forensic-acquisition standard)

**R11 — Chunk a long evidentiary corpus into bounded chronological batches**
Source: `edisc.md`
Keep processing batches to roughly 50–100 pages per run to stay within model context limits when running an extraction pass over a multi-year document corpus.
**SOFT**

---

## 2. Search & retrieval

**R12 — Reject flat/uniform chunking for structured or hierarchical content**
Source: `edisc.md`, citing a 2024 study on multi-layered embedding retrieval for legal texts
Index at multiple hierarchical levels simultaneously (whole document → component → structural grouping → article → clause) rather than splitting into equal-sized blocks; the cited study found this recovered a substantially higher share of essential chunks (37.86% vs 16.39%) with fewer unnecessary retrievals.
**SOFT** (backed by a single external study, not a standard)

**R13 — Embed each extracted fact twice: isolated and in conversational context**
Source: `edisc.md`
Store one embedding of an event/fact in isolation (for precise matching) and one with its surrounding exchange attached, tagged to a parent-thread ID, so retrieval doesn't strip a message of the context that gives it meaning — explicitly tied to the project's "nuance IS the abuse" principle.
**SOFT**

**R14 — Apply a similarity-deviation cutoff and de-duplicate overlapping context at retrieval time**
Source: `edisc.md`
Use a roughly 25%-deviation-from-top-match cutoff and a token budget per response, de-duplicating overlapping parent/child context to avoid redundant returns.
**SOFT**

**R15 — Ground LLM outputs in a structured fact/knowledge layer rather than flat RAG alone**
Source: `Mary Technology Whitepaper.pdf`
Combining RAG with a structured knowledge-graph-like layer is argued (citing Barron et al. 2024, Nguyen & Satoh 2024) to reduce hallucination and improve multi-hop reasoning versus RAG alone — though the whitepaper itself notes these hybrids "remain far from flawless."
**SOFT** (vendor thesis, honestly caveated in the source)

**R16 — Do not rely on expanding context-window size to fix retrieval quality**
Source: `Mary Technology Whitepaper.pdf`, citing Li et al. 2024
Longer context alone shows diminishing returns and can amplify contradictions if the underlying data isn't structured; the paper argues this is why raw long-context approaches don't substitute for a fact layer.
**SOFT**

**R17 — Port TAR's elusion-sampling methodology onto RAG citation grounding**
Source: `edisc.md`
Split every RAG output into "grounded" and "flagged/uncertain" buckets, stratify the grounded bucket by citation type and confidence band, draw weekly samples (50–100), have a human independently confirm three things (source exists / pinpoint supports the claim / characterization is accurate), and compute an elusion rate (hallucinated + misgrounded ÷ sample) per stratum. Proposes a working threshold under 2–3% elusion before filing use, with zero tolerance for unreviewed AI output in court-facing documents.
**SOFT** (this is a proposed *adaptation* of TAR methodology to a new problem, not itself an established standard — though the underlying TAR/elusion-testing statistical practice it borrows from is well established in eDiscovery)

**R18 — Use a closed-world citation constraint**
Source: `edisc.md`, citing a practitioner discussion
Constrain the model so it may only cite paragraphs it actually retrieved, with backend regex extraction of cited identifiers checked against a database, as an automated first-pass filter ahead of human elusion sampling.
**SOFT**

---

## 3. Evidence bundling & production

**R19 — Use EDRM-standard load-file formats for cross-platform production**
Source: `edisc.md`
Opticon (.opt/.log) and Concordance (.dat) load-file formats, plus EDRM XML schemas for metadata/folder hierarchy/document relationships, are named as the technical interchange standard for evidentiary production.
**HARD** (named industry standard body)

**R20 — Follow Sedona Principles / Commentary on Defense of Process for culling, dedup, and TAR defensibility**
Source: `edisc.md`
The Sedona Principles (3rd ed.) and the Commentary on Defense of Process are cited as the legal-defensibility backbone for culling, deduplication, and technology-assisted-review decisions.
**HARD**

**R21 — Apply the Sedona Conference's judicial AI framework to guard against automation/confirmation bias**
Source: `edisc.md`, citing "Navigating AI in the Judiciary" (Feb. 2025)
Any AI-assisted review or drafting layer should be designed with explicit awareness that Sedona's judicial guidance calls out automation bias and confirmation bias as named risks.
**HARD** (guidance from an authoritative standards body directed at courts and, by extension, filers before them)

**R22 — Comply with jurisdiction-specific procedural discovery rules**
Source: `edisc.md`
For a Michigan matter, ESI production must additionally satisfy MCR 2.302 (including the (B)(6) proportionality limit), on top of the general EDRM/Sedona/NIST layer.
**HARD** (binding court rule)

**R23 — Map every extracted evidentiary event to the governing statutory taxonomy**
Source: `edisc.md`
Every extracted event in a Michigan custody matter must map to one of the twelve MCL 722.23 Best Interest Factors; the report supplies a factor-to-coverage table as the tagging schema.
**HARD** (statutory basis for the matter's evidentiary relevance)

**R24 — Export final work product as a structured matrix, not narrative prose**
Source: `edisc.md`
Judges and Friend-of-the-Court referees are said to respond better to an 8-column matrix (date/time, category, Best Interest Factor, factual description, quote/evidence summary, exhibit/source ID, contradicting testimony, admissibility/witness source) than to narrative chronology text; a 9th `context_thread_id` field is recommended so a reviewer can pull full conversational context.
**SOFT** (practical/persuasive recommendation, not a codified filing format)

---

## 4. Verification & trust — the Mary whitepapers' core thesis

The second Mary whitepaper's central argument, stated precisely: **"Verification is therefore a design problem: the system must make the basis and limits of its output easy to inspect before someone relies on it."** The mechanism it argues for this claim: verification fails as a purely human-discipline problem because *checking costs consume the time savings the AI was supposed to deliver* — "if verifying an answer means repeating the task that produced it, the time saving disappears and, under deadline pressure, review becomes the step most likely to be cut." It frames this economic pattern as a **"verification tax"** (citing Morae's 2026 survey of 850 senior legal professionals: 67% say verification cost is outweighing AI's efficiency benefit; 48% say humans always/often materially change AI outputs before use).

This reframes "be more careful" as an insufficient answer — the paper marshals a 2026 Wharton study (Shaw & Nave, 9,593 trials) showing that a wrong-but-confident AI made people *worse* than no AI at all (accuracy fell 15 points below baseline, wrong answers accepted 80% of the time, self-confidence still rose 11.7% regardless of correctness) — the named phenomenon is **"cognitive surrender."** The paper's conclusion is that professional exhortation cannot fix a cognitive/economic pattern that operates "at professional scale"; it has to be addressed by what the product exposes, not by asking lawyers to try harder.

**R25 — Design the workflow around five specific, distinct controls**
Source: `Mary Technology Whitepaper - Verification in Legal AI is a Design Problem.pdf`
A checkable workflow needs: (a) source-and-context links on every material claim (not just a citation, but the surrounding passage); (b) explicit gap/scope reporting (what wasn't searched, what's missing, what's unresolved); (c) an independent checking method capable of disagreeing with the generator (a second prompt to the same model does not count); (d) a defined response when support fails (block / warn / escalate — never silently absorbed into polished prose); (e) a mandatory review gate at the point of consequential reliance (signing, filing, exporting), not merely a source link the reviewer can ignore. The paper is explicit that each control addresses a *different* failure mode and none substitutes for another.
**SOFT** (product-design prescription; grounded in but distinct from the HARD duties in ABA Formal Opinion 512, which it cites as the source of the underlying professional obligations)

**R26 — Responsibility for filed/adopted work is non-delegable**
Source: `Mary Technology Whitepaper - Verification in Legal AI is a Design Problem.pdf`
FRCP 11's Advisory Committee note describes the presenter's responsibility to the court as nondelegable; Rule 11 also makes the firm jointly responsible for a partner/associate/employee's violation. Recent state measures reinforce rather than alter this allocation: Florida Rule 2.515(d)(2) (eff. June 15, 2026) requires a signer to represent that cited authorities "exist and are accurately cited"; California Rule 10.430 requires "meaningful human review" policies; Illinois requires thorough review of AI-generated content before court submission; New York's Part 161 permits an optional model rule with a review-and-certification requirement. The paper's framing: **"You can delegate the reading. You cannot delegate the signature."**
**HARD** (federal rule + four state court rules/policies, cited to source and effective dates)

**R27 — Evaluate legal AI systems with a "known-matter test," not a generic accuracy score**
Source: `Mary Technology Whitepaper - Verification in Legal AI is a Design Problem.pdf`; corroborated independently in `The Complete Guide to Legal Fact Management.md`
Test a system against a matter the firm's own lawyers already understand, then inspect: support for each material conclusion, documents/periods excluded from the search, unresolved conflicts, and points where a person had to judge how the work could be used — scored against the five controls above. The companion short guide states the same idea independently: "Use a closed matter with a reference record reviewed by lawyers who know the file... Avoid relying on a generic accuracy number without the task and scoring method behind it."
**SOFT**

**R28 — Guard against skill atrophy in junior lawyers exposed only to finished AI output**
Source: `Mary Technology Whitepaper - Verification in Legal AI is a Design Problem.pdf`
Cites a colonoscopy-AI deskilling study (unassisted detection rate fell from 28.4% to 22.4% after 3 months of AI-assisted practice) as an analogy: junior lawyers build judgment by working the record directly (ordering facts, checking sources, resolving contradictions), and a workflow that shows them only finished AI output risks producing lawyers with less practice at the skill their eventual signature represents.
**SOFT** (explicitly analogical — the paper states "the direct evidence on lawyer skill development under AI assistance doesn't yet exist")

---

## 5. Fact management

**R29 — Separate document storage/retrieval from fact-level structuring**
Source: `The Complete Guide to Legal Fact Management.md`; `Mary Technology Whitepaper.pdf`
"A document management or eDiscovery system can hold and retrieve the files. The legal team still has to identify the people, events, dates, conflicts and gaps across them." A fact layer is framed as a distinct system responsibility from document storage, not a feature bolted onto it.
**SOFT** (Mary's core product thesis; a reasonable design distinction, not an external norm)

**R30 — Every fact record should carry source, context, review status, and conflict status**
Source: `The Complete Guide to Legal Fact Management.md`
"A factual record should show what happened, who was involved, when it occurred, which document supports the statement, whether accounts conflict, whether expected material is missing and whether a lawyer has reviewed or corrected the fact."
**SOFT**

**R31 — Persist and propagate lawyer corrections to downstream outputs**
Source: `The Complete Guide to Legal Fact Management.md`; `Mary Technology Whitepaper.pdf`
"The record should evolve as new documents arrive and corrections are made"; the whitepaper frames this as a requirement that AI-driven summaries and drafting reuse the corrected fact layer rather than regenerating from raw documents each time.
**SOFT**

**R32 — Distinguish claims/allegations from verified statements of truth by source context**
Source: `Mary Technology Whitepaper.pdf`
The same sentence ("Rowan stole a computer") carries different evidentiary weight depending on who said it, where (sworn testimony vs. casual text), and why (testimony vs. preliminary allegation) — a fact layer should tag and track this provenance rather than flattening every statement into an undifferentiated "fact."
**SOFT**

**R33 — Track contradictions as first-class objects, not incidental notes**
Source: `Mary Technology Whitepaper.pdf`
Worked example: a fact layer should unify every mention of a fact whose value changed over time (an incident date corrected from 15 March to 20 March), showing exactly when the error was introduced, who repeated it, and how it was resolved.
**SOFT**

---

## 6. Schema & lineage

**R34 — Maintain one live schema spine; do not fragment custody trail across parallel stores**
Source: `archive-triage-parser-schema-lineage-2026-08-09.md`; `edisc.md`
Once a bitemporal Postgres schema (`analysis.normalized_record`, with `occurred_at`/`knowledge_time`/`disclosure_tier` and evidence custody hashing) exists as the target, extracted records and embeddings should be stored there rather than in a separate tool (Airtable, standalone SQLite), because introducing a parallel system fragments a custody trail already engineered into the primary database.
**SOFT** (internal architectural discipline motivated by, but distinct from, the HARD chain-of-custody requirement itself)

**R35 — Distinguish "design reconciled" from "verified applied to the live database"**
Source: `archive-triage-parser-schema-lineage-2026-08-09.md`
A behavioral/ontology schema migration merging nine prior fragmented iterations exists as a design artifact, but per the project's own reconciliation report is "DRAFT / paper-only... nothing here has been applied or diffed against the running DB." The recommendation: treat deployment verification as the actual next action, not re-extraction of already-reconciled source material.
**SOFT**

**R36 — Triage competing schema/parser lineages by live commit recency and runtime call-sites, not upload recency or apparent completeness**
Source: `archive-triage-parser-schema-lineage-2026-08-09.md`
When several historical schema or parser lineages exist (a live SQL spine vs. dead Drizzle/TypeScript schemas vs. a newest-uploaded-but-unreconciled extraction scaffold), determine "current" by grepping for actual imports/call-sites in the live repo, not by which artifact was most recently handed over.
**SOFT**

**R37 — Minimal chain-of-custody schema: ingestion run + chunk status tables**
Source: `conversation_ingestion_system_design.md`
Concrete DDL landed on: `ingestion_runs(source_file, chunk_folder, schema_name, transformation_config JSONB, started_at, completed_at, total_chunks, total_records, status, error_log)` and `chunk_status(ingestion_run_id FK, chunk_number, chunk_file, validation_status, repair_log JSONB, records_processed, errors JSONB, processed_at)`.
**SOFT** (concrete schema decision, offered as a reusable minimal pattern rather than a standard)

---

## Documents flagged as thin / non-substantive rather than padded

- **`VLEX-RESEARCH-PROMPTS.md`** is a set of 14 legal-research prompts (plus a save/retention protocol) for running against vLex on a specific Michigan custody-guide project. It contains almost no generalizable system-design guidance — its only transferable pattern is the discipline of the standard instruction block (require full citation, court/issuing body, pinpoint, effective date, subsequent history, and an explicit `UNSUPPORTED` outcome rather than silence) and the file-naming/hash-on-save convention in its closing section. Everything else is matter-specific legal research scaffolding, not a recommendation for a codebase.
- **`SocialListeningAPI.md`** is a captured SaaS dashboard page (API key, credit balance, a curl example). It carries no design or process recommendation and was excluded from the register entirely rather than stretched to fit a theme.
