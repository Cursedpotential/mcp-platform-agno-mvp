---
title: RecordLinkage Platform Integration - Across Sources
version: 1.0.0
created: 2026-03-04 23:45
modified: 2026-03-04 23:45
author: execution@opencode
project: traceiq-forensic
status: active
---

# RecordLinkage Platform Integration - Across Sources

> **How recordlinkage connects conversations across platforms, formats, and databases**

## The Question

**What exactly is it "linking"?**
- Conversations together?
- Different formats of the same file (SMS XML vs backup vs Facebook JSON/HTML export)?
- Across Neo4j → Semantica → PostgreSQL → DuckDB?

## Answer: It Links ENTITIES Across All Tiers

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    RECORDLINKAGE IN THE PIPELINE                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐   │
│  │  INGESTION (coordinator.ts)                                           │   │
│  │                                                                       │   │
│  │  Phase 1: EXACT dedup                                                 │   │
│  │  - SHA-256 hash → Block on exact match                                │   │
│  │  - Fast: O(1) lookup                                                  │   │
│  │  - NO recordlinkage needed here (hash comparison is faster)          │   │
│  └───────────────────────────────────────────────────────────────────────┘   │
│                              │                                              │
│                              ▼                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐   │
│  │  SEMANTICA (Python pipeline)                                          │   │
│  │                                                                       │   │
│  │  Phase 2: ENTITY RESOLUTION & ACROSS-SOURCES LINKING                  │   │
│  │                                                                       │   │
│  │  Uses recordlinkage WITH Pandas DataFrames:                           │   │
│  │                                                                       │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐   │   │
│  │  │  INPUT: Pull from ALL tiers                                     │   │   │
│  │  │                                                                 │   │   │
│  │  │  DuckDB: SELECT * FROM raw_documents                            │   │   │
│  │  │  PostgreSQL: SELECT * FROM messaging_messages                  │   │   │
│  │  │  Neo4j: MATCH (e:Evidence) RETURN e                            │   │   │
│  │  │                                                                 │   │   │
│  │  │  → Load into Pandas DataFrames                                   │   │   │
│  │  │  → recordlinkage works on DataFrames                            │   │   │
│  │  └─────────────────────────────────────────────────────────────────┘   │   │
│  │                                                                       │   │
│  │  recordlinkage DOES:                                                  │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐   │   │
│  │  │  1. CONVERSATION LINKING                                         │   │   │
│  │  │     df_sms[df_sms['conversation_id'] == conv_id]                │   │   │
│  │  │     df_facebook[df_facebook['participants'].str.contains(name)] │   │   │
│  │  │     → Link: SMS thread "Jake" = Facebook chat "Jake V&B"       │   │   │
│  │  │                                                                 │   │   │
│  │  │  2. SENDER RESOLUTION                                           │   │   │
│  │  │     indexer.block('sender_first_letter')                       │   │   │
│  │  │     compare.string('sender', 'sender', method='jarowinkler')   │   │   │
│  │  │     → Link: "Jake" = "Jake from V&B" = "Jake V&B Party Store"  │   │   │
│  │  │                                                                 │   │   │
│  │  │  3. DIFFERENT FORMATS OF SAME FILE                               │   │   │
│  │  │     # SMS XML from January                                       │   │   │
│  │  │     # SMS backup from March (contains January + Feb + March)    │   │   │
│  │  │     compare.date('start_date', 'end_date')                      │   │   │
│  │  │     compare.numeric('message_count')                            │   │   │
│  │  │     → Link: "Document A is subset of Document B"              │   │   │
│  │  │                                                                 │   │   │
│  │  │  4. ACROSS-SOURCES EVIDENCE                                     │   │   │
│  │  │     # Your phone + Katrina's phone                              │   │   │
│  │  │     indexer.add(recordlinkage.Index('device_id').difference())  │   │   │
│  │  │     compare.string('body', 'body', method='exact')              │   │   │
│  │  │     → Link: Same conversation from different devices            │   │   │
│  │  │     → Neo4j: CREATE (a)-[:SAME_CONTENT_DIFFERENT_SOURCE]->(b)   │   │   │
│  │  └─────────────────────────────────────────────────────────────────┘   │   │
│  │                                                                       │   │
│  │  OUTPUT: Write links to Neo4j + PostgreSQL                           │   │
│  │                                                                       │   │
│  └───────────────────────────────────────────────────────────────────────┘   │
│                              │                                              │
│                              ▼                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐   │
│  │  NEO4J (Knowledge Graph)                                              │   │
│  │                                                                       │   │
│  │  Stores the RELATIONSHIPS found by recordlinkage:                    │   │
│  │                                                                       │   │
│  │  (Jake)-[:CITES_IN_EVIDENCE]->(Message {body: "..."})               │   │
│  │  (Conversation:SMS)-[:LINKED_TO]->(Conversation:Facebook)            │   │
│  │  (Document:January)-[:SUBSET_OF]->(Document:March)                  │   │
│  │  (Message:MyPhone)-[:SAME_CONTENT_DIFFERENT_SOURCE]->(Message:Katrina)│   │
│  │                                                                       │   │
│  └───────────────────────────────────────────────────────────────────────┘   │
│                              │                                              │
│                              ▼                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐   │
│  │  DUCKDB (Analytics)                                                   │   │
│  │                                                                       │   │
│  │  Query across all linked entities:                                   │   │
│  │                                                                       │   │
│  │  SELECT                                                               │   │
│  │    m.sender,                                                          │   │
│  │    COUNT(*) as message_count,                                         │   │
│  │    array_agg(DISTINCT d.device_id) as devices                        │   │
│  │  FROM messages m                                                      │   │
│  │  JOIN document_links l ON m.document_id = l.source_id               │   │
│  │  JOIN raw_documents d ON l.target_id = d.uuid                        │   │
│  │  WHERE l.link_type = 'SAME_SENDER'                                   │   │
│  │  GROUP BY m.sender                                                    │   │
│  │                                                                       │   │
│  │  Result: "Jake" across ALL devices, ALL formats                      │   │
│  │                                                                       │   │
│  └───────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## What RecordLinkage Actually Does

