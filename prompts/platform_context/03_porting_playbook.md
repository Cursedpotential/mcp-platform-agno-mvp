# Porting Playbook: Alpha → Current

## How to Port a Tool: The Standard Process

1. **Read the alpha implementation** — understand the logic, inputs, outputs, edge cases
2. **Read the current target** — understand the MCP server structure, tool registration pattern
3. **Design the interface** — define the tool name, parameters, return type
4. **Implement** — write the tool function with proper error handling
5. **Register** — add it to the server's tool registration
6. **Write tests** — integration test with fixture data
7. **Update docs** — PARITY_MATRIX.md, GROUND_TRUTH.md, TODO.md

## P0: Immediate Blockers (Unblock Ingestion)

### P0-1: Wire Facebook Parser into EvidenceIngestor

**Problem:** `FacebookExportParser.ts` has ~250 lines of real implementation with dual HTML structure support, fuzzy date parsing, message type detection. But `EvidenceIngestor.ts` lines 103-108 hardcoded reject `.html`/`.htm` files.

**Alpha source to reference:** `server/mcp/loaders/facebook-parser.ts`
**Current file to modify:** `mcp-servers/ts-mcp-server/src/tools/EvidenceIngestor.ts`

**Specific change needed:**
```typescript
// EvidenceIngestor.ts ~line 103
// BEFORE:
return { status: 'unsupported_format', message: 'Facebook HTML parsing is a planned addition — requires owner approval' }

// AFTER:
if (ext === '.html' || ext === '.htm') {
  const facebookParser = new FacebookExportParser();
  const result = await facebookParser.parse(filePath, fileBuffer);
  return { status: 'parsed', data: result };
}
```

**Also needed:**
- Wire SHA-256 hash computation before parsing (first touch requirement)
- Wire DuckDB vault logging after parsing
- Add `.html`/`.htm` to the supported extensions check at the top of `EvidenceIngestor.ts`
- Test with actual Facebook HTML export files

**Estimated effort:** 1 day
**Blocker:** Owner (Matt) approval to activate

---

### P0-2: Port iMessage PDF Parser

**Problem:** `ImessagePdfParser.ts` is a pure stub — `parse()` throws `"iMessage PDF parser is not yet implemented."`

**Alpha source:** `server/mcp/loaders/pdf-imessage-parser.ts` — this is a WORKING implementation
**Current stub:** `mcp-servers/ts-mcp-server/src/tools/ImessagePdfParser.ts` (28 lines)

**What the alpha implementation does:**
1. Opens PDF with PDF parsing library
2. Extracts text content page by page
3. Uses regex to identify iMessage-specific formatting (timestamps, sender names, message bubbles)
4. Parses message direction (sent vs received) based on alignment/ styling
5. Generates SHA-256 hash of original PDF
6. Returns normalized message array with metadata

**Porting steps:**
1. Read `pdf-imessage-parser.ts` from alpha — understand regex patterns and PDF library usage
2. Check current TS MCP server dependencies — does it already have a PDF library?
3. If not, add `pdf-parse` or `pdfjs-dist` to `package.json`
4. Reimplement in `ImessagePdfParser.ts` following the same patterns as `SmsXmlParser.ts`
5. Wire into `EvidenceIngestor.ts` for `.pdf` files
6. Add test fixtures (sample iMessage PDF export)

**Estimated effort:** 2-3 days
**Blocker:** None

---

### P0-3: Port production-message-schemas.ts from Alpha

**Problem:** Alpha has `production-message-schemas.ts` with shared TypeScript interfaces for normalized messages. Current has extensions (pgvector fields, device_id, WAL) but the base schema isn't merged.

**Alpha source:** Look for `message-schemas.ts` or `production-message-schemas.ts` in alpha
**Current target:** `mcp-servers/ts-mcp-server/src/types/` or similar

**What needs merging:**
- Base message interface (id, timestamp, sender, content, direction, platform)
- Alpha extensions (thread_id, group_chat, attachments)
- Current extensions (pgvector embedding vector, device_id, WAL LSN)

**Estimated effort:** 1 day
**Blocker:** None

---

## P1: High-Value Ports (Next Sprint)

### P1-1: Port Pattern Analyzer from Alpha

**Alpha:** `server/mcp/forensics/pattern-analyzer.ts` — behavioral pattern detection
**Current gap:** PY-005 in TODO.md — not started
**Target:** Py MCP server — add as `semantica_detect_patterns` or `forensic_pattern_analyze`

