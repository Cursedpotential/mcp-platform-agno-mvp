---
title: Pipeline Verification Analysis - Best Practices Research
version: 1.0.0
created: 2026-03-16 19:00
modified: 2026-03-16 19:00
author: thinking@opencode
project: dial-stack
status: final
---

# Pipeline Verification Analysis

## Executive Summary

Research into digital evidence handling best practices confirms the dial-stack architecture is on the right track with **4 critical gaps** requiring immediate attention.

### Critical Findings:

| Requirement | Status | Priority |
|-------------|--------|----------|
| Hash recomputation at retrieval | ❌ MISSING | CRITICAL |
| Timestamp to Eastern Time (DST-aware) | ❌ MISSING | CRITICAL |
| SQLite WAL/Carving for deleted data | ❌ MISSING | CRITICAL |
| Cryptographic signing | ❌ MISSING | HIGH |
| Case-level grouping | ✅ NOT NEEDED | N/A (personal case) |

---

## Best Practices Research Summary

### Chain of Custody Requirements (SWGDE, Cellebrite, NIST)

1. **Hash verification at EVERY step** - SHA-256 minimum, re-verify on retrieval
2. **Write-once, read-many (WORM)** - Original files never modified
3. **Audit trail with timestamps** - Who, what, when, why for every action
4. **Cryptographic signing** - Ed25519 or HMAC for integrity verification
5. **Metadata preservation** - Original file metadata captured before processing

### Message Parsing/Reassembly (ConversationExtractor, Cellebrite)

1. **SQLite WAL processing** - Deleted messages often in WAL files
2. **Binary carving** - Recover fragments from unallocated space
3. **Thread reconstruction** - Match messages by participants, order by timestamp
4. **Confidence scoring** - Track reliability of recovered data
5. **Multi-source correlation** - SMS + call logs + contacts for complete picture

### Evidence Management Architecture (Axon, VeriPic, VIDIZMO)

1. **Centralized metadata store** - PostgreSQL for canonical records
2. **Tiered storage** - Hot (PostgreSQL) → Warm (LanceDB) → Cold (Archive)
3. **GraphQL federation** - Single query interface across all storage tiers
4. **Cross-verification** - Multiple detection systems compare results
5. **Audit query interface** - Chain of custody verifiable at any point

---

## Simulation Results

### Simulation 1: SMS Message Ingestion

**File**: `messages_2026-03-16.xml` (SMS Backup & Restore)

| Step | Component | Action | Best Practice Check |
|------|-----------|--------|---------------------|
| 1 | DuckDB (T1) | Hash + Dedup + Clock | ✅ Hash before processing |
| 2 | PostgreSQL (T2) | UUID assignment | ✅ UUID before tagging |
| 3 | ContextForge | PII/Content tagging | ✅ Permissive mode, no modification |
| 4 | LanceDB (T3) | Embedding generation | ✅ Uses tags for filtering |
| 5 | Neo4j/Semantica (T4) | Entity extraction | ✅ Uses tags for prioritization |
| 6 | PostgreSQL (T2) | Final storage | ✅ All flags consolidated |
| 7 | WunderGraph Cosmo | Retrieval | ❌ NO HASH VERIFICATION |

**Gap Found**: Hash not re-verified at retrieval

### Simulation 2: Deleted Message Recovery

**Files**: `mmssms.db`, `mmssms.db-wal`, `mmssms.db-shm`

| Step | Component | Action | Status |
|------|-----------|--------|--------|
| 1 | DuckDB (T1) | Hash each file separately | ✅ Works |
| 2 | PostgreSQL (T2) | Case grouping | ✅ NOT NEEDED (personal) |
| 3 | Custom Tool | WAL parsing | ❌ DOESN'T EXIST |
| 4 | Custom Tool | Binary carving | ❌ DOESN'T EXIST |
| 5 | Neo4j/Semantica | Thread reconstruction | ✅ Can use recovered data |

**Gap Found**: No SQLite WAL parser or binary carver

### Simulation 3: Multi-Source Correlation

**Files**: iPhone backup, Gmail export, Facebook data

| Step | Component | Action | Status |
|------|-----------|--------|--------|
| 1 | DuckDB (T1) | Hash all files | ✅ Works |
| 2 | PostgreSQL (T2) | Canonical entity mapping | ❌ NEEDS ENTITY RESOLVER |
| 3 | Custom Tool | Timeline normalization | ❌ NEEDS TIMELINE NORMALIZER |
| 4 | Neo4j/Semantica | Relationship graph | ✅ Works |
| 5 | WunderGraph Cosmo | Unified query | ✅ Works |

**Gap Found**: No canonical entity resolver or timeline normalizer

---

## Critical Gap: Hash Recomputation

### Problem
Current architecture computes hash once at DuckDB (T1) but never re-verifies at retrieval.

### Solution: pgcrypto + External Library

