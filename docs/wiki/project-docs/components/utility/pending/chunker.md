# Smart Text Chunker — Skill Reference

## Overview
- **What**: Multi-format text parser with intelligent chunking for LLM context windows
- **Status**: 🔴 Pending Integration
- **Target Server**: TS MCP
- **Category**: pending
- **MCP Tool**: Not yet implemented

## Legacy Reference
- **Source**: `MCP_Tool_Platform/Evidence_Analysis/apps/utilities/Chunker/` (READ-ONLY)
- **Key patterns**: Format-specific parsing, semantic chunking, metadata preservation

## What It Does
- Parses multiple formats: CSV, HTML, Markdown, TSV, plain text
- Chunks text respecting format boundaries (paragraphs, table rows, etc.)
- Calculates token counts for LLM context window optimization
- Preserves semantic meaning across chunks
- Generates chunk metadata (format type, position, token count)

## Supported Formats
- **CSV**: Row-aware chunking, header preservation
- **HTML**: Tag-aware parsing, link/metadata extraction
- **Markdown**: Section-aware chunking, heading hierarchy
- **TSV**: Column-aware chunking
- **Plain text**: Paragraph and sentence-aware chunking

## Integration Points
- Input: Documents in any supported format
- Output: Array of chunks with metadata (tokens, format, position)
- Used by: LLM context preparation, document preprocessing
- Related: Document processors (for initial extraction), format detector

## Implementation Tasks
- [ ] Port utility app logic to TS MCP tool
- [ ] Implement token counting (via tiktoken or similar)
- [ ] Add format-specific boundary detection
- [ ] Support configurable chunk size (by tokens or characters)
- [ ] Preserve format information in chunk metadata
- [ ] Test with large documents and various formats

## Configuration Options
- Target chunk size (default: 2000 tokens)
- Token counter type (GPT-3.5, GPT-4, etc.)
- Overlap between chunks (default: 200 tokens)
- Format-specific settings per type

## Testing Checklist
- [ ] Token counting accuracy
- [ ] Boundary respecting across formats
- [ ] Metadata preservation
- [ ] Large document handling
