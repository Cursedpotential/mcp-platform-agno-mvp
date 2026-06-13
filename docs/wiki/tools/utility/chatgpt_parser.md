# ChatGPT Parser - Skill Reference

## Overview
- **What**: Parses ChatGPT JSON export files and extracts structured conversations, entities, and code artifacts
- **Version**: 1.0.0 (Sprint 1)
- **Category**: parser | nlp | evidence-processing
- **Installed In**: `utilities/scripts/chatgpt_parser.py`
- **Status**: Active (core evidence ingestion tool)

## Purpose

The ChatGPT Parser is a forensic evidence extraction tool designed to:
1. **Ingest** ChatGPT JSON exports (from Settings > Data Export)
2. **Normalize** conversation turns into a standardized schema
3. **Extract** named entities using spaCy NER
4. **Identify** code artifacts (blocks, files, snippets)
5. **Hash** all content for chain-of-custody tracking
6. **Output** JSONL for downstream processing (Neo4j, LanceDB, PostgreSQL)

## How It Works

### Input Format
Accepts ChatGPT's native JSON export format with conversations array containing message mappings.

### Processing Pipeline

1. **Schema Detection** (pre_scan_schema())
   - Validates JSON structure
   - Detects conversation format variants
   - Checks for required fields

2. **Conversation Normalization**
   - Flattens nested message structure
   - Extracts turn metadata (timestamp, author, role)
   - Generates SHA-256 hash of each message for deduplication

3. **Entity Extraction** (spaCy NER)
   - Identifies PERSON, ORG, GPE, DATE, etc.
   - Tracks entity aliases and mention counts
   - Records first mention context
   - Assigns confidence scores

4. **Artifact Detection**
   - Identifies code blocks (markdown fences)
   - Extracts language, content, context
   - Hashes artifact content
   - Links to source message

5. **Output Generation**
   - Writes JSONL (one record per line)
   - Separate files for conversations, entities, artifacts
   - Includes statistics and error logs

### Data Structures

**ConversationTurn** (normalized message):
```json
{
  "message_hash": "sha256_hex",
  "conversation_id": "uuid",
  "platform": "chatgpt",
  "timestamp": "ISO8601",
  "turn_type": "user|assistant",
  "content": "message text",
  "raw_metadata": {}
}
```

**Entity** (extracted):
```json
{
  "entity_id": "uuid",
  "type": "PERSON|ORG|GPE|...",
  "name": "entity name",
  "aliases": ["alt1", "alt2"],
  "confidence": 0.95,
  "first_mention": {"message_hash": "...", "context": "..."},
  "mention_count": 5,
  "extraction_method": "spacy_ner"
}
```

**Artifact** (code block):
```json
{
  "artifact_id": "uuid",
  "type": "code|file|snippet",
  "language": "python|javascript|...",
  "content": "code text",
  "content_hash": "sha256_hex",
  "context": "surrounding text",
  "source_message": "message_hash",
  "timestamp": "ISO8601",
  "metadata": {}
}
```

## When to Use It

### Primary Use Cases
- **Evidence Ingestion**: First step in processing ChatGPT exports for legal/forensic analysis
- **Entity Mapping**: Extract all people, organizations, dates mentioned in conversations
- **Code Artifact Preservation**: Capture code snippets with full context and timestamps
- **Deduplication**: Hash-based identification of duplicate messages across exports
- **Chain of Custody**: Create immutable records with SHA-256 hashing

### Workflow Integration
```
ChatGPT Export (JSON)
    |
[chatgpt_parser.py] <- YOU ARE HERE
    |
Normalized JSONL (conversations, entities, artifacts)
    |
[conversation_splitter.py] (if large)
    |
[output_schemas.py] (validation)
    |
Neo4j (semantica_build_graph)
    |
PostgreSQL (postgres_write_record)
```

## Dependencies

### Required
- **Python 3.8+**
- **spacy** - NLP entity extraction
  ```bash
  pip install spacy
  python -m spacy download en_core_web_sm
  ```
