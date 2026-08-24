# Review Scope

> _Byline: Claude Code · Opus 5 · 2026-08-23_

## Target

Gap / issue / opportunity analysis across three local repos, focused on
**document handling, search & retrieval, and evidence bundling**, benchmarked
against the recommendations in eight supplied reference documents.

This is an ANALYSIS deliverable, not a refactor. Applying the zero-tech-debt
lens: recommendations are framed as intended-end-state + what to delete,
not as incremental patches.

## Repos (local paths — remotes are the GitHub links given)

| Repo | Local path | Remote |
|---|---|---|
| mcp-platform-agno-mvp | `Agno-MCP-Platform/` | Cursedpotential/mcp-platform-agno-mvp |
| Legal-Workspace | `Legal-Workspace/` | Cursedpotential/Legal-Workspace |
| sbv-forensic | `Agno-MCP-Platform/vendored/sbv/` | vendored into the Agno repo |

All paths relative to `E:/AI_Workspace/Projects/the-platform-workspace`.

## Reference corpus (C:/Users/matts/Downloads)

- Mary Technology Whitepaper.pdf
- Mary Technology Whitepaper - Verification in Legal AI is a Design Problem.pdf
- The Complete Guide to Legal Fact Management.md
- edisc.md
- conversation_ingestion_system_design.md
- Claude - chat pipeline for PostgreSQL - Claude.md
- archive-triage-parser-schema-lineage-2026-08-09.md
- VLEX-RESEARCH-PROMPTS.md
- SocialListeningAPI.md

## Flags

- Security Focus: no (not the ask)
- Performance Critical: no
- Strict Mode: no
- Framework: Python/FastAPI + PostgreSQL (Agno, Legal-Workspace); Go + SQLite (sbv)

## Review lanes (parallel subagents)

1. Agno-MCP-Platform — ingest, evidence, custody, schema lineage
2. Legal-Workspace — matter/document model, UI, bundling
3. sbv-forensic — message evidence, custody hashing, universal imports
4. Reference corpus — extract every actionable recommendation
5. Cross-cutting — search/retrieval architecture across all three
