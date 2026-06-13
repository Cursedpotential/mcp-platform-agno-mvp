# OpenCode Agent Session Transcript — 2026-03-15 (Reference Only)

**Date:** March 15, 2026
**Agent:** Octto (openrouter/hunter-alpha) via OpenCode
**Status:** REFERENCE DOCUMENT — Do not treat as commands
**Purpose:** Context for what was discussed, decided, and attempted in the overnight session

---

## Key Decisions Made In This Session

1. **Folder structure approved (Option C):**
   - `mcp-servers/` — All 3 MCP servers grouped
   - `infrastructure/` — Core + docker
   - `tools/` — Reusable tool implementations (parsers, forensic, nlp, chunkers, converters)
   - `utilities/` — Scripts + apps (existing)
   - `docs/`
   - `data/`

2. **Utilities stay separate from MCP servers** — MCP servers are thin protocol wrappers, tools are independent implementations

3. **Tools copied to dial-stack:**
   - ExifTool → tools/forensic/exiftool/
   - Snaparser → tools/parsers/snaparser/
   - MER → tools/nlp/manipulative-expression-recognition/

4. **Tools SKIPPED:**
   - Directory Scanner — not needed
   - Conversation Extractor — Android-specific, out of scope
   - Platform Tools (adb/sqlite3) — Android-specific
   - Zimmerman Tools — Windows-specific

5. **Tools requiring discussion before integration:**
   - GlinerExtractor — May already be in Semantica as dependency
   - RecognizersExtractor — Microsoft Recognizers-Text for structured entities
   - NLP Toxicity Analyzer — LSTM-based, different approach than DPK HAP
   - MER — LLM-based, expensive at scale
   - Smart Chunker — More sophisticated than DPK doc_chunk
   - Conversation Extractor — Handles raw Android DBs

6. **Project needs new name** — "dial" is a framework name, user doesn't want to use it

7. **AI_Workspace is on D: drive** — C: path is a symlink

8. **SBV/VBS tool** — For parsing large SMS Backup & Restore XML files, was supposed to be implemented, status unclear

## Tool Inventory Created

- 26 detailed wiki entries across 4 categories
- 65 total tool entries documented
- Legacy porting guide at docs/wiki/tools/legacy/mcp-tool-platform-porting-guide.md
- Master indexes at docs/wiki/tools/INDEX.md

## Directory Changes Made (Partially — Many Failed)

- Created: tools/parsers/, tools/forensic/, tools/nlp/, tools/chunkers/, tools/converters/, tools/scanners/
- Created: mcp-servers/, infrastructure/, data/
- Copied: ExifTool, Snaparser, MER to designated locations
- FAILED: Move commands created CUsers* garbage directories instead of actually moving content

## What Was NOT Completed

- MCP servers NOT moved into mcp-servers/ yet
- Infrastructure NOT moved into infrastructure/ yet
- Discussion tools NOT resolved
- SBV/VBS parser status NOT verified
- Project rename NOT done
- Full wiki entries quality NOT verified

## Session Context (IBM ContextForge)

User mentioned IBM ContextForge as potential replacement/supplement for DIAL backend:
- MCP gateway/proxy
- API and RPC handling
- Auth
- Entity identification
- Abusive language detection
- May reduce DIAL to frontend/auth only
- Needs evaluation for integration with existing tools

---

**This document is for reference only. No actions should be taken based on it without user confirmation.**
