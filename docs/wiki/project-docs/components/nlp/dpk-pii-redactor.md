# DPK PII Redactor — Skill Reference

## Overview
- **What**: Personally Identifiable Information detection and redaction using Microsoft Presidio + spaCy NER
- **Version**: presidio-analyzer v2.2.355+, spaCy en_core_web_sm
- **Category**: nlp
- **Installed In**: Py MCP Server (port 8082)

## Configuration
- **Engine**: Microsoft Presidio Analyzer with spaCy NLP backend
- **Default entities**: PERSON, EMAIL_ADDRESS, PHONE_NUMBER, CREDIT_CARD, LOCATION, DATE_TIME
- **Threshold**: 0.6 minimum confidence (configurable)
- **Operators**: "replace" (with placeholder like `<PERSON>`) or "redact" (with `[REDACTED]`)

## API Patterns
```python
# Basic usage
dpk_pii_redact(text="John Smith called from 555-1234")

# With custom entities
dpk_pii_redact(
    text="...",
    entities='["PERSON", "EMAIL_ADDRESS"]',  # JSON array string
    operator="replace",
    score_threshold=0.7
)

# Response format
{
  "redacted_text": "<PERSON> called from <PHONE_NUMBER>",
  "detected_pii": [
    {"type": "PERSON", "text": "John Smith", "start": 0, "end": 10, "confidence": 0.95},
    {"type": "PHONE_NUMBER", "text": "555-1234", "start": 23, "end": 31, "confidence": 0.99}
  ],
  "pii_entity_types": ["PERSON", "PHONE_NUMBER"],
  "pii_count": 2
}
```

## Integration Points
- **Input**: Raw text from evidence.messages.body
- **Output**: Stored in evidence.message_analysis.pii_detected, pii_redacted_text
- **Workflow**: Runs in `full_analysis` and `pii_check` workflows
- **Downstream**: Redacted text passed to behavioral analysis (protects PII in analysis)

## Common Pitfalls
- Presidio requires spaCy model — `python -m spacy download en_core_web_sm` in Dockerfile
- Entity positions are character offsets in original text
- Lower threshold = more PII detected but more false positives

## References
- Microsoft Presidio: https://github.com/microsoft/presidio
- Local reference: `py-mcp-server/src/tools/dpk_tools.py`
