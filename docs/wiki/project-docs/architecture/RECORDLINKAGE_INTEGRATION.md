---
title: RecordLinkage Integration - Deduplication & Entity Resolution
version: 1.0.0
created: 2026-03-04 23:30
modified: 2026-03-04 23:30
author: execution@opencode
project: traceiq-forensic
status: active
---

# RecordLinkage Integration

> **One library for deduplication AND document linking** - Why build custom when `recordlinkage` solves both?

## Why RecordLinkage

| Requirement | recordlinkage | Custom Code | dedupe |
|-------------|--------------|-------------|--------|
| **Exact duplicates** | ✅ `block('content_hash')` | Hash comparison | ❌ Fuzzy-focused |
| **Fuzzy matching** | ✅ Jaro-Winkler, Levenshtein | Manual regex | ✅ ML-based |
| **Across sources linking** | ✅ Link evidence from different devices/backups | Manual joins | ❌ Single entity |
| **Pandas native** | ✅ Works with existing workflow | N/A | ❌ Custom format |
| **Actively maintained** | ✅ v0.16 (July 2023) | N/A | ⚠️ v2.0 (Feb 2022) |
| **License** | ✅ BSD-3-Clause | N/A | Check license |

**Key capability**: Link evidence **ACROSS SOURCES** - your phone, their phone, different backups, different export formats.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ DUAL-LEVEL DEDUPLICATION ARCHITECTURE                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐   │
│  │  PHASE 1: INGESTION (TypeScript coordinator.ts)                       │   │
│  │                                                                       │   │
│  │  File-level dedup: SHA-256 hash comparison                            │   │
│  │  Message-level dedup: SHA-256 hash comparison                          │   │
│  │  - FAST: O(1) hash lookup                                            │   │
│  │  - EXACT: No false positives                                          │   │
│  │  - Device-aware: Same hash + different device = NEW evidence         │   │
│  └───────────────────────────────────────────────────────────────────────┘   │
│                              │                                              │
│                              ▼                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐   │
│  │  PHASE 2: SEMANTICA (Python semantica_pipeline.py)                    │   │
│  │                                                                       │   │
│  │  recordlinkage usage:                                                 │   │
│  │                                                                       │   │
│  │  1. DOCUMENT LINKING                                                  │   │
│  │     - Link related evidence files (backup.zip + export.xml)          │   │
│  │     - Cross-reference citations, attachments                          │   │
│  │                                                                       │   │
│  │  2. SENDER RESOLUTION                                                 │   │
│  │     - Match "Jake" vs "Jake from V&B" to same entity                 │   │
│  │     - Phone normalization: +1-555-123-4567 vs 555.123.4567            │   │
│  │     - Email normalization: case-insensitive                          │   │
│  │                                                                       │   │
│  │  3. CROSS-DEVICE CORRELATION                                          │   │
│  │     - Link conversations from different devices                      │   │
│  │     - Identify same person across devices                            │   │
│  │                                                                       │   │
│  │  4. TEMPORAL LINKING                                                  │   │
│  │     - Link events across time windows                                 │   │
│  │     - Behavioral pattern detection                                    │   │
│  └───────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Usage Examples

### 1. Exact Duplicate Detection (Phase 1 Alternative)

```python
import recordlinkage
import pandas as pd

# Load messages from PostgreSQL
messages = pd.read_sql("""
    SELECT id, content_hash, device_id, sender, body, timestamp
    FROM messaging_messages
""", connection)

# Create indexer for exact blocking on content_hash
indexer = recordlinkage.Index()
indexer.block('content_hash')

# Generate candidate pairs (same hash)
candidate_links = indexer.index(messages, messages)

# This finds exact duplicates efficiently
print(f"Found {len(candidate_links)} potential exact duplicates")

# For each pair, check device_id
for pair in candidate_links:
    msg_a = messages.loc[pair[0]]
    msg_b = messages.loc[pair[1]]
    
    if msg_a['device_id'] == msg_b['device_id']:
        # EXACT DUPLICATE - same content, same device
        print(f"Duplicate: {msg_a['id']} and {msg_b['id']}")
    else:
        # CROSS-DEVICE - same content, different source
        print(f"Cross-device evidence: {msg_a['device_id']} -> {msg_b['device_id']}")
```

