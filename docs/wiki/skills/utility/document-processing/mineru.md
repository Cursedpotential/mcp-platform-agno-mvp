# MinerU Document Extraction — Skill Reference

## Overview
- **What**: High-quality PDF and document text extraction with layout understanding
- **Status**: 🔴 Pending Evaluation
- **Target Server**: TS MCP or Python MCP
- **Category**: document-processing
- **MCP Tool**: Not yet implemented

## What It Does
- Extracts text from PDFs with high accuracy
- Preserves document structure and reading order
- Handles complex layouts (tables, multi-column, figures)
- Optimized for academic and technical documents
- Outputs structured text with metadata

## Key Strengths
- Better handling of dense technical PDFs vs standard tools
- Accurate table extraction and formatting
- Maintains spatial relationships and hierarchy
- Works well with both scanned and digital PDFs

## Integration Points
- Input: PDF files (primary), other document formats (secondary)
- Output: Structured text with layout information
- Used by: Document ingestion pipeline, evidence processing
- Related: Docling (similar goals), Pandoc (format conversion)

## Implementation Tasks
- [ ] Evaluate MinerU performance vs Docling/Pandoc
- [ ] Determine deployment approach (TS wrapper vs Python service)
- [ ] Test on dial-stack document types
- [ ] Benchmark extraction quality metrics
- [ ] Plan integration with existing parsers

## Decision Points
- Choose between TS wrapper or Python MCP implementation
- Evaluate cost/complexity vs benefit vs existing tools
- Determine when to use MinerU vs Docling vs Pandoc

## Testing Checklist
- [ ] PDF text extraction accuracy
- [ ] Table detection and formatting
- [ ] Complex layout handling
- [ ] Performance on large documents
