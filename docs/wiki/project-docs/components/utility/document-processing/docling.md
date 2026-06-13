# IBM Docling Document Processor — Skill Reference

## Overview
- **What**: Converts complex documents (PDFs, DOCXs, PPTs) to structured text with layout preservation
- **Status**: 🔴 Pending Integration
- **Target Server**: JS MCP
- **Category**: document-processing
- **MCP Tool**: Not yet implemented

## What It Does
- Extracts structured text from complex PDF layouts (multi-column, tables, headers)
- Preserves document hierarchy and reading order
- Detects and extracts tables, figures, and metadata
- Outputs to JSON, Markdown, or plain text formats
- Handles OCR for scanned documents (with fallback)

## Integration Points
- Input: PDF, DOCX, PPT, PNG, JPEG files
- Output: Structured JSON or Markdown with layout preservation
- Used by: Document ingestion pipeline, evidence processing
- Related: Pandoc (format conversion), MinerU (PDF extraction)

## Implementation Tasks
- [ ] Evaluate Docling library and dependencies
- [ ] Create JS MCP wrapper for Docling
- [ ] Implement chunking for large document output
- [ ] Add format detection (PDF vs DOCX handling differences)
- [ ] Test with complex multi-layout documents
- [ ] Benchmark performance against alternatives

## Configuration Needed
- OCR backend selection (Tesseract vs cloud)
- Output format preference (JSON vs Markdown)
- Table extraction granularity settings

## Testing Checklist
- [ ] Multi-column PDF parsing
- [ ] Table and figure detection
- [ ] Large document handling (>100 pages)
- [ ] Mixed PDF types (text + scanned)
