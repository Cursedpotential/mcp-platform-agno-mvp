# ADR-0044: Evidence-vs-Context boundary + forensic transcript data model
- Status: **Accepted** (numbered + accepted by PIPELINE per ORCHESTRATOR greenlight, TASKS 00:05; drafted by PROCESS)
- Date: 2026-06-25 (accepted 2026-06-27); **renumbered ~~ADR-0033~~ → ADR-0044 on 2026-08-05**
- Renumbering note: this ADR was drafted as 0033 on the unmerged branch
  `docs/adr-0033-0034-evidence-model` while, in parallel, `main` shipped a
  *different* ADR-0033 (`0033-server-package-layout-repack.md`, the ADR-0033
  referenced by AGENTS.md and D-027). Two accepted ADRs held the same number.
  The one already merged and cross-referenced across the repo keeps 0033; this
  one takes the next free number. **Its content and accepted status are
  unchanged** — only the identifier moved. Its sibling ADR-0034
  (multi-level custody hashing) kept its number: 0034 was a genuine gap on
  `main`, flagged as "STRANDED" in three docs, and merging it closes that gap.
- _Byline: Claude Code (PROCESS lane, draft) · Opus 4.8 · 2026-06-25_
- Extends: ADR-0017 (evidence polyglot mesh), 0018 (bitemporal), 0020 (multi-domain knowledge)
- Implements: `casebible-coordination/specs/chat-parser-and-custody-hashing-spec.md`

## Context
The 25-file AI-chats pilot ran the evidence vertical and exposed two governance failures: (1) AI chats
were written into the **evidence schema** (`evidence.evidence_hash` / `analysis.normalized_record`), and
(2) the `transcripts.markdown` whole-file fallback **blended User + assistant turns into one blob** with
`participants:['owner']`, no per-message structure, and `occurred_at` NULL. Both are disqualifying for a
forensic system — you cannot blend different people's messages and call it normalized evidence.

## Decision
1. **Evidence-vs-context data boundary (hard).** AI chats / research / notes are **Context Corpus →
   knowledge-only** (Milvus `casebible_ai_conversations`, owned by SORT). They **never** enter the evidence
   schema. The custody/evidence vertical (`evidence.evidence_hash`, `analysis.normalized_record`,
   `casebible_evidence`) is reserved for **primary evidence** (messaging between parties, records, media).
2. **Forensic transcript data model.** Chat/transcript ingestion emits **one `normalized_record` per
   message** — `role` (user|assistant|system|tool), resolved `speaker`, per-message `content`,
   `occurred_at`, `sequence_number`. **Never blend speakers; never a whole-file blob for evidence.**
3. **Best-format selection.** When a conversation exists in multiple formats, ingest the **structured**
   source (JSON/JSONL with real turns + timestamps) over markdown over whole-file; log rejected siblings.
4. **Tiered parser.** Explicit speaker markers (per-platform) → structural heuristics → LLM segmentation
   fallback. The whole-file `transcripts.markdown` parser is the **last resort only and BANNED for evidence.**

## Consequences
- Evidence stays defensible (per-message attribution, citable turns); context stays in the knowledge layer.
- The parser is shared infra: PIPELINE builds it in `evidence/tools/`; SORT reuses it for context ingest.
- Pilot data (AI chats currently in the evidence schema + `casebible_evidence`) is **throwaway** — dumped
  clean before any real-evidence ingest.
- Folder taxonomy mirrors the boundary: `Knowledge/` (context) is a separate top-level from `Evidence/`
  (the type-first sort; the cloud sort/dedupe handoff encodes this).

## Alternatives considered
- Whole-file blob "normalized" — rejected: blends speakers, no timeline, unusable as evidence.
- AI chats in the evidence schema — rejected: they're context, not primary evidence (data-boundary violation).
- Markdown over JSON when both exist — rejected: lossy; structured always wins.
