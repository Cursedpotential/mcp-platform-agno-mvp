# Review Scope

> _Byline: Claude Code · Opus 5 · 2026-08-23_

## Target

Cross-repo gap / issue / opportunity analysis of **document handling, search, and evidence
bundling** across the three platform repos, measured against the recommendations contained in
eight supplied reference documents.

This is a domain-focused review, not a generic code-quality sweep. The `full-review` phase
structure is retained; the agent briefs are re-pointed at the document/search/evidence surface.

## Repos under review

| Repo | Local path | Notes |
|---|---|---|
| `mcp-platform-agno-mvp` | `E:/AI_Workspace/Projects/the-platform-workspace/Agno-MCP-Platform` | nested repo, gitlinked |
| `Legal-Workspace` | `E:/AI_Workspace/Projects/the-platform-workspace/Legal-Workspace` | nested repo, gitlinked |
| `sbv-forensic` | `<scratchpad>/sbv-forensic` | **no local clone existed** — shallow-cloned read-only for this review. Private fork of `lowcarbdev/sbv` (MIT) w/ forensic extensions. Salvage artifacts also at `the-platform-workspace/extracted-code/sbv` |

## Reference documents (recommendation sources)

- `Mary Technology Whitepaper.pdf`
- `Mary Technology Whitepaper - Verification in Legal AI is a Design Problem.pdf`
- `SocialListeningAPI.md`
- `archive-triage-parser-schema-lineage-2026-08-09.md`
- `Claude - chat pipeline for PostgreSQL - Claude.md`
- `conversation_ingestion_system_design.md`
- `VLEX-RESEARCH-PROMPTS.md`
- `edisc.md`
- `The Complete Guide to Legal Fact Management.md`

All under `C:/Users/matts/Downloads/`.

## Flags

- Security Focus: no (not requested)
- Performance Critical: no
- Strict Mode: no
- Framework: mixed — Python/FastAPI (Agno, Legal-Workspace API), Next.js (Legal-Workspace web), Go (sbv-forensic)

## Review Phases

0. Source distillation + repo capability mapping (parallel)
1. Capability gaps & architecture coherence
2. Evidence integrity & retrieval quality
3. Testing & documentation of the evidence path
4. Opportunities & consolidation (zero-tech-debt lens)
5. Consolidated report
