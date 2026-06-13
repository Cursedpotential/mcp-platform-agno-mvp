---
title: Dual-Level Deduplication Logic
version: 1.0.0
created: 2026-03-04 21:15
modified: 2026-03-04 21:15
author: execution@opencode
project: traceiq-forensic
status: active
---

# Dual-Level Deduplication Logic

> **Critical Forensic Evidence Platform Architecture**: How to handle duplicate evidence from multiple sources without losing provenance.

## The Problem

Evidence comes from multiple sources:
- Your phone (primary source)
- Your partner's phone (secondary source - Katrina's device)
- Your computer backups
- Cloud exports
- Third-party extractions

**Key insight**: Same content from different devices is **NOT a duplicate** - it's independent evidence from different sources.

Example scenario:
```
File A (Jan): Messages from Jan-Mar (my phone)
File B (Feb): Messages from Jan-Apr (my phone)     ← Contains A + new messages
File C (Jan): Messages from Jan-Mar (Katrina's phone) ← Same content, DIFFERENT SOURCE
```

**Deduplication rules:**
1. File A and File B: File-level duplicate (same device, A is subset of B)
2. File A and File C: **NOT duplicates** (different devices = different sources)
3. Message duplicate check must account for device_id

---

## Two-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         LEVEL 1: FILE DEDUP                         │
│                                                                     │
│  Input: Raw file (SMS XML, Facebook JSON/HTML export, etc.)        │
│  Compute: SHA-256 hash of ENTIRE file content                      │
│  Check: Does (hash + device_id) exist in DuckDB?                   │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │                                                               │ │
│  │  IF same_hash AND same_device:                               │ │
│  │    → DUPLICATE FILE                                          │ │
│  │    → Skip processing, return existing UUID                    │ │
│  │                                                               │ │
│  │  IF same_hash BUT different_device:                          │ │
│  │    → NEW FILE (different source)                             │ │
│  │    → Process for message-level dedup                          │ │
│  │                                                               │ │
│  │  IF new_hash:                                                │ │
│  │    → NEW FILE                                                │ │
│  │    → Proceed to message-level dedup                          │ │
│  │                                                               │ │
│  └───────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘

                              │
                              ▼
                              
┌─────────────────────────────────────────────────────────────────────┐
│                      LEVEL 2: MESSAGE DEDUP                          │
│                                                                     │
│  Input: Parsed messages from file                                  │
│  Compute: SHA-256 hash of message content + metadata               │
│  Check: Does (content_hash + device_id + conversation_id) exist?   │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │                                                               │ │
│  │  IF same_content_hash                                        │ │
│  │     AND same_device                                          │ │
│  │     AND same_conversation_id:                                │ │
│  │    → DUPLICATE MESSAGE                                       │ │
│  │    → Skip insertion, link to existing                        │ │
│  │    → Still track in file-level audit                         │ │
│  │                                                               │ │
│  │  IF same_content_hash BUT different_device:                  │ │
│  │    → NEW MESSAGE (independent evidence from different source) │ │
│  │    → Insert into DB                                          │ │
│  │    → Track provenance: "same content, different source"     │ │
│  │    → Create cross-reference in Neo4j                         │ │
│  │                                                               │ │
│  └───────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Implementation

### Database Schema (DuckDB + PostgreSQL)

