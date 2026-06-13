# Find Duplicates - Skill Reference

## Overview
- **What**: Hash-based duplicate file finder using SHA-256
- **Version**: 1.0.0
- **Category**: utility | deduplication | forensic
- **Installed In**: `utilities/scripts/find_duplicates.py`
- **Status**: Active (chain of custody verification)

## Purpose

Find Duplicates enables forensic deduplication:
1. **Hash files** using SHA-256
2. **Identify duplicates** across directory trees
3. **Report groups** of identical files
4. **Verify integrity** - same hash = same content
5. **Support chain of custody** - prove no data loss

## How It Works

### Processing Pipeline

1. **Traverse directory**
   - Recursively walks all subdirectories
   - Processes all files

2. **Hash each file**
   - Reads file in binary mode
   - Computes SHA-256 hash
   - Stores hash -> file mapping

3. **Identify duplicates**
   - Finds hashes with multiple files
   - Groups by hash
   - Reports duplicate groups

## When to Use It

### Primary Use Cases
- **Deduplication**: Find and remove duplicate evidence files
- **Integrity verification**: Confirm no data loss during transfers
- **Chain of custody**: Prove files are identical across copies
- **Storage optimization**: Identify space-saving opportunities
- **Forensic analysis**: Detect copied or modified files

## Dependencies

### Required
- **Python 3.6+**
- **hashlib** (stdlib)
- **pathlib** (stdlib)
- **collections** (stdlib)

## Usage Examples

### Basic Usage
```bash
python find_duplicates.py ./evidence
python find_duplicates.py .
```

## Online Repo & Docs

- **GitHub**: https://github.com/Cursedpotential/mcp-tool-platform/tree/main/utilities/scripts
- **SHA-256**: https://en.wikipedia.org/wiki/SHA-2

---

**Last Updated**: 2026-03-15
**Status**: Production-ready
