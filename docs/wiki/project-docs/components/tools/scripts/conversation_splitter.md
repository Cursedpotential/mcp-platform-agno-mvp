# Conversation Splitter - Skill Reference

## Overview
- **What**: Splits large conversation JSON files by conversation count
- **Version**: 1.0.0
- **Category**: utility | data-processing
- **Installed In**: `utilities/scripts/conversation_splitter.py`
- **Status**: Active (essential for large exports)

## Purpose

Conversation Splitter handles the common problem of processing huge ChatGPT exports:
1. **Chunk large files** by conversation count (not file size)
2. **Preserve structure** - maintains JSON format in each chunk
3. **Enable parallel processing** - process chunks independently
4. **Reduce memory usage** - load smaller files into memory
5. **Prepare for downstream tools** - output ready for parsers and validators

## How It Works

### Input Format
Accepts either:
- **Array format**: `[{conversation1}, {conversation2}, ...]`
- **Object format**: `{"conversations": [{conversation1}, {conversation2}, ...]}`

### Processing Pipeline

1. **Load JSON**
   - Reads entire file into memory
   - Detects format (array vs object)
   - Validates structure

2. **Calculate chunks**
   - Divides conversations by count
   - Calculates total chunks needed
   - Determines start/end indices

3. **Write chunks**
   - Creates output directory
   - Writes each chunk as valid JSON
   - Preserves original structure

4. **Report progress**
   - Prints chunk count and conversation count
   - Shows output directory location

## When to Use It

### Primary Use Cases
- **Large exports**: ChatGPT exports with 1000+ conversations
- **Memory constraints**: Limited RAM available
- **Parallel processing**: Process chunks in parallel
- **Batch validation**: Validate each chunk independently
- **Incremental ingestion**: Ingest one chunk at a time

## Dependencies

### Required
- **Python 3.6+**
- **json** (stdlib)
- **pathlib** (stdlib)
- **argparse** (stdlib)

## Usage Examples

### Basic Usage
```bash
# Split with default 50 conversations per chunk
python conversation_splitter.py export.json

# Custom chunk size
python conversation_splitter.py export.json --conversations-per-chunk 100

# Custom output directory
python conversation_splitter.py export.json --output-dir ./chunks
```

## Online Repo & Docs

- **GitHub**: https://github.com/Cursedpotential/mcp-tool-platform/tree/main/utilities/scripts

---

**Last Updated**: 2026-03-15
**Status**: Production-ready
