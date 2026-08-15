# Platform Blueprint

> **SUPERSEDED REVIEW COPY 2026-08-15:** unique historical findings are
> preserved here, but the current human-facing blueprints are
> `../PRODUCT-BLUEPRINT-2026-08-15.md`,
> `../ARCHITECTURE-BLUEPRINT-2026-08-15.md`, and
> `../MIGRATION-DIAGRAMS-2026-08-15.md`; generated-agent contract lives in
> `../../.agents/blueprint/`. Do not execute this older AgentOS-centered plan.
> _Banner byline: Codex · GPT-5 · 2026-08-15._


> _Byline: Claude Code · Opus 4.8 · 2026-08-10; ADR-0053 amendment Codex · GPT-5 ·
> 2026-08-13_
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
— landing in **five knowledge lanes** (platform · legal · personal_history · context · evidence),
with relationship history inside personal_history and evidence remaining custody-only.
**Today** that pipeline is not built: two disconnected ingest paths each do part of the job,
Semantica extraction is unwired, no change-detection exists, and AI chats bypass SBV.

## Navigation

| Layer | Doc | Covers |
|---|---|---|
| 1 — Architecture | [architecture.md](architecture.md) | System context · DFD (current + forward) · deploy topology |
| 2 — Structure | [structure.md](structure.md) | Five-lane knowledge ERD · parser registry · agent→lane map |
| 3 — Features | [features.md](features.md) | Conversation→timeline flow · feature hierarchy |

## Source-of-truth pointers

- Ingest pipeline flow: **ADR-0051** (`docs/adr/0051-ingest-pipeline-parse-extract-verify.md`)
- Knowledge-base structure: **ADR-0053** (supersedes ADR-0050's taxonomy)
- SBV as universal parser: **ADR-0049**
- Evidence/context boundary + transcript model: **ADR-0044**
- Semantica extraction worker: **ADR-0043**
- Current-reality gap + decisions: **DECISION_LOG D-045**
