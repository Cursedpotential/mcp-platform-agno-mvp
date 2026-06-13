# Forensic Diff - Skill Reference

## Overview
- **What**: Deep structural and textual diff tool for JSON, YAML, and text files
- **Version**: 1.0.0
- **Category**: forensic | analysis | comparison
- **Installed In**: `utilities/scripts/forensic_diff.py`
- **Status**: Active (evidence comparison and validation)

## Purpose

Forensic Diff enables detailed evidence comparison:
1. **Compare files** - JSON, YAML, text, or mixed
2. **Detect changes** - structural and textual differences
3. **Measure similarity** - similarity scores for text
4. **Report deltas** - detailed change logs
5. **Support auditing** - prove what changed and when

## How It Works

### Input Format
Accepts any file type:
- **JSON** - structured data comparison
- **YAML** - configuration comparison
- **Text** - line-by-line diff
- **Mixed** - auto-detects format

### Processing Pipeline

1. **Load files**
   - Detects file format
   - Parses JSON/YAML or reads as text
   - Handles encoding errors gracefully

2. **Compare structured data** (JSON/YAML)
   - Uses DeepDiff if available
   - Falls back to custom recursive walk
   - Tracks added, removed, changed fields
   - Includes path to each change

3. **Compare text**
   - Uses difflib.SequenceMatcher
   - Calculates similarity score (0-1)
   - Counts added/removed lines
   - Generates unified diff preview

## When to Use It

### Primary Use Cases
- **Evidence validation**: Compare original vs processed versions
- **Configuration auditing**: Track changes to system configs
- **Report comparison**: Identify differences in analysis reports
- **Version control**: Audit what changed between versions
- **Integrity checking**: Verify files haven't been tampered with

## Dependencies

### Required
- **Python 3.6+**
- **json** (stdlib)
- **difflib** (stdlib)
- **yaml** - YAML parsing
  ```bash
  pip install pyyaml
  ```

### Optional
- **deepdiff** - Advanced structural comparison
  ```bash
  pip install deepdiff
  ```

## Usage Examples

### Basic Usage
```bash
python forensic_diff.py config_v1.json config_v2.json
python forensic_diff.py report_v1.txt report_v2.txt
python forensic_diff.py file1.json file2.json --format text
```

## Online Repo & Docs

- **GitHub**: https://github.com/Cursedpotential/mcp-tool-platform/tree/main/utilities/scripts
- **DeepDiff**: https://deepdiff.readthedocs.io/
- **difflib**: https://docs.python.org/3/library/difflib.html

---

**Last Updated**: 2026-03-15
**Status**: Production-ready
