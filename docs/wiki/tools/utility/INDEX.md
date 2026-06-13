# Utility Tools — Complete Wiki Index

High-value utility scripts for evidence processing, document conversion, and data quality assurance.

## Quick Reference

| Tool | Purpose | Status |
|------|---------|--------|
| [chatgpt_parser](./chatgpt_parser.md) | Parse ChatGPT JSON exports, extract entities and artifacts | Production |
| [conversation_splitter](./conversation_splitter.md) | Split large conversation files by count | Production |
| [conversation_to_docx](./conversation_to_docx.md) | Convert JSONL conversations to formatted Word documents | Production |
| [find_duplicates](./find_duplicates.md) | Hash-based duplicate file finder (SHA-256) | Production |
| [forensic_diff](./forensic_diff.md) | Deep structural and textual diff for JSON/YAML/text | Production |
| [pandoc_converter](./pandoc_converter.md) | Universal document converter (MD, DOCX, HTML to PDF) | Production |
| [output_schemas](./output_schemas.md) | Validate parser output JSONL against schemas | Production |
| [chunk_file_tool](./chunk_file_tool.md) | Split large files into fixed-size chunks | Production |
| [robust_conversation_extractor](./robust_conversation_extractor.md) | Extract conversations from broken/malformed JSON | Production |
| [analyze_triggers](./analyze_triggers.md) | Scan Claude skill triggers for anti-patterns | Production |

## By Category

### Parsers & Extraction
- [chatgpt_parser](./chatgpt_parser.md) — Parse ChatGPT exports with NER
- [robust_conversation_extractor](./robust_conversation_extractor.md) — Recover from corrupted JSON

### Document Conversion
- [conversation_to_docx](./conversation_to_docx.md) — JSONL to Word
- [pandoc_converter](./pandoc_converter.md) — Universal format conversion
- [chunk_file_tool](./chunk_file_tool.md) — Split large files

### Data Processing
- [conversation_splitter](./conversation_splitter.md) — Split by conversation count
- [find_duplicates](./find_duplicates.md) — Deduplication via SHA-256
- [forensic_diff](./forensic_diff.md) — Detailed file comparison

### Quality Assurance
- [output_schemas](./output_schemas.md) — JSONL validation
- [analyze_triggers](./analyze_triggers.md) — Skill quality monitoring

## Workflow Integration

### Full Evidence Processing Pipeline
```
ChatGPT Export (JSON)
    |
[chatgpt_parser] - Extract conversations, entities, artifacts
    |
[conversation_splitter] - Split if large (optional)
    |
[output_schemas] - Validate JSONL structure
    |
[forensic_diff] - Compare original vs parsed (optional)
    |
Neo4j + PostgreSQL - Store normalized data
    |
[conversation_to_docx] - Generate reports for review
    |
[pandoc_converter] - Convert to PDF for distribution
```

### Deduplication & Integrity
```
Raw Evidence Directory
    |
[find_duplicates] - Identify duplicate files
    |
Manual Review - Decide which to keep
    |
Delete Duplicates - Remove redundant copies
    |
[find_duplicates] - Verify no duplicates remain
```

### Large File Handling
```
Huge Export File
    |
[chunk_file_tool] - Split into manageable chunks
    |
[chatgpt_parser] - Process each chunk independently
    |
Merge JSONL - Combine results
```

### Corrupted Data Recovery
```
Broken/Malformed JSON
    |
[robust_conversation_extractor] - Extract via pattern matching
    |
Markdown Preview - Review recovered data
    |
Manual Correction - Fix issues
    |
[chatgpt_parser] - Re-parse corrected data
```

## Installation

All tools are in `utilities/scripts/`. Install dependencies:

```bash
# Core dependencies
pip install spacy pyyaml python-docx

# Optional (for enhanced features)
pip install deepdiff pandas tqdm

# Download spaCy model
python -m spacy download en_core_web_sm

# Install pandoc (system-level)
# Windows: choco install pandoc
# macOS: brew install pandoc
# Linux: apt-get install pandoc
```

## Common Workflows

### Process a ChatGPT Export
```bash
# 1. Parse
python chatgpt_parser.py export.json ./parsed

# 2. Validate
python output_schemas.py ./parsed/conversations.jsonl conversation

# 3. Convert to Word
python conversation_to_docx.py ./parsed/conversations.jsonl

# 4. Convert to PDF
python pandoc_converter.py ./parsed --format pdf
```

### Find and Remove Duplicates
```bash
# 1. Scan
python find_duplicates.py ./evidence

# 2. Review output, identify which to keep

# 3. Delete duplicates manually

# 4. Verify
python find_duplicates.py ./evidence
```

### Compare Two Versions
```bash
# Compare original vs processed
python forensic_diff.py original.json processed.json

# Review diff output
cat diff_report.json | jq '.diff'
```

### Handle Large Exports
```bash
# 1. Split
python conversation_splitter.py huge_export.json --conversations-per-chunk 100

# 2. Process chunks
for chunk in chunks/chunk_*.json; do
  python chatgpt_parser.py "$chunk" ./parsed
done

# 3. Validate
python output_schemas.py ./parsed/conversations.jsonl conversation
```

## Dependencies Summary

| Tool | Python | External | Optional |
|------|--------|----------|----------|
| chatgpt_parser | 3.8+ | spacy | pandas, tqdm |
| conversation_splitter | 3.6+ | - | - |
| conversation_to_docx | 3.6+ | python-docx | - |
| find_duplicates | 3.6+ | - | - |
| forensic_diff | 3.6+ | pyyaml | deepdiff |
| pandoc_converter | 3.6+ | pandoc | wkhtmltopdf |
| output_schemas | 3.6+ | - | - |
| chunk_file_tool | 3.6+ | - | - |
| robust_conversation_extractor | 3.6+ | - | - |
| analyze_triggers | 3.6+ | - | - |

## Performance Notes

- **chatgpt_parser**: ~100 conversations/sec with spaCy NER
- **conversation_splitter**: ~1000 conversations/sec
- **find_duplicates**: ~50 MB/sec hashing
- **forensic_diff**: ~10 MB/sec for text, instant for small JSON
- **pandoc_converter**: ~1 page/sec to PDF (depends on engine)

## Troubleshooting

### Out of Memory
- Use `conversation_splitter` to chunk large files first
- Process chunks independently
- Merge results afterward

### Slow Performance
- Reduce spaCy NER confidence threshold
- Use parallel processing for multiple files
- Cache hashes for duplicate detection

### Encoding Issues
- Scripts auto-fix UTF-8 on Windows
- Use `--encoding utf-8` flag if available
- Check file encoding before processing

### Missing Dependencies
- Run `pip install -r requirements.txt`
- Install system tools (pandoc, wkhtmltopdf)
- Download spaCy models: `python -m spacy download en_core_web_sm`

## Contributing

To add a new utility tool:
1. Create script in `utilities/scripts/`
2. Follow naming convention: `tool_name.py`
3. Add docstring with usage
4. Create wiki entry in `docs/wiki/tools/utility/`
5. Update this index
6. Add to `docs/TOOL_CATALOG.md`

## References

- **GitHub**: https://github.com/Cursedpotential/mcp-tool-platform/tree/main/utilities/scripts
- **Parent**: [Tools Index](../INDEX.md)
- **Related**: [MCP Servers](../INDEX.md#mcp-servers)

---

**Last Updated**: 2026-03-15
**Total Tools**: 10
**Status**: All production-ready