**What it does:**
- Detects communication patterns in message data (frequency, timing, response latency)
- Identifies behavioral anomalies (sudden silence, burst communication, time-of-day shifts)
- Flags potential coercive control patterns
- Generates pattern reports with confidence scores

**Porting approach:**
1. Read `pattern-analyzer.ts` — understand the pattern detection algorithms
2. Port the core logic to Python (likely uses pandas/numpy for time series)
3. Register as MCP tool in Py server
4. Add tests with synthetic conversation data

**Estimated effort:** 2-3 days

---

### P1-2: Port HurtLex Integration from Alpha

**Alpha:** `server/mcp/forensics/hurtlex-fetcher.ts` + `hurtlex-stream.ts`
**Current gap:** PY-006 in TODO.md — not started
**Target:** Py MCP server — add as `dpk_hurtlex_analyze` or similar

**What it does:**
- Fetches HurtLex lexicon (multilingual lexicon of abusive language)
- Streams large texts through HurtLex analysis
- Categorizes hurtful language by type (reliability, physical, mental, etc.)
- Returns scored analysis with term matches

**Porting approach:**
1. HurtLex data is downloadable (open lexicon)
2. Port the streaming analysis logic to Python
3. Integrate with existing `dpk_hap_score` tool as complementary analysis
4. Add lexicon loading/caching

**Estimated effort:** 1-2 days

---

### P1-3: Port Conversation Segmentation from Alpha

**Alpha:** `server/mcp/analysis/conversation-segmentation.ts`
**Current gap:** No equivalent in current platform
**Target:** Py MCP server — Semantica NLP pipeline

**What it does:**
- Segments long conversations into logical topic-based segments
- Detects topic shifts using NLP heuristics
- Useful for breaking up long chat transcripts before analysis

**Estimated effort:** 2-3 days

---

### P1-4: Port Timeline Generator from Alpha

**Alpha:** `server/mcp/forensics/timeline-generator.ts`
**Current gap:** No equivalent
**Target:** Py MCP server

**What it does:**
- Generates chronological timelines from forensic evidence
- Correlates events across multiple data sources (SMS, Facebook, iMessage)
- Outputs structured timeline with provenance

**Estimated effort:** 2-3 days

---

### P1-5: Activate Pandoc Document Intelligence Engine

**Current:** `mcp-servers/py-mcp-server/document_intelligence/engines/pandoc_engine.py` — STUB
**Alpha:** `server/mcp/plugins/document-processors.ts` — WORKING Pandoc integration

**What needs to happen:**
1. Py server engine file exists but has no implementation
2. Port the Pandoc subprocess invocation from alpha
3. Wire into DocumentIntelligenceRouter
4. Register MCP tool for document conversion

**Estimated effort:** 2-3 days

---

### P1-6: Activate Tesseract OCR Engine

**Current:** `mcp-servers/py-mcp-server/document_intelligence/engines/tesseract_engine.py` — STUB
**Alpha:** `server/mcp/plugins/ocr.ts` — WORKING OCR integration

**What needs to happen:**
1. Port Tesseract/OCRmyPDF subprocess invocation
2. Handle image-to-text and PDF-to-text extraction
3. Wire into DocumentIntelligenceRouter
4. Register MCP tool

**Estimated effort:** 2-3 days

---

## P2: Medium Priority (Following Sprint)

| # | Task | Alpha Source | Current Target | Effort |
|---|------|-------------|----------------|--------|
| P2-1 | Port stats/observability collector | `stats/collector.ts` | New module | 2 days |
| P2-2 | Port export tools | `export/` | New TS tools | 3 days |
| P2-3 | Port Redis queue system | `queue/redis-queue.ts` | New module | 3 days |
| P2-4 | Implement hybrid search (LanceDB + pgvector FTS) | N/A — new feature | Py server | 3 days |
| P2-5 | Populate Neo4j with entity data | N/A — new feature | Py server | 2 days |
| P2-6 | Port document hierarchy builder | `loaders/document-hierarchy.ts` | TS server | 2 days |

## P3: Future / Nice to Have

| # | Task | Notes |
|---|------|-------|
| P3-1 | Port BERT Sentiment | Needs ONNX runtime |
| P3-2 | Port browser search (Tavily) | External API dependency |
| P3-3 | Port LangGraph workflows | Complex, evaluate if needed |
| P3-4 | Port LlamaIndex RAG | Evaluate against native LanceDB |
| P3-5 | Activate Directus | In docker-compose, needs config |
| P3-6 | Implement graph traversal search | Neo4j already configured |
