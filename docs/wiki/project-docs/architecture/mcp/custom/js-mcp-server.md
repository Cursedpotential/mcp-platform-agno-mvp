# JS MCP Server Tools — Complete Documentation

**Server:** dial-js-core (port 8083)
**Transport:** HTTP (StreamableHTTPServerTransport)
**Tags:** `legacy`, `document-processing`
**Status:** 1 built (placeholder), 4 planned

---

## Current State

**⚠️ MINIMAL PLACEHOLDER** — Only `ping_js_server` tool exists. Server consumes container resources with no functional tools. Per IMPLEMENTATION_HANDOFF.md: "js-mcp-server/src/index.js is an empty placeholder with only a ping_js_server tool. It consumes container resources for nothing."

---

## Built Tools

### `ping_js_server`
- **Description:** Health check ping
- **Input:** None
- **Output:** "Pong from dial-js-core!"
- **Status:** ✅ Built (placeholder)

---

## Planned Tools

### `docling_convert`
- **Description:** Convert documents via Docling API
- **Purpose:** Convert complex documents (PDFs, DOCXs, PPTs) to structured text with layout preservation
- **Planned Features:**
  - Extract structured text from multi-column PDFs
  - Preserve document hierarchy and reading order
  - Detect and extract tables, figures, metadata
  - Output to JSON, Markdown, or plain text
  - OCR support for scanned documents
- **Status:** ⏳ Planned — NOT INTEGRATED
- **Skill:** `docs/wiki/skills/utility/document-processing/docling.md`

### `pandoc_convert`
- **Description:** Convert between document formats via Pandoc
- **Purpose:** Universal document format converter
- **Planned Features:**
  - Support 30+ document formats
  - Preserve document structure during conversion
  - Handle styling and metadata preservation
  - Support custom filters and templates
  - Input: DOCX, ODT, RTF, LaTeX, Markdown, HTML, PDF (text)
  - Output: Markdown, HTML, DOCX, PDF, LaTeX, Reveal.js slides
- **Status:** ⏳ Planned — NOT INTEGRATED
- **Skill:** `docs/wiki/skills/utility/document-processing/pandoc.md`

### `chatgpt_json_parser`
- **Description:** Parse ChatGPT conversation exports
- **Legacy Source:** `Evidence_Analysis/Scripts/chatgpt_parser.py`
- **Status:** ⏳ Planned

### `google_timeline_parser`
- **Description:** Parse Google Timeline location data
- **Legacy Source:** `Evidence_Analysis/Scripts/parser.py`
- **Status:** 🅿️ **PARKED — not planned.** Owner directive, emphatic, 2026-07-03 and again
  2026-08-09 (~87 prior iterations); the messaging/transcript lane goes first. Do not propose
  Timeline work until the owner raises it. See ADR-0048. Corrected from "⏳ Planned"
  2026-08-10 — _Claude Code · Opus 5_

---

## Recommendation

Either implement Docling/Pandoc now if there's near-term need, or remove the container from docker-compose.yml until tools are ready. Currently consuming resources with no functional output.
