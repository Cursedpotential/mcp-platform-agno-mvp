# Utility Tools Wiki — Documentation Complete

**Created**: 2026-03-15  
**Status**: Production-ready  
**Total Tools**: 10  
**Documentation Files**: 11  

## What Was Created

Complete wiki documentation for 10 high-value utility scripts used in the AI DIAL evidence processing pipeline.

### Files Created

```
docs/wiki/tools/utility/
├── INDEX.md                              (Master index, quick reference)
├── chatgpt_parser.md                     (Parse ChatGPT exports)
├── conversation_splitter.md              (Split large files)
├── conversation_to_docx.md               (Convert to Word)
├── find_duplicates.md                    (Deduplication)
├── forensic_diff.md                      (File comparison)
├── pandoc_converter.md                   (Format conversion)
├── output_schemas.md                     (JSONL validation)
├── chunk_file_tool.md                    (File chunking)
├── robust_conversation_extractor.md      (Corrupted data recovery)
├── analyze_triggers.md                   (Skill quality)
└── README.md                             (This file)
```

## Documentation Quality

Each tool entry includes:

1. **Overview** — What it is, version, category, status
2. **Purpose** — 5-point summary of functionality
3. **How It Works** — Processing pipeline, data structures, examples
4. **When to Use It** — Primary use cases, workflow integration
5. **Dependencies** — Required and optional packages
6. **Usage Examples** — CLI, workflow, and Python API examples
7. **Workflow Integration** — Full pipeline diagrams
8. **LLM Tool Interface** — MCP tool call format and expected output
9. **Online Repo & Docs** — GitHub and external links
10. **How to Update** — Enhancement and optimization guidelines
11. **Common Pitfalls** — Known issues and solutions

## Quick Start

### Find a Tool
- **By name**: See [INDEX.md](./INDEX.md) quick reference table
- **By category**: See [INDEX.md](./INDEX.md) "By Category" section
- **By workflow**: See [INDEX.md](./INDEX.md) "Workflow Integration" section

### Learn How to Use It
1. Open the tool's markdown file
2. Read "When to Use It" section
3. Check "Usage Examples" for your scenario
4. Review "Dependencies" and install if needed
5. Run the command

### Integrate with Your Workflow
1. Check "Workflow Integration" section
2. See how it connects to other tools
3. Review "LLM Tool Interface" for MCP integration
4. Test with sample data

## Tools at a Glance

| Tool | Purpose | Key Feature |
|------|---------|------------|
| **chatgpt_parser** | Parse ChatGPT exports | spaCy NER + SHA-256 hashing |
| **conversation_splitter** | Split large files | Preserves JSON structure |
| **conversation_to_docx** | Convert to Word | Formatted for legal review |
| **find_duplicates** | Find duplicates | SHA-256 hash-based |
| **forensic_diff** | Compare files | JSON/YAML/text support |
| **pandoc_converter** | Format conversion | Batch processing |
| **output_schemas** | Validate JSONL | Quality gates |
| **chunk_file_tool** | Split by size | Parallel processing |
| **robust_conversation_extractor** | Recover from broken JSON | Pattern matching |
| **analyze_triggers** | Skill quality | Anti-pattern detection |

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

See: [chatgpt_parser](./chatgpt_parser.md), [output_schemas](./output_schemas.md), [conversation_to_docx](./conversation_to_docx.md), [pandoc_converter](./pandoc_converter.md)

### Find and Remove Duplicates
```bash
# 1. Scan
python find_duplicates.py ./evidence

# 2. Review output, identify which to keep

# 3. Delete duplicates manually

# 4. Verify
python find_duplicates.py ./evidence
```

See: [find_duplicates](./find_duplicates.md)

### Compare Two Versions
```bash
# Compare original vs processed
python forensic_diff.py original.json processed.json

# Review diff output
cat diff_report.json | jq '.diff'
```

See: [forensic_diff](./forensic_diff.md)

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

See: [conversation_splitter](./conversation_splitter.md), [chatgpt_parser](./chatgpt_parser.md), [output_schemas](./output_schemas.md)

### Recover from Corrupted JSON
```bash
# Extract via pattern matching
python robust_conversation_extractor.py ./chunks

# Review markdown output
cat chunks_markdown/*.md

# Manual correction if needed

# Re-parse corrected data
python chatgpt_parser.py corrected.json ./parsed
```

See: [robust_conversation_extractor](./robust_conversation_extractor.md), [chatgpt_parser](./chatgpt_parser.md)

## Installation

### Python Dependencies
```bash
# Core
pip install spacy pyyaml python-docx

# Optional (enhanced features)
pip install deepdiff pandas tqdm

# Download spaCy model
python -m spacy download en_core_web_sm
```

### System Dependencies
```bash
# Windows
choco install pandoc wkhtmltopdf

# macOS
brew install pandoc wkhtmltopdf

# Linux
apt-get install pandoc wkhtmltopdf
```

## Integration with AI DIAL

These tools integrate with:
- **AI DIAL Core** — MCP tool calls
- **Neo4j** — Semantica graph building
- **PostgreSQL** — Evidence storage
- **LanceDB** — Vector embeddings
- **React + CopilotKit** — HITL review
- **WunderGraph Cosmo** — GraphQL federation

See each tool's "LLM Tool Interface" section for MCP integration details.

## Performance Notes

| Tool | Speed | Notes |
|------|-------|-------|
| chatgpt_parser | ~100 conv/sec | With spaCy NER |
| conversation_splitter | ~1000 conv/sec | Fast JSON parsing |
| find_duplicates | ~50 MB/sec | SHA-256 hashing |
| forensic_diff | ~10 MB/sec | Text diff |
| pandoc_converter | ~1 page/sec | Depends on PDF engine |

## Troubleshooting

### Out of Memory
- Use `conversation_splitter` to chunk files first
- Process chunks independently
- Merge results afterward

### Slow Performance
- Reduce spaCy NER confidence threshold
- Use parallel processing for multiple files
- Cache hashes for duplicate detection

### Encoding Issues
- Scripts auto-fix UTF-8 on Windows
- Check file encoding before processing
- Use `--encoding utf-8` flag if available

### Missing Dependencies
- Run `pip install -r requirements.txt`
- Install system tools (pandoc, wkhtmltopdf)
- Download spaCy models

See each tool's "Common Pitfalls" section for detailed troubleshooting.

## Contributing

To add a new utility tool:

1. Create script in `utilities/scripts/`
2. Follow naming convention: `tool_name.py`
3. Add docstring with usage
4. Create wiki entry in `docs/wiki/tools/utility/`
5. Update [INDEX.md](./INDEX.md)
6. Add to `docs/TOOL_CATALOG.md`
7. Create MCP tool wrapper if needed

## References

- **GitHub**: https://github.com/Cursedpotential/mcp-tool-platform/tree/main/utilities/scripts
- **Parent Index**: [Tools Index](../INDEX.md)
- **Tool Catalog**: [TOOL_CATALOG.md](../../TOOL_CATALOG.md)
- **Architecture**: [ARCHITECTURE.md](../../ARCHITECTURE.md)

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-03-15 | Initial documentation: 10 tools, 11 wiki files |

---

**Last Updated**: 2026-03-15  
**Status**: Production-ready  
**Maintainer**: Documentation Team  
**License**: Same as parent project
