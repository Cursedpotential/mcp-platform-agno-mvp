# Pandoc Document Converter — Skill Reference

## Overview
- **What**: Universal document format converter (Markdown, HTML, DOCX, LaTeX, etc.)
- **Status**: 🔴 Pending Integration
- **Target Server**: JS MCP
- **Category**: document-processing
- **MCP Tool**: Not yet implemented

## What It Does
- Converts between 30+ document formats
- Preserves document structure during conversion
- Handles styling and metadata preservation
- Supports custom filters and templates
- Enables format-agnostic document pipelines

## Format Support
- Input: DOCX, ODT, RTF, LaTeX, Markdown, HTML, PDF (text)
- Output: Markdown, HTML, DOCX, PDF, LaTeX, Reveal.js slides
- Special: Pandoc filters for custom transformations

## Integration Points
- Input: Any document format supported by Pandoc
- Output: Target format (typically Markdown for analysis pipeline)
- Used by: Format conversion, normalization, document ingestion
- Related: Docling (structured extraction), MinerU (PDF focus)

## Implementation Tasks
- [ ] Create JS MCP wrapper for Pandoc CLI
- [ ] Implement format auto-detection and routing
- [ ] Handle large file streaming
- [ ] Add custom filter support (if needed)
- [ ] Test with mixed content (embedded images, etc.)

## Configuration Needed
- Pandoc binary location
- Default target format (typically Markdown)
- Custom filter paths (optional)

## Testing Checklist
- [ ] Format conversion accuracy (all major formats)
- [ ] Metadata preservation
- [ ] Large document handling
- [ ] Embedded media references