**PostgreSQL Implementation:**
```sql
-- Enable pgcrypto
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Evidence table with hash verification
CREATE TABLE evidence (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  original_hash TEXT NOT NULL,
  hash_algorithm TEXT DEFAULT 'sha256',
  file_path TEXT NOT NULL,
  -- ... other fields ...
  verification_status TEXT DEFAULT 'pending',
  last_verified_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Hash verification function
CREATE OR REPLACE FUNCTION verify_evidence_hash(
  p_evidence_id UUID,
  p_content BYTEA
) RETURNS TEXT AS $$
DECLARE
  v_stored_hash TEXT;
  v_computed_hash TEXT;
BEGIN
  SELECT original_hash INTO v_stored_hash
  FROM evidence WHERE id = p_evidence_id;
  
  v_computed_hash := encode(sha256(p_content), 'hex');
  
  IF v_stored_hash = v_computed_hash THEN
    UPDATE evidence SET
      verification_status = 'verified',
      last_verified_at = NOW()
    WHERE id = p_evidence_id;
    RETURN 'VERIFIED';
  ELSE
    UPDATE evidence SET
      verification_status = 'tampered',
      last_verified_at = NOW()
    WHERE id = p_evidence_id;
    RETURN 'TAMPERED';
  END IF;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
```

**External Library (Python):**
```python
# Use hashlib for hash verification
import hashlib

def verify_evidence_hash(file_path: str, stored_hash: str) -> tuple[str, str]:
    """
    Verify evidence file hash.
    
    Returns:
        tuple: (status, computed_hash)
        status: 'VERIFIED' or 'TAMPERED'
    """
    with open(file_path, 'rb') as f:
        file_content = f.read()
    
    computed_hash = hashlib.sha256(file_content).hexdigest()
    
    if stored_hash == computed_hash:
        return ('VERIFIED', computed_hash)
    else:
        return ('TAMPERED', computed_hash)
```

---

## Critical Gap: Eastern Time Conversion (DST-Aware)

### Problem
Timestamps are in UTC or Unix format. User needs human-readable Eastern Time with proper DST handling.

### Solution: PostgreSQL AT TIME ZONE + Python Library

**PostgreSQL Implementation:**
```sql
-- Store as TIMESTAMPTZ (UTC internally)
CREATE TABLE evidence (
  id UUID PRIMARY KEY,
  event_timestamp TIMESTAMPTZ NOT NULL,  -- Stored as UTC
  -- ... other fields ...
);

-- Convert to Eastern Time for display
SELECT 
  id,
  event_timestamp AS utc_time,
  event_timestamp AT TIME ZONE 'America/New_York' AS eastern_time,
  to_char(event_timestamp AT TIME ZONE 'America/New_York', 'YYYY-MM-DD HH12:MI:SS AM') AS eastern_readable
FROM evidence;

-- Example output:
-- utc_time: 2026-03-16 18:00:00+00
-- eastern_time: 2026-03-16 14:00:00 (EDT - daylight time)
-- eastern_readable: 2026-03-16 02:00:00 PM
```

**Python Library: pendulum (Recommended)**
```python
import pendulum

def convert_to_eastern(utc_timestamp: str) -> dict:
    """
    Convert UTC timestamp to Eastern Time with DST handling.
    
    Uses pendulum for proper DST transitions.
    """
    # Parse UTC timestamp
    dt = pendulum.parse(utc_timestamp)
    
    # Convert to Eastern Time
    eastern = dt.in_timezone('America/New_York')
    
    return {
        'utc': dt.format('YYYY-MM-DD HH:mm:ss'),
        'eastern': eastern.format('YYYY-MM-DD hh:mm:ss A'),
        'timezone': eastern.timezone_name,  # 'EST' or 'EDT'
        'is_dst': eastern.is_dst(),
        'offset': eastern.offset_hours,  # -5 (EST) or -4 (EDT)
        'human_readable': eastern.format('dddd, MMMM D, YYYY [at] h:mm A')
    }

# Example:
# convert_to_eastern('2026-03-16T18:00:00Z')
# Returns:
# {
#   'utc': '2026-03-16 18:00:00',
#   'eastern': '2026-03-16 02:00:00 PM',
#   'timezone': 'EDT',
#   'is_dst': True,
#   'offset': -4,
#   'human_readable': 'Monday, March 16, 2026 at 2:00 PM'
# }
```

**Why pendulum over pytz:**
- Cleaner API
- Automatic DST handling
- Human-readable formatting built-in
- Handles edge cases (ambiguous times, non-existent times)

---

## Critical Gap: SQLite WAL/Carving

### Problem
Deleted messages often exist in SQLite WAL files or unallocated space. Current tools don't recover these.

### Solution: Add sqlite_wal_parser Tool

**Tool: sqlite_wal_parser**
```python
# TS MCP Server - sqlite_wal_parser.ts

interface WALMessage {
  rowid: number;
  timestamp: number;
  address: string;
  body: string;
  status: 'existing' | 'deleted_in_wal' | 'carved';
  confidence: number;
}

async function parseSQLiteWAL(dbPath: string, walPath: string): Promise<WALMessage[]> {
  // 1. Parse main database for existing messages
  const existingMessages = await parseSQLiteDB(dbPath);
  
  // 2. Parse WAL file for deleted message fragments
  const walMessages = await parseWALFile(walPath);
  
  // 3. Find messages in WAL but not in main DB
  const deletedMessages = walMessages.filter(
    wm => !existingMessages.find(em => em.rowid === wm.rowid)
  );
  
  // 4. Tag with recovery status
  return deletedMessages.map(dm => ({
    ...dm,
    status: 'deleted_in_wal',
    confidence: 0.95
  }));
}
```