### 2. Sender Name Resolution (Phase 2)

```python
# Match senders across messages
indexer = recordlinkage.Index()
indexer.block('sender_first_letter')  # Block on first letter for efficiency

c = recordlinkage.Compare()
c.string('sender', 'sender', method='jarowinkler', threshold=0.85)

# Generate comparison vectors
compare_vectors = c.compute(candidate_links, senders_df, senders_df)

# Use ECM classifier (unsupervised)
ecm = recordlinkage.ECMClassifier()
matches = ecm.fit_predict(compare_vectors)

# Result: "Jake" matches "Jake from V&B" with confidence 0.92
```

### 3. Document Linking (Phase 2)

```python
# Link related documents (evidence files)
documents = pd.read_sql("""
    SELECT uuid, filename, extraction_date, device_id, message_count
    FROM raw_documents
""", connection)

# Create pairs based on device and time proximity
indexer = recordlinkage.Index()
indexer.block('device_id')  # Same device

c = recordlinkage.Compare()
c.date('extraction_date', 'extraction_date', 
       missing_value=0.5,  # Different days get lower score
       swap=True)
c.numeric('message_count', 'message_count', 
          method='gauss', offset=0, scale=100)

# Find additive files (Jan-Feb-Mar -> Jan-Feb-Mar-Apr-May)
compare_vectors = c.compute(candidate_links, documents, documents)

matches = ecm.fit_predict(compare_vectors)

# Result: Document A is subset of Document B
# → Mark Document A as having overlapping evidence with Document B
```

### 4. Cross-Device Correlation (Phase 2)

```python
# Link conversations across devices
conversations = pd.read_sql("""
    SELECT 
        c.id,
        c.device_id,
        c.participants,
        c.message_count,
        c.start_date,
        c.end_date
    FROM messaging_conversations_enhanced c
""", connection)

# Create pairs across different devices
indexer = recordlinkage.Index()
indexer.add(recordlinkage.Index('device_id').difference())  # Different devices

c = recordlinkage.Compare()
# Compare participant lists (set similarity)
c.string('participants', 'participants', method='jarowinkler')
# Compare time overlap
c.date('start_date', 'end_date', missing_value=0.3)

compare_vectors = c.compute(candidate_links, conversations, conversations)

# Find conversations that might be the same across devices
matches = ecm.fit_predict(compare_vectors)

# Result: "Conversation from my phone" matches "Conversation from Katrina's phone"
# → Create Neo4j CROSS_SOURCE_SAME_CONTENT edge
```

## Integration Points

### In semantica_pipeline.py