```sql
-- DuckDB: File-level dedup (Tier 1)
CREATE TABLE raw_documents (
  uuid TEXT PRIMARY KEY,           -- UUIDv7
  hash TEXT NOT NULL,              -- SHA-256 of file
  device_id TEXT NOT NULL,         -- Source device identifier
  file_path TEXT,                  -- Original file location
  file_size BIGINT,
  ingestion_timestamp TIMESTAMP,
  status TEXT,                     -- 'accepted', 'duplicate_file', 'processed'
  
  UNIQUE(hash, device_id)          -- Composite uniqueness
);

-- PostgreSQL: Message-level dedup (Tier 4)
CREATE TABLE messaging_messages (
  id UUID PRIMARY KEY,
  content_hash TEXT NOT NULL,      -- SHA-256 of message content
  device_id TEXT NOT NULL,         -- Source device
  conversation_id TEXT NOT NULL,
  sender TEXT NOT NULL,
  body TEXT,
  timestamp TIMESTAMP,
  provenance TEXT,                 -- JSON: source file, extraction method
  
  UNIQUE(content_hash, device_id, conversation_id)
);

-- Neo4j: Cross-source references (Tier 3)
// When same content exists from different devices:
CREATE (a:Message {content_hash: $hash, device_id: "device_A"})
CREATE (b:Message {content_hash: $hash, device_id: "device_B"})
CREATE (a)-[:CROSS_SOURCE_SAME_CONTENT {
  detected_at: datetime(),
  relationship: "independent_corroboration"
}]->(b)
```

### Coordinator Flow

```typescript
// server/mcp/ingest/coordinator.ts

async function processDocument(rawFile: Buffer, metadata: DocumentMetadata) {
  // ═══════════════════════════════════════════════════════════════
  // LEVEL 1: FILE-LEVEL DEDUP
  // ═══════════════════════════════════════════════════════════════
  
  const fileHash = createHash('sha256').update(rawFile).digest('hex')
  const uuid = generateUUIDv7()
  
  // Check: same hash + same device?
  const existingFile = await duckdb.query(`
    SELECT uuid, hash, device_id, status 
    FROM raw_documents 
    WHERE hash = ? AND device_id = ?
  `, [fileHash, metadata.device_id])
  
  if (existingFile.length > 0) {
    // EXACT FILE DUPLICATE - same device, same content
    logger.info({
      event: 'file_duplicate',
      hash: fileHash,
      device_id: metadata.device_id,
      existing_uuid: existingFile[0].uuid
    })
    
    return {
      status: 'duplicate_file',
      uuid: existingFile[0].uuid,
      hash: fileHash,
      device_id: metadata.device_id,
      duplicate_type: 'file'
    }
  }
  
  // ═══════════════════════════════════════════════════════════════
  // NEW FILE - Proceed to parsing
  // ═══════════════════════════════════════════════════════════════
  
  const format = detectFormat(rawFile)
  const parsed = await parseWithRightParser(format, rawFile)
  
  // Log file acceptance (chain of custody starts HERE)
  await duckdb.insert({
    uuid: uuid,
    hash: fileHash,
    device_id: metadata.device_id,
    file_path: metadata.file_path,
    file_size: rawFile.length,
    ingestion_timestamp: new Date().toISOString(),
    status: 'accepted'
  })
  
  // ═══════════════════════════════════════════════════════════════
  // LEVEL 2: MESSAGE-LEVEL DEDUP
  // ═══════════════════════════════════════════════════════════════
  
  const messageResults = []
  
  for (const message of parsed.messages) {
    // Hash the message content (not the whole file)
    const contentHash = createHash('sha256')
      .update(JSON.stringify({
        conversation_id: message.conversation_id,
        sender: message.sender,
        body: message.body,
        timestamp: message.timestamp
      }))
      .digest('hex')
    
    // Check: same content + same device + same conversation?
    const existingMessage = await postgresql.query(`
      SELECT id, content_hash, device_id, conversation_id 
      FROM messaging_messages 
      WHERE content_hash = ? AND device_id = ? AND conversation_id = ?
    `, [contentHash, metadata.device_id, message.conversation_id])
    
    if (existingMessage.length > 0) {
      // MESSAGE DUPLICATE - same device, same content
      messageResults.push({
        status: 'duplicate_message',
        content_hash: contentHash,
        device_id: metadata.device_id,
        existing_id: existingMessage[0].id
      })
      continue
    }
    
    // ═══════════════════════════════════════════════════════════
    // NEW MESSAGE - Check for CROSS-SOURCE MATCH
    // ═══════════════════════════════════════════════════════════
    
    const crossSourceMatch = await postgresql.query(`
      SELECT id, device_id, conversation_id 
      FROM messaging_messages 
      WHERE content_hash = ? AND device_id != ?
    `, [contentHash, metadata.device_id])
    
    if (crossSourceMatch.length > 0) {
      // SAME CONTENT, DIFFERENT DEVICE
      // This is INDEPENDENT CORROBORATION, not a duplicate
      
      logger.info({
        event: 'cross_source_match',
        content_hash: contentHash,
        new_device: metadata.device_id,
        existing_devices: crossSourceMatch.map(m => m.device_id),
        relationship: 'independent_corroboration'
      })
      
      // Insert as NEW message with provenance
      const newMessageId = await postgresql.insert({
        id: generateUUIDv7(),
        content_hash: contentHash,
        device_id: metadata.device_id,
        conversation_id: message.conversation_id,
        sender: message.sender,
        body: message.body,
        timestamp: message.timestamp,
        provenance: JSON.stringify({
          source_file: uuid,
          extraction_method: format,
          duplicate_of: null,
          cross_source_match: crossSourceMatch[0].id
        })
      })
      
      // Create Neo4j cross-reference
      await semantica.createCrossReference({
        message_a: crossSourceMatch[0].id,
        message_b: newMessageId,
        relationship: 'CROSS_SOURCE_SAME_CONTENT'
      })
    } else {
      // COMPLETELY NEW MESSAGE (no matches anywhere)
      await postgresql.insert({
        id: generateUUIDv7(),
        content_hash: contentHash,
        device_id: metadata.device_id,
        conversation_id: message.conversation_id,
        sender: message.sender,
        body: message.body,
        timestamp: message.timestamp,
        provenance: JSON.stringify({
          source_file: uuid,
          extraction_method: format,
          duplicate_of: null,
          cross_source_match: null
        })
      })
    }
    
    messageResults.push({
      status: 'new_message',
      content_hash: contentHash,
      device_id: metadata.device_id,
      conversation_id: message.conversation_id
    })
  }
  
  // ═══════════════════════════════════════════════════════════════
  // CONTINUE PIPELINE: LanceDB → Semantica → Neo4j
  // ═══════════════════════════════════════════════════════════════
  
  await continuePipeline({ uuid, parsed, messageResults })
  
  return {
    status: 'processed',
    uuid: uuid,
    file_hash: fileHash,
    messages: messageResults
  }
}
```