### 1. Across Conversations

```python
# Link conversations across platforms

import recordlinkage
import pandas as pd

# Pull from PostgreSQL
sms = pd.read_sql("SELECT * FROM messaging_messages WHERE platform = 'sms'", conn)
facebook = pd.read_sql("SELECT * FROM messaging_messages WHERE platform = 'facebook'", conn)

# Create pairs of conversations across platforms
indexer = recordlinkage.Index()
# Block on participants (same people in conversation)
indexer.block('participants')  # "Jake_Katrina" blocks together

compare = recordlinkage.Compare()
# Compare time windows
compare.date('timestamp', 'timestamp', missing_value=0.5)
# Compare sent vs received patterns
compare.string('body', 'body', method='jarowinkler')

# Find matching conversations across platforms
candidates = indexer.index(sms, facebook)
vectors = compare.compute(candidates, sms, facebook)

ecm = recordlinkage.ECMClassifier()
matches = ecm.fit_predict(vectors)

# Result: SMS thread "Jake_Katrina" = Facebook chat "Jake_V&B_Katrina"
```

### 2. Across Formats (Same File, Different Export)

```python
# Link SMS XML (January) with SMS backup (March contains January)

documents = pd.read_sql("""
    SELECT uuid, filename, extraction_date, message_count, device_id
    FROM raw_documents
    WHERE format = 'sms_xml'
""", conn)

# Create pairs of documents from same device
indexer = recordlinkage.Index()
indexer.block('device_id')

compare = recordlinkage.Compare()
# Time range overlap
compare.date('start_date', 'end_date', missing_value=0.3)
# Message count (subset detection)
compare.numeric('message_count', 'message_count', method='gauss')

candidates = indexer.index(documents, documents)
vectors = compare.compute(candidates, documents, documents)

matches = ecm.fit_predict(vectors)

# Result:
# Document January (Jan-Mar, 100 messages) is SUBSET of
# Document March (Jan-May, 200 messages)
# → Link them in Neo4j
```

### 3. Across Devices

