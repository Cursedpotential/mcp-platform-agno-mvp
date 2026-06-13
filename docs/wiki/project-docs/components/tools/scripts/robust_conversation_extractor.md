# Robust Conversation Extractor - Skill Reference

## Overview
- **What**: Extracts conversations from broken/malformed JSON using fuzzy pattern matching
- **Version**: 1.0.0
- **Category**: parser | recovery | nlp
- **Installed In**: `utilities/scripts/robust_conversation_extractor.py`
- **Status**: Active (corrupted data recovery)

## Purpose

Robust Conversation Extractor handles corrupted JSON:
1. **Extract conversations** from broken JSON
2. **Use pattern matching** instead of JSON parsing
3. **Recover data** from partially corrupted files
4. **Generate markdown** output for review
5. **Handle edge cases** - missing fields, encoding issues

## How It Works

### Processing Pipeline

1. **Read raw text**
   - Ignores JSON structure
   - Treats as plain text
   - Handles encoding errors

2. **Find conversations**
   - Uses regex patterns
   - Looks for context_uuid markers
   - Splits on boundaries

3. **Extract fields**
   - Pattern matches for title, created, updated
   - Extracts entries (role + content)
   - Cleans JSON escaping

4. **Format markdown**
   - Creates readable markdown
   - Adds timestamps
   - Separates user/assistant

5. **Write output**
   - Saves as markdown files
   - One file per chunk
   - Preserves conversation count

## When to Use It

### Primary Use Cases
- **Corrupted exports**: Recover from broken JSON
- **Partial failures**: Extract what's recoverable
- **Legacy formats**: Handle non-standard JSON
- **Emergency recovery**: Last resort data extraction
- **Preview**: Quick markdown preview of conversations

## Dependencies

### Required
- **Python 3.6+**
- **re** (stdlib)
- **pathlib** (stdlib)
- **argparse** (stdlib)

## Usage Examples

### Basic Usage
```bash
python robust_conversation_extractor.py ./chunks
python robust_conversation_extractor.py ./chunks --output-prefix "perplexity"
```

## Online Repo & Docs

- **GitHub**: https://github.com/Cursedpotential/mcp-tool-platform/tree/main/utilities/scripts

---

**Last Updated**: 2026-03-15
**Status**: Production-ready