---

## Critical Gap: Cryptographic Signing

### Problem
No digital signatures on evidence records. Chain of custody could be challenged.

### Solution: Ed25519 Signatures

```python
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
import base64

class EvidenceSigner:
    def __init__(self):
        self.private_key = ed25519.Ed25519PrivateKey.generate()
        self.public_key = self.private_key.public_key()
    
    def sign_evidence(self, evidence_id: str, hash: str, timestamp: str) -> str:
        """Sign evidence record with Ed25519."""
        message = f"{evidence_id}:{hash}:{timestamp}".encode()
        signature = self.private_key.sign(message)
        return base64.b64encode(signature).decode()
    
    def verify_signature(self, evidence_id: str, hash: str, timestamp: str, signature: str) -> bool:
        """Verify evidence signature."""
        message = f"{evidence_id}:{hash}:{timestamp}".encode()
        sig_bytes = base64.b64decode(signature)
        try:
            self.public_key.verify(sig_bytes, message)
            return True
        except:
            return False
```

---

## Recommended Implementation Order

### Phase 1: Hash Verification (CRITICAL)
1. Add pgcrypto extension to PostgreSQL
2. Create `verify_evidence_hash()` function
3. Add verification to every retrieval operation
4. Log all verification attempts

### Phase 2: Eastern Time Conversion (CRITICAL)
1. Add pendulum to Python dependencies
2. Create `timestamp_converter` tool
3. Add Eastern Time columns to evidence table
4. Update GraphQL schema with formatted timestamps

### Phase 3: SQLite WAL Parsing (CRITICAL)
1. Create `sqlite_wal_parser` tool
2. Add binary carving for fragments
3. Tag recovered messages with confidence scores
4. Integrate with Neo4j thread reconstruction

### Phase 4: Cryptographic Signing (HIGH)
1. Generate Ed25519 keypair
2. Sign all evidence records at ingestion
3. Verify signatures at retrieval
4. Store public key for court presentation

---

## Architecture Verification

### Current Pipeline (Verified)

```
DuckDB (T1) → PostgreSQL (T2) → ContextForge → [LanceDB (T3) + Neo4j/Semantica (T4)] → PostgreSQL (T2) → WunderGraph Cosmo
     │              │                  │                        │                              │
     │              │                  │                        │                              │
   Hash          UUIDv7          Tags added              Parallel                      Final storage
   Dedup       Canonical         (permissive)            processing                    with all flags
   Clock        mapping                                  with tags
```

### Additions Required

```
                    ┌─────────────────────────────────────────────────────────────────────────┐
                    │                    NEW TOOLS REQUIRED                                   │
                    ├─────────────────────────────────────────────────────────────────────────┤
                    │                                                                         │
                    │  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    │
                    │  │ hash_verifier   │    │ timestamp_      │    │ sqlite_wal_     │    │
                    │  │ (pgcrypto +     │    │ converter       │    │ parser          │    │
                    │  │  Python)        │    │ (pendulum +     │    │ (deleted msg    │    │
                    │  │                 │    │  PostgreSQL)    │    │  recovery)      │    │
                    │  └─────────────────┘    └─────────────────┘    └─────────────────┘    │
                    │                                                                         │
                    │  ┌─────────────────┐    ┌─────────────────┐                           │
                    │  │ evidence_signer │    │ entity_resolver │                           │
                    │  │ (Ed25519)       │    │ (canonical      │                           │
                    │  │                 │    │  entities)      │                           │
                    │  └─────────────────┘    └─────────────────┘                           │
                    │                                                                         │
                    └─────────────────────────────────────────────────────────────────────────┘
```

---

## Conclusion

The dial-stack architecture is fundamentally sound. The 4 critical gaps identified are:

1. **Hash recomputation** - Use pgcrypto + Python hashlib
2. **Eastern Time conversion** - Use PostgreSQL AT TIME ZONE + pendulum
3. **SQLite WAL parsing** - Add new tool for deleted message recovery
4. **Cryptographic signing** - Add Ed25519 signatures for legal admissibility

Case-level grouping is NOT needed for personal case context.

All evidence should be viewable in Eastern Time with proper DST handling, with both PostgreSQL and external library implementations for flexibility.

---

## References

- (source: SWGDE Best Practices for Digital Evidence Collection)
- (source: Cellebrite - 10 Best Practices for Digital Evidence Collection)
- (source: ConversationExtractorModule - Autopsy plugin for SMS reconstruction)
- (source: PostgreSQL Documentation - AT TIME ZONE operator)
- (source: pendulum - Python datetimes made easy)
- (source: pgcrypto - PostgreSQL cryptographic functions)
