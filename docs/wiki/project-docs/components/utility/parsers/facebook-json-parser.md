---
title: Facebook JSON Parser
type: reference
status: active
created: 2026-03-30
updated: 2026-03-30
reviewed: 2026-03-30
tags:
  - dial-stack
  - wiki
  - parser
  - facebook
  - mvp
summary: MVP-critical parser note for Facebook JSON exports, including evidence-safe ingest rules and current platform usage.
repo_usage_state: core-mvp
repo_version: parse_facebook_export tool in TS MCP server
upstream_version: current Facebook export format handling reviewed against repo parser path on 2026-03-30
official_docs:
  - "platform export source: Facebook JSON data download"
official_downloads:
  - "user-provided evidence export packages"
---

# Facebook JSON Parser

## At a Glance

- **What it is**: The MVP-priority Facebook evidence parser for JSON exports.
- **Current role in `dial-stack`**: Preferred Facebook ingest path ahead of HTML.
- **Why it matters**: JSON is the cleaner, more evidence-safe Facebook path for the current MVP.

## Current Direction

For Facebook, the current priority is:

- JSON first
- HTML secondary

That choice is deliberate because the JSON export path is easier to normalize reliably and less brittle than HTML scraping-style handling.

## Full-Ingest Contract

If the export contains the field, the ingest path should preserve it.

That includes:

- participants
- timestamps
- message content
- conversation metadata
- attachments and media references when present
- message-level metadata and source export fields

Normalization may add interpreted fields, but it should not silently discard raw evidence-bearing data.

## Evidence Handling Rules

The Facebook JSON path must follow the same core rules as SMS:

- DuckDB first-touch handling
- UUIDv7 linkage
- layered hashing and provenance
- PostgreSQL canonical write before derived enrichment
- Semantica and retrieval layers only after canonical storage

## How `dial-stack` Uses It

Current local anchors:

- [facebook-json-parser.md](C:/Users/matts/Projects/TheBigOne/dial-stack/docs/wiki/skills/utility/parsers/facebook-json-parser.md)
- [index.ts](C:/Users/matts/Projects/TheBigOne/dial-stack/mcp-servers/ts-mcp-server/src/index.ts)
- [DuckDbService.ts](C:/Users/matts/Projects/TheBigOne/dial-stack/mcp-servers/ts-mcp-server/src/services/DuckDbService.ts)

Current intended posture:

- parser support exists through the shared TS MCP parser surface
- it must participate in the same evidence-safe intake path as the SMS XML workflow

## How We Could Expand Its Use

- richer attachment and media reference capture
- better export-variant detection and parser diagnostics
- stronger sample coverage for export variations across Facebook data packages
- analyst-facing provenance views showing source export to normalized record lineage

## What We Need to Watch

- HTML and JSON should not be treated as interchangeable evidence sources
- source export lineage must survive normalization
- attachment metadata should not be discarded just because text extraction is the immediate priority
- parser docs should stay aligned with the actual TS MCP implementation surface

## Key Repo Files

- [index.ts](C:/Users/matts/Projects/TheBigOne/dial-stack/mcp-servers/ts-mcp-server/src/index.ts)
- [DuckDbService.ts](C:/Users/matts/Projects/TheBigOne/dial-stack/mcp-servers/ts-mcp-server/src/services/DuckDbService.ts)
- [facebook-html-parser.md](C:/Users/matts/Projects/TheBigOne/dial-stack/docs/wiki/skills/utility/parsers/facebook-html-parser.md)

## Related Notes

- [[skills/utility/parsers/sms-xml-parser|SMS XML Parser]]
- [[skills/utility/parsers/facebook-html-parser|Facebook HTML Parser]]
- [[skills/database/duckdb|DuckDB]]
- [[skills/database/postgresql|PostgreSQL]]
- [[skills/nlp/semantica|Semantica]]
- [[INDEX|dial-stack Wiki Index]]