```python
# semantica_pipeline.py

from recordlinkage import Index, Compare, ECMClassifier
import pandas as pd

class EvidenceLinker:
    """Use recordlinkage for document linking and sender resolution."""
    
    def __init__(self, postgres_connection):
        self.conn = postgres_connection
        self.indexer = Index()
        self.compare = Compare()
        self.classifier = ECMClassifier()
    
    def link_evidence_files(self, device_id: str) -> pd.DataFrame:
        """Link related evidence files from same device."""
        # Get all documents for this device
        docs = pd.read_sql("""
            SELECT uuid, filename, extraction_date, message_count
            FROM raw_documents
            WHERE device_id = ?
            ORDER BY extraction_date
        """, self.conn, params=[device_id])
        
        # Block on device_id (already filtered), compare date proximity
        self.indexer.block('device_id')
        
        self.compare.date('extraction_date', 'extraction_date', 
                          missing_value=0.5, swap=True)
        
        candidates = self.indexer.index(docs, docs)
        vectors = self.compare.compute(candidates, docs, docs)
        
        return self.classifier.fit_predict(vectors)
    
    def resolve_senders(self, messages: pd.DataFrame) -> pd.DataFrame:
        """Resolve sender names to canonical entities."""
        # Normalize senders across messages
        senders = messages[['sender']].drop_duplicates()
        
        # Block on first letter for efficiency
        self.indexer = Index()
        self.indexer.block('sender_first_letter')
        
        self.compare = Compare()
        self.compare.string('sender', 'sender', 
                           method='jarowinkler', 
                           threshold=0.85)
        
        # Find similar senders
        candidates = self.indexer.index(senders, senders)
        vectors = self.compare.compute(candidates, senders, senders)
        
        matches = self.classifier.fit_predict(vectors)
        
        # Create canonical sender mapping
        return self._build_canonical_mapping(senders, matches)
    
    def cross_device_correlation(self) -> pd.DataFrame:
        """Find overlapping conversations across devices."""
        # Get all conversations
        conversations = pd.read_sql("""
            SELECT id, device_id, participants, start_date, end_date
            FROM messaging_conversations_enhanced
        """, self.conn)
        
        # Create pairs across different devices
        self.indexer = Index()
        # ... blocking logic
        
        # Compare participants and time overlap
        self.compare.string('participants', 'participants', 
                           method='jarowinkler')
        
        candidates = self.indexer.index(conversations, conversations)
        vectors = self.compare.compute(candidates, conversations, conversations)
        
        return self.classifier.fit_predict(vectors)
```

### In Neo4j Integration

```python
# After recordlinkage finds relationships

async def create_evidence_links(self, links: pd.DataFrame):
    """Create Neo4j relationships from recordlinkage results."""
    
    for idx, (source_uuid, target_uuid) in enumerate(links[links['match'] == True].index):
        # Get match confidence
        confidence = links.loc[(source_uuid, target_uuid), 'confidence']
        
        # Create Neo4j relationship
        await self.neo4j.run("""
            MATCH (a:Evidence {uuid: $source})
            MATCH (b:Evidence {uuid: $target})
            MERGE (a)-[r:RELATED_EVIDENCE {
                confidence: $confidence,
                method: 'recordlinkage',
                detected_at: datetime()
            }]->(b)
        """, source=source_uuid, target=target_uuid, confidence=confidence)
```

## Performance Considerations

| Dataset Size | Blocking Method | Comparison Time | Memory |
|--------------|-----------------|-----------------|--------|
| < 10K records | Full comparison | Seconds | Low |
| 10K - 100K | Block on hash | Minutes | Medium |
| 100K - 1M | Block + SortedNeighbour | Minutes | Medium |
| > 1M | Multi-index + Sampling | Hours | High |

**For forensic evidence:**
- **File-level**: Usually < 1000 files → Full comparison OK
- **Message-level**: Could be millions → Block on `conversation_id` first
- **Sender resolution**: Block on first letter → Manageable

## Next Steps

1. **Phase 1 (Now)**: Use exact SHA-256 hash blocking (coordinator.ts)
2. **Phase 2 (Later)**: Integrate `recordlinkage` in Semantica for:
   - Document linking
   - Sender resolution
   - Cross-device correlation
   - Temporal pattern detection

## Dependencies

```txt
# requirements.txt
recordlinkage>=0.16.0  # BSD-3-Clause, actively maintained
pandas>=2.0.0
numpy>=1.24.0
scipy>=1.10.0
scikit-learn>=1.3.0
```

## References

- **Documentation**: https://recordlinkage.readthedocs.io/
- **GitHub**: https://github.com/J535D165/recordlinkage
- **License**: BSD-3-Clause (business-friendly)
- **Citation**: De Bruin, J. (2019). Python Record Linkage Toolkit. Zenodo. https://doi.org/10.5281/zenodo.3559043

---

*Don't build what exists. Use recordlinkage for dedup + linking.*