```python
# Link messages from your phone + Katrina's phone

your_messages = pd.read_sql("""
    SELECT * FROM messaging_messages WHERE device_id = 'your_phone'
""", conn)

their_messages = pd.read_sql("""
    SELECT * FROM messaging_messages WHERE device_id = 'katrina_phone'
""", conn)

# Create pairs ACROSS devices (different device_id)
indexer = recordlinkage.Index()
indexer.block('sender_first_letter')  # Same sender first letter

compare = recordlinkage.Compare()
compare.exact('body')  # Exact content match
compare.date('timestamp', threshold_seconds=60)  # Same time +/- 60 seconds

candidates = indexer.index(your_messages, their_messages)
vectors = compare.compute(candidates, your_messages, their_messages)

# Same content + same time + different device = CROSS_SOURCE_SAME_CONTENT
matches = ecm.fit_predict(vectors)

# Create Neo4j relationship
for match in matches:
    neo4j.run("""
        MATCH (a:Message {id: $your_id})
        MATCH (b:Message {id: $their_id})
        CREATE (a)-[:SAME_CONTENT_DIFFERENT_SOURCE {
            your_device: 'your_phone',
            their_device: 'katrina_phone',
            matched_at: datetime()
        }]->(b)
    """, your_id=match[0], their_id=match[1])
```

### 4. Across Neo4j + Semantica + PostgreSQL + DuckDB

```python
# Pull from all tiers into Pandas
duckdb_df = pd.read_sql("SELECT * FROM raw_documents", duckdb_conn)
postgres_df = pd.read_sql("SELECT * FROM messaging_messages", postgres_conn)
neo4j_df = pd.DataFrame(neo4j.run("MATCH (e:Evidence) RETURN e.uuid, e.type"))

# recordlinkage can merge ALL of these
merged = pd.merge(
    duckdb_df,
    postgres_df,
    left_on='uuid',
    right_on='source_document',
    how='outer'
)

# Now run recordlinkage on the merged DataFrame
indexer = recordlinkage.Index()
indexer.block('device_id')

# ... compare across all columns
```

## The Flow

```
1. INGESTION (TypeScript coordinator)
   └─ SHA-256 hash comparison (FAST, EXACT, no recordlinkage needed)
   
2. SEMANTICA (Python pipeline)
   ├─ Pull DataFrames from DuckDB + PostgreSQL + Neo4j
   ├─ Run recordlinkage for:
   │  ├─ Conversation linking (SMS ↔ Facebook)
   │  ├─ Sender resolution ("Jake" = "Jake V&B")
   │  ├─ Document linking (January ⊂ March backup)
   │  └─ Across-sources (My phone ↔ Their phone)
   ├─ Write relationships to Neo4j
   └─ Write resolved entities to PostgreSQL
   
3. NEO4J (Knowledge Graph)
   └─ Store relationships: (Entity)-[:LINKED_TO]->(Entity)
   
4. DUCKDB (Analytics)
   └─ Query across ALL linked entities
```

## Why This Works

| What | Why recordlinkage |
|------|-------------------|
| **Pandas DataFrames** | All tiers can export to Pandas |
| **Blocking** | Fast filtering before comparison |
| **Fuzzy matching** | Handle name variations naturally |
| **Cross-source** | Compare across ANY DataFrames |
| **Unsupervised** | ECM classifier needs no training data |
| **BSD License** | Business-friendly |

## When to Use

| Use Case | Use recordlinkage? |
|----------|-------------------|
| Exact duplicates (Phase 1) | ❌ No - SHA-256 is faster |
| Fuzzy sender matching | ✅ Yes - Jaro-Winkler |
| Conversation linking | ✅ Yes - Block on participants |
| Document linking | ✅ Yes - Date + count comparison |
| Cross-device evidence | ✅ Yes - Same body + diff device |
| Cross-platform (SMS + Facebook) | ✅ Yes - Time + participants |

## Summary

**recordlinkage links ENTITIES across ALL tiers:**
1. Pull data from DuckDB + PostgreSQL + Neo4j into Pandas
2. Run comparison algorithms across ALL sources
3. Write relationships back to Neo4j
4. Query across everything in DuckDB

**Don't build custom linking logic - use recordlinkage.**