---

## Key Principles

### 1. Device Identity is Non-Negotiable

```typescript
// WRONG - Device ID not checked
const isDuplicate = await checkHash(hash)

// RIGHT - Device ID MUST be included
const isDuplicate = await checkHashAndDevice(hash, device_id)
```

### 2. Hash BEFORE Transformation

```typescript
// WRONG - Hash after parsing
const parsed = await parse(rawFile)
const hash = sha256(parsed)

// RIGHT - Hash the RAW file, BEFORE any transformation
const hash = sha256(rawFile)
const parsed = await parse(rawFile)
```

### 3. Cross-Source is Evidence, Not Duplicate

```typescript
// WRONG - Treat cross-device as duplicate
if (sameContent) skip()

// RIGHT - Cross-device is INDEPENDENT VERIFICATION
if (sameContent && sameDevice) {
  skip()  // True duplicate
} else if (sameContent && differentDevice) {
  insert()  // Independent evidence
  createCrossReference()
}
```

### 4. Provenance Tracking

Every message MUST have provenance JSON:
```typescript
interface Provenance {
  source_file: string          // UUID of source file
  extraction_method: string    // 'sms_xml', 'facebook_json', 'facebook_html', etc.
  duplicate_of: string | null  // UUID of original if duplicate
  cross_source_match: string | null  // UUID of cross-device match
}
```

### 5. Audit Trail

