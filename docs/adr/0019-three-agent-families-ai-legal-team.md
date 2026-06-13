# ADR-0019: Three agent families — add the AI Legal Team (Part 3)
- Status: Accepted
- Date: 2026-06-11
- Extends: ADR-0006 (two-layer team topology: root Router over coordinate families).

## Context
The platform's purpose is threefold: process evidence (Part 1), analyze it (Part 2), and **assist
the owner's pro se family-law case** (Part 3) — strategy, motions, filings, discovery. The owner has
already prototyped the legal assistant as **Gemini Gems + personas**; it will be ported to Agno. This
is where the imported Michigan legal skills + the MCL 722.23 ontology engage.

## Decision
The root Router (`mode=route`) dispatches to **three** coordinate families (was two):
1. **Platform Ops** — ingestion / analysis / review (the evidence pipeline).
2. **Builder** — Dev Copilot / Project PAL / Forensic Data (bootstraps the platform itself).
3. **AI Legal Team** (new, to build) — ported from the owner's Gemini Gems personas; uses evidence +
   the domain-separated knowledge base (ADR-0020) + Michigan legal skills to produce strategy,
   documents, and filings. Pro se context.
Document Digest (Gemini long-context) and Cloud Drive Cleanup remain standalone.

## Consequences
- Router instructions + eval cases gain the Legal family (routing reliability must cover 3 families).
- The Legal Team reads `legal_strategy` + `timeline_relationship` knowledge domains + evidence;
  it does not perform custody ops.
- Stable agent keys extend to the legal agents (UI/tests depend on them).
- Building the Legal Team is a later round; topology + routing slot reserved now.

## Alternatives considered
- Keep legal work in the Gemini Gems UI — rejected: it can't reach the evidence graph or knowledge
  base; the value is grounding strategy in the actual processed evidence.
- One generalist legal agent — rejected: the owner's persona set maps to a coordinate family.
