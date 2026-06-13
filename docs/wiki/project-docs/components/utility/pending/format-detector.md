# Format Detector — Skill Reference

## Overview
- **What**: Confidence-scored automatic file format detection before routing to parsers
- **Status**: 🔴 Pending Implementation
- **Target Server**: TS MCP
- **Category**: pending
- **MCP Tool**: Not yet implemented

## Legacy Reference
- **Source**: `MCP_Tool_Platform/ingest/format-detection.ts` (READ-ONLY)
- **Key patterns**: File signature analysis, MIME type detection, confidence scoring

## What It Does
- Detects file format from file extension, MIME type, and content analysis
- Returns confidence score for each detected format
- Routes files to appropriate parsers based on format
- Handles ambiguous files (e.g., plain text that could be multiple formats)
- Prevents sending files to wrong parsers

## Detection Methods
1. **File extension** (quick, unreliable)
2. **MIME type** (header-based, more reliable)
3. **Content analysis** (magic bytes, format signatures)
4. **Heuristics** (sample content parsing)

## Integration Points
- Input: Raw files, unknown format
- Output: Detected format, confidence score, recommended parser
- Used by: Ingestion pipeline, parser routing
- Related: All parsers (SMS, Facebook, iMessage, etc.)

## Implementation Tasks
- [ ] Create TS MCP tool `detect_format`
- [ ] Implement content-based detection (magic bytes)
- [ ] Add confidence scoring algorithm
- [ ] Support all parser input formats
- [ ] Fallback handling for ambiguous formats
- [ ] Test with mislabeled and unusual files

## Parser Format Mapping
- XML → SMS parser
- HTML → Facebook parser
- PDF → iMessage parser
- TXT → WhatsApp/generic parser
- JSON → ChatGPT/Timeline parser
- CSV/other → Chunker

## Testing Checklist
- [ ] Correct format detection (all types)
- [ ] Confidence scoring accuracy
- [ ] Ambiguous file handling
- [ ] Performance on binary content