```
File A (my device, Jan):
  └─ hash: abc123
  └─ status: accepted
  └─ messages: [m1, m2, m3]

File B (my device, Feb):
  └─ hash: xyz789
  └─ status: accepted
  └─ messages: [m1_dup, m2_dup, m3_dup, m4_new, m5_new]
  └─ provenance: [{ duplicate_of: m1 }, { duplicate_of: m2 }, ...]

File C (Katrina's device, Jan):
  └─ hash: def456
  └─ status: accepted
  └─ messages: [m1_cross, m2_cross, m3_cross]
  └─ provenance: [{ cross_source_match: m1 }, ...]
  └─ Neo4j: (m1)-[:CROSS_SOURCE_SAME_CONTENT]->(m1_cross)
```

---

## Testing Scenarios

### Scenario 1: Exact File Duplicate

```typescript
// File A uploaded twice
const result1 = await processDocument(fileA, { device_id: 'my-phone' })
// → status: 'processed', messages: [new, new, new]

const result2 = await processDocument(fileA, { device_id: 'my-phone' })
// → status: 'duplicate_file', existing_uuid: result1.uuid
```

### Scenario 2: Additive File (Overlapping Messages)

```typescript
// File A: Jan-Mar
const result1 = await processDocument(fileA, { device_id: 'my-phone' })
// → messages: [Jan, Feb, Mar]

// File B: Jan-Apr (contains A + Apr)
const result2 = await processDocument(fileB, { device_id: 'my-phone' })
// → messages: [Jan_dup, Feb_dup, Mar_dup, Apr_new, May_new]
```

### Scenario 3: Cross-Device (Same Content, Different Source)

```typescript
// File A (my phone)
const result1 = await processDocument(fileA, { device_id: 'my-phone' })
// → messages: [m1, m2, m3]

// File C (Katrina's phone, same conversation)
const result2 = await processDocument(fileC, { device_id: 'katrina-phone' })
// → messages: [m1_cross, m2_cross, m3_cross]
// → Each message linked via Neo4j CROSS_SOURCE_SAME_CONTENT
```

### Scenario 4: Unknown Device

```typescript
// If device_id is missing or invalid
await processDocument(file, { device_id: undefined })
// → THROW ValidationError: "device_id is required"
```

---

## Fefe Schema for Deduplication

```typescript
import { object, string, number, boolean, optional } from 'fefe'

// File-level dedup key
const validateFileKey = object({
  hash: string({ regex: /^[a-f0-9]{64}$/, minLength: 64, maxLength: 64 }),
  device_id: string({ minLength: 1 }),
  file_path: optional(string()),
  file_size: number({ min: 0, integer: true })
}, {
  allowExcessProperties: false,
  allErrors: true
})

// Message-level dedup key
const validateMessageKey = object({
  content_hash: string({ regex: /^[a-f0-9]{64}$/ }),
  device_id: string({ minLength: 1 }),
  conversation_id: string({ minLength: 1 }),
  timestamp: string(),
  sender: string({ minLength: 1 }),
  body: optional(string())
}, {
  allowExcessProperties: false,
  allErrors: true
})

// Cross-source match detection
const validateCrossSourceMatch = object({
  content_hash: string({ regex: /^[a-f0-9]{64}$/ }),
  matching_device_id: string({ minLength: 1 }),
  matching_message_id: string(),
  relationship: string()  // 'independent_corroboration'
})
```

---

## Summary

| Level | What | Key | Dedup Logic |
|-------|------|-----|-------------|
| 1 | File | `hash + device_id` | Same hash + same device = duplicate |
| 2 | Message | `content_hash + device_id + conversation_id` | Same content + same device = duplicate |
| Cross-source | Message | `content_hash` | Same content + different device = NEW evidence |

**Critical**: Device identity is the boundary. Never deduplicate across devices.

---

*Chain of custody starts at hash. Provenance ends at cross-reference.*
