# Skill: Privacy Handling

## Purpose
Handle sensitive personal content appropriately throughout the
processing pipeline.

## Principles
1. **Raw transcripts stay local** — never upload full conversation files
2. **Only structured chunks go to cloud** — and only when necessary
3. **No PII stripping** — per your preference, raw content is preserved
4. **Access control** — all extracted data is stored in YOUR database
5. **Chain of custody** — SHA-256 hashes track every file and message

## What's Local vs Cloud

### LOCAL (your machine only)
- Raw transcript files (never leave your machine)
- Parsed messages (standardized format, still local)
- Topic segmentation (runs on your 2GB GPU)
- Artifact extraction (regex-based, local)
- PostgreSQL database (local Docker container)

### CLOUD (sent to API)
- Semantic analysis of `personal_legal` segments
- Entity extraction from text
- Timeline event identification
- Emotional context analysis

### What Gets Sent
Only the **content of individual messages** within a topic segment:
```
Input to cloud: "I stayed at the Hilton Garden Inn on April 15th. 
                 Katrina had been controlling my phone access for weeks."
NOT sent: Full conversation, filenames, metadata
```

## Security Measures
- API keys stored in `.env` (never committed)
- Database password in `.env` (never committed)
- No logs of personal content sent to external systems
- SHA-256 hashes verify file integrity at every step

## Data Retention
- Raw transcripts: Keep indefinitely (evidence)
- Parsed messages: Keep indefinitely (evidence)
- Cloud API calls: Not stored by us (check provider's retention policy)
- Database backups: Encrypted, local only

## Compliance Notes
For court admissibility:
- Every file has SHA-256 hash at first touch
- Every processing step is logged with timestamp
- Chain of custody is maintained automatically
- Raw files are never modified (read-only processing)
