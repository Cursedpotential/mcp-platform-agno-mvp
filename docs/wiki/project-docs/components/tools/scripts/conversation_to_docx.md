# Conversation to DOCX - Skill Reference

## Overview
- **What**: Converts JSONL conversation records to formatted Microsoft Word documents
- **Version**: 1.0.0
- **Category**: converter | document-generation
- **Installed In**: `utilities/scripts/conversation_to_docx.py`
- **Status**: Active (evidence report generation)

## Purpose

Conversation to DOCX enables forensic evidence presentation:
1. **Convert JSONL** to human-readable DOCX format
2. **Format conversations** with speaker labels and timestamps
3. **Generate reports** suitable for legal review
4. **Preserve metadata** in document properties
5. **Enable editing** - output is editable in Microsoft Word

## When to Use It

### Primary Use Cases
- **Evidence reports**: Generate formatted reports for legal review
- **HITL review**: Create documents for human-in-the-loop analysis
- **Stakeholder communication**: Share conversations with non-technical users
- **Archival**: Store conversations in standard document format
- **Editing**: Allow manual corrections and annotations

## Dependencies

### Required
- **Python 3.6+**
- **python-docx** - Word document generation
  ```bash
  pip install python-docx
  ```

## Usage Examples

### Basic Usage
```bash
python conversation_to_docx.py conversations.jsonl
python conversation_to_docx.py conversations.jsonl --output report.docx
```

## Online Repo & Docs

- **GitHub**: https://github.com/Cursedpotential/mcp-tool-platform/tree/main/utilities/scripts
- **python-docx**: https://python-docx.readthedocs.io/

---

**Last Updated**: 2026-03-15
**Status**: Production-ready
