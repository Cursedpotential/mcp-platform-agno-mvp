---
title: SMS XML Parser
type: reference
status: active
created: 2026-03-30
updated: 2026-03-30
reviewed: 2026-03-30
tags:
  - dial-stack
  - wiki
  - parser
  - sms
  - mvp
summary: MVP-critical parser note for Android SMS Backup and Restore XML, including full-ingest requirements, evidence-handling rules, and current implementation direction.
repo_usage_state: core-mvp
repo_version: parse_sms_xml tool in TS MCP server; evidence-safe SMS ingest workflow present in ts-mcp-server index
upstream_version: local SBV tooling selected as preferred standalone base; integration version not yet pinned
official_docs:
  - "local resource: D:/Users/matts/Downloads/sbv-main.zip"
  - "local resource: C:/Users/matts/Projects/TheBigOne/MCP_Tool_Platform-REF-READ-ONLY/docs/SBV_MCP_INTEGRATION.md"
official_downloads:
  - "local resource: D:/Users/matts/Downloads/sbv-main.zip"
  - "local resource: C:/Users/matts/sms-exporter-ui"
---

# SMS XML Parser

## At a Glance

- **What it is**: The MVP-priority message parser for Android SMS Backup and Restore XML exports.
- **Current role in `dial-stack`**: First message-ingest path to harden end to end.
- **Why it matters**: This is the fastest route to an evidence-safe message pipeline that handles real exported phone data.

## Current Direction

The current direction is:

- preserve `SBV` as a standalone app/tool
- make it callable from the backend as a tool surface
- use the TS MCP layer to enforce evidence-safe intake into DuckDB and PostgreSQL

This parser note is not just about XML parsing. It is about full-fidelity evidence ingest.

## Full-Ingest Contract

If the export contains it, we ingest it.

That means:

- SMS
- MMS text-bearing content
- call records
- message status fields
- call result and outcome fields
- blocked, accepted, rejected, missed, refused, voicemail, zero-duration, and related status indicators
- raw metadata and parser-visible source fields

Nothing evidence-bearing should be silently dropped because it looks secondary.

## Evidence Handling Rules

The SMS XML path must follow:

- DuckDB first
- UUIDv7 linkage
- 3-level hashing target
- raw preservation before normalization
- provenance-safe write ordering

Working order:

`SMS XML -> parser/tool -> DuckDB first-touch handling -> PostgreSQL normalized write -> Semantica + LanceDB -> PostgreSQL enrichment`

## How `dial-stack` Uses It

Current local anchors:

- [SmsXmlParser.ts](C:/Users/matts/Projects/TheBigOne/dial-stack/mcp-servers/ts-mcp-server/src/tools/SmsXmlParser.ts)
- [index.ts](C:/Users/matts/Projects/TheBigOne/dial-stack/mcp-servers/ts-mcp-server/src/index.ts)
- [DuckDbService.ts](C:/Users/matts/Projects/TheBigOne/dial-stack/mcp-servers/ts-mcp-server/src/services/DuckDbService.ts)

Current tool posture:

- parsing exists
- evidence-safe workflow wiring exists in outline
- full ingest fidelity and hash/linkage hardening still need continued implementation discipline

## How We Could Expand Its Use

- fold SBV more cleanly into a callable backend-tool contract
- add richer MMS and attachment handling
- tighten status and outcome normalization while still preserving raw codes
- add parser-version recording and more formal sample coverage testing

## What We Need to Watch

- parsing only the “useful” fields would violate the ingest contract
- status/result fields must survive normalization
- evidence linkage must survive every stage of the workflow
- parser upgrades should be treated as evidence-affecting changes, not casual refactors

## Key Repo and Local Resources

- [SmsXmlParser.ts](C:/Users/matts/Projects/TheBigOne/dial-stack/mcp-servers/ts-mcp-server/src/tools/SmsXmlParser.ts)
- [index.ts](C:/Users/matts/Projects/TheBigOne/dial-stack/mcp-servers/ts-mcp-server/src/index.ts)
- [SBV_MCP_INTEGRATION.md](C:/Users/matts/Projects/TheBigOne/MCP_Tool_Platform-REF-READ-ONLY/docs/SBV_MCP_INTEGRATION.md)
- [sbv-main.zip](D:/Users/matts/Downloads/sbv-main.zip)
- [sms-exporter-ui](C:/Users/matts/sms-exporter-ui)

## Related Notes

- [[skills/utility/parsers/facebook-json-parser|Facebook JSON Parser]]
- [[skills/database/duckdb|DuckDB]]
- [[skills/database/postgresql|PostgreSQL]]
- [[skills/nlp/semantica|Semantica]]
- [[INDEX|dial-stack Wiki Index]]
