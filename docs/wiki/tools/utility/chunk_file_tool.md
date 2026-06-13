# Chunk File Tool - Skill Reference

## Overview
- **What**: Splits large files into fixed-size chunks
- **Version**: 1.0.0
- **Category**: utility | file-processing
- **Installed In**: `utilities/scripts/chunk_file_tool.py`
- **Status**: Active (large file handling)

## Purpose

Chunk File Tool enables large file processing:
1. **Split files** by size (MB)
2. **Reduce memory** - process chunks independently
3. **Enable parallel** - process chunks in parallel
4. **Preserve order** - maintain chunk sequence
5. **Support recovery** - resume from any chunk

## When to Use It

### Primary Use Cases
- **Large files**: Split files larger than available RAM
- **Parallel processing**: Process chunks independently
- **Network transfer**: Send smaller chunks
- **Incremental processing**: Process one chunk at a time
- **Backup**: Create manageable backup chunks

## Dependencies

### Required
- **Python 3.6+**
- **pathlib** (stdlib)

## Usage Examples

### Basic Usage
```bash
python chunk_file_tool.py large_file.json
python chunk_file_tool.py large_file.json 50
```

## Online Repo & Docs

- **GitHub**: https://github.com/Cursedpotential/mcp-tool-platform/tree/main/utilities/scripts

---

**Last Updated**: 2026-03-15
**Status**: Production-ready