- **pathlib** (stdlib)
- **json** (stdlib)
- **hashlib** (stdlib)
- **uuid** (stdlib)
- **dataclasses** (stdlib, Python 3.7+)

### Optional
- **pandas** - For large-scale statistics
- **tqdm** - Progress bars

## Usage Examples

### Basic Usage
```bash
# Parse a single export
python chatgpt_parser.py export.json

# Parse with custom output directory
python chatgpt_parser.py export.json ./output_dir
```

### In a Workflow
```bash
# Full pipeline
python chatgpt_parser.py huge_export.json ./parsed
python output_schemas.py ./parsed/conversations.jsonl conversation
python conversation_splitter.py ./parsed/conversations.jsonl --conversations-per-chunk 100
```

### From Python
```python
from pathlib import Path
from chatgpt_parser import ChatGPTParser

parser = ChatGPTParser(
    export_path=Path("export.json"),
    output_dir=Path("./output")
)
parser.run()

# Access statistics
print(parser.stats)
```

## Workflow Integration

### Evidence Processing Pipeline
1. **Ingestion** (chatgpt_parser.py)
   - Parse ChatGPT export
   - Extract entities and artifacts
   - Generate hashes for chain of custody

2. **Validation** (output_schemas.py)
   - Verify JSONL structure
   - Check required fields
   - Report validation errors

3. **Splitting** (conversation_splitter.py)
   - Split large files if needed
   - Prepare for downstream processing

4. **Enrichment** (Neo4j + Semantica)
   - Build knowledge graph
   - Link entities across conversations
   - Add temporal relationships

5. **Storage** (PostgreSQL)
   - Write normalized records
   - Maintain audit trail
   - Enable full-text search

## LLM Tool Interface

### MCP Tool Call (DIAL)
```json
{
  "tool": "parse_chatgpt_export",
  "arguments": {
    "export_path": "/path/to/export.json",
    "output_dir": "/path/to/output",
    "extract_entities": true,
    "extract_artifacts": true
  }
}
```

### Expected Output
```json
{
  "status": "success",
  "conversations_processed": 42,
  "messages_processed": 1250,
  "entities_extracted": 89,
  "artifacts_extracted": 23,
  "output_files": {
    "conversations": "/path/to/output/conversations.jsonl",
    "entities": "/path/to/output/entities.jsonl",
    "artifacts": "/path/to/output/artifacts.jsonl"
  },
  "errors": []
}
```

## Online Repo & Docs

- **GitHub**: https://github.com/Cursedpotential/mcp-tool-platform/tree/main/utilities/scripts
- **spaCy Docs**: https://spacy.io/usage/linguistic-features#named-entities
- **ChatGPT Export Format**: https://help.openai.com/en/articles/7260999-how-do-i-export-my-chatgpt-history

## How to Update

### Adding New Entity Types
1. Modify spaCy model or add custom NER pipeline
2. Update Entity dataclass with new fields
3. Add extraction logic in _extract_entities()
4. Update output_schemas.py validation

### Improving Artifact Detection
1. Enhance regex patterns in _find_artifacts()
2. Add language detection (Pygments)
3. Support more code block formats
4. Test with test_artifacts.json

### Performance Optimization
1. **Lazy load spaCy**: Only initialize on first use
2. **Batch processing**: Process multiple exports in parallel
3. **Streaming**: Use generators for large files
4. **Caching**: Hash-based deduplication across runs

## Common Pitfalls

| Pitfall | Solution |
|---------|----------|
| spaCy model not installed | Run `python -m spacy download en_core_web_sm` |
| Unicode encoding errors on Windows | Script auto-fixes with codecs.getwriter('utf-8') |
| Out of memory on huge exports | Use conversation_splitter.py first, then parse chunks |
| Missing entities | Increase spaCy confidence threshold or use custom NER |
| Duplicate messages | Check SHA-256 hashes in output; use find_duplicates.py |

---

**Last Updated**: 2026-03-15
**Status**: Production-ready
