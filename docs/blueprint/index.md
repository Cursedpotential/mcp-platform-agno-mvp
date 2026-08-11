# Platform Blueprint

> _Byline: Claude Code · Opus 4.8 · 2026-08-10_
> **Mode:** hybrid — reverse (what IS, verified in code this session) + forward (ADR-0051 target, labeled).
> **Provenance:** built from this session's smart-explore passes + direct code reads; live container
> inventory from `ovh-app`/`ovh-files` (2026-08-10); ADRs 0043/0044/0049/0050/0051.
> Every diagram carries a provenance line; unverified elements are marked `%% UNVERIFIED` and listed
> in each doc's Open Questions.

## What this is

The three-layer picture of the Agno-MCP-Platform ingest + knowledge system — the diagram that
replaces re-explaining the architecture. Current reality and the ADR-0051 target, side by side.

## One-paragraph system summary

Source files (evidence, SMS, AI chats) are meant to flow through **one** pipeline: **SBV** parses
and previews, hands off to an **extraction** stage (chunk → multipass → entities → timeline)
triggered by **Postgres change-detection**, then **HITL** verifies before anything becomes canonical
— landing in **six knowledge lanes** (platform · legal · personal_history · relationship_timeline ·
context · evidence), the custody-hash tier being the only branch between evidence and context.
**Today** that pipeline is not built: two disconnected ingest paths each do part of the job,
Semantica extraction is unwired, no change-detection exists, and AI chats bypass SBV.

## Navigation

| Layer | Doc | Covers |
|---|---|---|
| 1 — Architecture | [architecture.md](architecture.md) | System context · DFD (current + forward) · deploy topology |
| 2 — Structure | [structure.md](structure.md) | Six-lane knowledge ERD · parser registry · agent→lane map |
| 3 — Features | [features.md](features.md) | Conversation→timeline flow · feature hierarchy |

## Source-of-truth pointers

- Ingest pipeline flow: **ADR-0051** (`docs/adr/0051-ingest-pipeline-parse-extract-verify.md`)
- Knowledge-base structure: **ADR-0050** (`docs/adr/0050-six-lane-knowledge-architecture.md`)
- SBV as universal parser: **ADR-0049**
- Evidence/context boundary + transcript model: **ADR-0044**
- Semantica extraction worker: **ADR-0043**
- Current-reality gap + decisions: **DECISION_LOG D-045**
