# Output Schemas - Skill Reference

## Overview
- **What**: Validates parser output JSONL files against defined schemas
- **Version**: 1.0.0
- **Category**: validation | quality-assurance
- **Installed In**: `utilities/scripts/output_schemas.py`
- **Status**: Active (data quality validation)

## Purpose

Output Schemas enables quality assurance:
1. **Validate JSONL** against defined schemas
2. **Check required fields** - ensure completeness
3. **Report errors** - detailed validation errors
4. **Support pipelines** - gate-keep data quality
5. **Enable auditing** - prove data meets standards

## Supported Record Types

**conversation** - Normalized conversation turn
- Required: message_hash, conversation_id, platform, timestamp, turn_type, content

**entity** - Extracted named entity
- Required: entity_id, type, name, confidence, mention_count

**artifact** - Code block or file artifact
- Required: artifact_id, type, language, content, content_hash

## When to Use It

### Primary Use Cases
- **Quality gates**: Validate before downstream processing
- **Error detection**: Find malformed records early
- **Pipeline monitoring**: Ensure data quality
- **Compliance**: Prove data meets standards
- **Debugging**: Identify parser issues

## Dependencies

### Required
- **Python 3.6+**
- **json** (stdlib)
- **dataclasses** (stdlib)

## Usage Examples

### Basic Usage
```bash
python output_schemas.py conversations.jsonl conversation
python output_schemas.py entities.jsonl entity
python output_schemas.py artifacts.jsonl artifact
```

## Online Repo & Docs

- **GitHub**: https://github.com/Cursedpotential/mcp-tool-platform/tree/main/utilities/scripts

---

**Last Updated**: 2026-03-15
**Status**: Production-ready
