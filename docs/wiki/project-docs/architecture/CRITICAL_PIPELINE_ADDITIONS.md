---
title: Critical Pipeline Additions - Implementation Task
version: 1.0.0
created: 2026-03-16 19:00
modified: 2026-03-16 19:00
author: execution@opencode
project: dial-stack
status: in-progress
---

# Critical Pipeline Additions - Implementation Task

## Background

Based on best practices research (SWGDE, Cellebrite, NIST) and sequential thinking analysis, 4 critical additions were identified for the evidence pipeline. This document tracks implementation progress.

## Pipeline Context

```
DuckDB (T1) → PostgreSQL (T2) → ContextForge → [LanceDB (T3) + Neo4j/Semantica (T4)] → PostgreSQL (T2) → WunderGraph Cosmo
     │              │                  │                        │                              │                    │
   Hash         UUIDv7           Tags added              PARALLEL                    Final storage      GraphQL
   Dedup       Canonical      (metadata)              processing                   with all flags    Federation
   Clock       mapping                               (uses tags)
```

## Task 1: Hash Verification at Retrieval

### Priority: CRITICAL
### Status: PENDING

### Requirements
- Hash recomputation at every retrieval
- PostgreSQL-side verification using `pgcrypto`
- Python-side verification using `hashlib`
- Audit trail for verification attempts

### Implementation Plan

#### PostgreSQL (pgcrypto)

```sql
-- Enable pgcrypto extension
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Hash verification function
CREATE OR REPLACE FUNCTION verify_evidence_hash(
    p_evidence_id UUID,
    p_content BYTEA
) RETURNS TEXT AS $$
DECLARE
    v_stored_hash TEXT;
    v_computed_hash TEXT;
BEGIN
    -- Get stored hash
    SELECT original_hash INTO v_stored_hash
    FROM evidence WHERE id = p_evidence_id;
    
    IF v_stored_hash IS NULL THEN
        RETURN 'ERROR: Evidence not found';
    END IF;
    
    -- Compute SHA-256 hash
    v_computed_hash := encode(digest(p_content, 'sha256'), 'hex');
    
    -- Compare
    IF v_stored_hash = v_computed_hash THEN
        -- Log successful verification
        INSERT INTO hash_verification_log (evidence_id, verified_at, status)
        VALUES (p_evidence_id, NOW(), 'verified');
        RETURN 'VERIFIED';
    ELSE
        -- Log failed verification
        INSERT INTO hash_verification_log (evidence_id, verified_at, status, expected_hash, computed_hash)
        VALUES (p_evidence_id, NOW(), 'failed', v_stored_hash, v_computed_hash);
        RETURN 'FAILED: Hash mismatch';
    END IF;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
```

#### Python (hashlib)

```python
import hashlib
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel

class HashVerificationResult(BaseModel):
    """Result of hash verification."""
    evidence_id: str
    verified: bool
    stored_hash: str
    computed_hash: str
    verified_at: datetime
    algorithm: str = "sha256"

def compute_hash(content: bytes, algorithm: str = "sha256") -> str:
    """Compute hash of content."""
    h = hashlib.new(algorithm)
    h.update(content)
    return h.hexdigest()

def verify_evidence_hash(
    evidence_id: str,
    content: bytes,
    stored_hash: str,
    algorithm: str = "sha256"
) -> HashVerificationResult:
    """Verify evidence hash matches stored hash."""
    computed_hash = compute_hash(content, algorithm)
    verified = (stored_hash.lower() == computed_hash.lower())
    
    return HashVerificationResult(
        evidence_id=evidence_id,
        verified=verified,
        stored_hash=stored_hash,
        computed_hash=computed_hash,
        verified_at=datetime.now(timezone.utc),
        algorithm=algorithm
    )
```

### Files to Create/Modify
- `mcp-servers/py-mcp-server/src/tools/hash_verification.py` (NEW)
- `migrations/001_pgcrypto_hash_verification.sql` (NEW)
- `mcp-servers/py-mcp-server/src/tools/evidence_tools.py` (MODIFY - add verification calls)

---

## Task 2: Eastern Time Conversion with DST Handling

### Priority: CRITICAL
### Status: PENDING

### Requirements
- All timestamps displayed in Eastern Time (ET)
- Automatic DST detection and handling
- Both PostgreSQL and Python implementations
- Original UTC preserved

### Implementation Plan

#### PostgreSQL (AT TIME ZONE)

```sql
-- Function to convert UTC to Eastern Time with DST info
CREATE OR REPLACE FUNCTION utc_to_eastern(p_utc_timestamp TIMESTAMPTZ)
RETURNS TABLE (
    utc_timestamp TIMESTAMPTZ,
    eastern_timestamp TIMESTAMP,
    is_dst BOOLEAN,
    timezone_name TEXT
) AS $$
BEGIN
    RETURN QUERY SELECT
        p_utc_timestamp AS utc_timestamp,
        p_utc_timestamp AT TIME ZONE 'America/New_York' AS eastern_timestamp,
        EXTRACT(MONTH FROM p_utc_timestamp AT TIME ZONE 'America/New_York') IN (3, 4, 5, 6, 7, 8, 9, 10, 11) AS is_dst,
        CASE 
            WHEN EXTRACT(MONTH FROM p_utc_timestamp AT TIME ZONE 'America/New_York') BETWEEN 3 AND 11 THEN 'EDT'
            ELSE 'EST'
        END AS timezone_name;
END;
$$ LANGUAGE plpgsql STABLE;

-- View for evidence with Eastern Time
CREATE OR REPLACE VIEW evidence_with_et AS
SELECT
    e.id,
    e.original_hash,
    e.file_path,
    e.created_at AS created_at_utc,
    e.created_at AT TIME ZONE 'America/New_York' AS created_at_eastern,
    CASE 
        WHEN EXTRACT(MONTH FROM e.created_at AT TIME ZONE 'America/New_York') BETWEEN 3 AND 11 THEN 'EDT'
        ELSE 'EST'
    END AS timezone_name,
    e.contextforge_tags,
    e.verification_status
FROM evidence e;
```

#### Python (pendulum)

```python
import pendulum
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from pydantic import BaseModel

class EasternTimestamp(BaseModel):
    """Timestamp with Eastern Time conversion."""
    utc: datetime
    eastern: datetime
    eastern_str: str
    is_dst: bool
    timezone_name: str  # 'EST' or 'EDT'
    offset_hours: int

def convert_to_eastern(utc_timestamp: datetime) -> EasternTimestamp:
    """Convert UTC timestamp to Eastern Time with DST info."""
    # Ensure UTC
    if utc_timestamp.tzinfo is None:
        utc_timestamp = utc_timestamp.replace(tzinfo=timezone.utc)
    
    # Convert to Eastern
    eastern = pendulum.instance(utc_timestamp).in_timezone('America/New_York')
    
    # Determine DST
    is_dst = eastern.is_dst()
    timezone_name = 'EDT' if is_dst else 'EST'
    offset_hours = eastern.offset_hours
    
    return EasternTimestamp(
        utc=utc_timestamp,
        eastern=eastern.naive(),
        eastern_str=eastern.format('YYYY-MM-DD HH:mm:ss'),
        is_dst=is_dst,
        timezone_name=timezone_name,
        offset_hours=offset_hours
    )

def format_evidence_timestamp(utc_timestamp: datetime) -> str:
    """Format evidence timestamp for display."""
    et = convert_to_eastern(utc_timestamp)
    return f"{et.eastern_str} {et.timezone_name} (UTC{et.offset_hours:+d})"
```

### Files to Create/Modify
- `mcp-servers/py-mcp-server/src/utils/timezone_utils.py` (NEW)
- `migrations/002_eastern_time_functions.sql` (NEW)
- `mcp-servers/py-mcp-server/requirements.txt` (MODIFY - add pendulum)

---

## Task 3: SQLite WAL Parser for Deleted Message Recovery

### Priority: CRITICAL
### Status: PENDING

### Requirements
- Parse SQLite Write-Ahead Log (WAL) files
- Recover deleted SMS/messages
- Extract metadata (timestamps, parties, status)
- Chain of custody for recovered items

### Implementation Plan

#### SQLite WAL Structure

```
WAL File Header (32 bytes):
- Magic number: 0x377f0682 or 0x377f0683
- File format version
- Database page size
- Checkpoint sequence number
- Salt values

WAL Frame (24 bytes header + page data):
- Page number (4 bytes)
- Commit marker (4 bytes) - non-zero if commit frame
- Salt values (8 bytes)
- Checksum (8 bytes)
- Page content (page_size bytes)
```

#### Python Implementation

```python
import struct
from pathlib import Path
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
import hashlib

class WALFrame(BaseModel):
    """Represents a single WAL frame."""
    page_number: int
    is_commit: bool
    checksum: bytes
    page_data: bytes
    frame_offset: int

class WALHeader(BaseModel):
    """WAL file header."""
    magic: int
    format_version: int
    page_size: int
    checkpoint_seq: int
    salt1: int
    salt2: int
    checksum1: int
    checksum2: int

class DeletedMessage(BaseModel):
    """Recovered deleted message."""
    id: str  # UUID
    wal_source: str
    frame_offset: int
    recovery_timestamp: datetime
    message_data: Dict[str, Any]
    recovery_hash: str
    original_hash: Optional[str]  # If determinable

class SQLiteWALParser:
    """Parser for SQLite WAL files."""
    
    WAL_MAGIC_BE = 0x377f0682  # Big-endian
    WAL_MAGIC_LE = 0x377f0683  # Little-endian
    
    def __init__(self, wal_path: Path):
        self.wal_path = wal_path
        self.header: Optional[WALHeader] = None
        self.frames: List[WALFrame] = []
        
    def parse(self) -> List[WALFrame]:
        """Parse WAL file and extract frames."""
        with open(self.wal_path, 'rb') as f:
            self._parse_header(f)
            self._parse_frames(f)
        return self.frames
    
    def _parse_header(self, f) -> WALHeader:
        """Parse 32-byte WAL header."""
        header_data = f.read(32)
        magic = struct.unpack('>I', header_data[0:4])[0]
        
        if magic == self.WAL_MAGIC_BE:
            fmt = '>'  # Big-endian
        elif magic == self.WAL_MAGIC_LE:
            fmt = '<'  # Little-endian
        else:
            raise ValueError(f"Invalid WAL magic: {hex(magic)}")
        
        self.header = WALHeader(
            magic=magic,
            format_version=struct.unpack(f'{fmt}I', header_data[4:8])[0],
            page_size=struct.unpack(f'{fmt}I', header_data[8:12])[0],
            checkpoint_seq=struct.unpack(f'{fmt}I', header_data[12:16])[0],
            salt1=struct.unpack(f'{fmt}I', header_data[16:20])[0],
            salt2=struct.unpack(f'{fmt}I', header_data[20:24])[0],
            checksum1=struct.unpack(f'{fmt}I', header_data[24:28])[0],
            checksum2=struct.unpack(f'{fmt}I', header_data[28:32])[0]
        )
        return self.header
    
    def _parse_frames(self, f) -> List[WALFrame]:
        """Parse all WAL frames."""
        frame_header_size = 24
        frame_offset = 32  # After header
        
        while True:
            frame_header = f.read(frame_header_size)
            if len(frame_header) < frame_header_size:
                break
            
            page_number = struct.unpack('>I', frame_header[0:4])[0]
            commit_marker = struct.unpack('>I', frame_header[4:8])[0]
            checksum = frame_header[16:24]
            
            page_data = f.read(self.header.page_size)
            if len(page_data) < self.header.page_size:
                break
            
            frame = WALFrame(
                page_number=page_number,
                is_commit=(commit_marker != 0),
                checksum=checksum,
                page_data=page_data,
                frame_offset=frame_offset
            )
            self.frames.append(frame)
            frame_offset += frame_header_size + self.header.page_size
        
        return self.frames

    def recover_deleted_messages(self) -> List[DeletedMessage]:
        """Attempt to recover deleted messages from WAL frames."""
        from datetime import datetime, timezone
        import uuid
        
        recovered = []
        for frame in self.frames:
            # Parse page data for message records
            messages = self._extract_messages_from_page(frame.page_data)
            for msg_data in messages:
                recovery_hash = hashlib.sha256(frame.page_data).hexdigest()
                recovered.append(DeletedMessage(
                    id=str(uuid.uuid4()),
                    wal_source=str(self.wal_path),
                    frame_offset=frame.frame_offset,
                    recovery_timestamp=datetime.now(timezone.utc),
                    message_data=msg_data,
                    recovery_hash=recovery_hash
                ))
        return recovered
    
    def _extract_messages_from_page(self, page_data: bytes) -> List[Dict]:
        """Extract message records from page data."""
        # This is a simplified extraction - real implementation
        # would need to parse SQLite B-tree structure
        messages = []
        # TODO: Implement B-tree parsing for message table
        return messages
```

### Files to Create/Modify
- `mcp-servers/py-mcp-server/src/tools/sqlite_wal_parser.py` (NEW)
- `mcp-servers/py-mcp-server/src/tools/evidence_recovery.py` (NEW)
- `migrations/003_deleted_message_storage.sql` (NEW)

---

## Task 4: Ed25519 Cryptographic Signing

### Priority: HIGH
### Status: PENDING

### Requirements
- Sign evidence records for chain of custody
- Ed25519 signatures (fast, secure)
- Signature verification at retrieval
- Legal admissibility considerations

### Implementation Plan

#### Python (PyNaCl)

```python
from nacl.signing import SigningKey, VerifyKey
from nacl.encoding import HexEncoder
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel
import json
import hashlib

class EvidenceSignature(BaseModel):
    """Cryptographic signature for evidence."""
    evidence_id: str
    signature: str
    public_key: str
    signed_at: datetime
    signed_hash: str
    signer_id: str
    algorithm: str = "Ed25519"

class EvidenceSigner:
    """Ed25519 signer for evidence chain of custody."""
    
    def __init__(self, seed: Optional[bytes] = None):
        """Initialize signer with optional seed for deterministic keys."""
        if seed:
            self.signing_key = SigningKey(seed)
        else:
            self.signing_key = SigningKey.generate()
        self.verify_key = self.signing_key.verify_key
    
    @property
    def public_key_hex(self) -> str:
        """Get public key as hex string."""
        return self.verify_key.encode(encoder=HexEncoder).decode('utf-8')
    
    def sign_evidence(
        self,
        evidence_id: str,
        content_hash: str,
        metadata: dict,
        signer_id: str
    ) -> EvidenceSignature:
        """Sign an evidence record."""
        # Create canonical message to sign
        message = {
            'evidence_id': evidence_id,
            'content_hash': content_hash,
            'metadata': metadata,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        # Canonical JSON encoding
        message_bytes = json.dumps(message, sort_keys=True).encode('utf-8')
        message_hash = hashlib.sha256(message_bytes).hexdigest()
        
        # Sign
        signed = self.signing_key.sign(message_bytes)
        signature_hex = signed.signature.encode(encoder=HexEncoder).decode('utf-8')
        
        return EvidenceSignature(
            evidence_id=evidence_id,
            signature=signature_hex,
            public_key=self.public_key_hex,
            signed_at=datetime.now(timezone.utc),
            signed_hash=message_hash,
            signer_id=signer_id
        )
    
    @staticmethod
    def verify_signature(
        evidence_id: str,
        content_hash: str,
        metadata: dict,
        signature: EvidenceSignature
    ) -> bool:
        """Verify an evidence signature."""
        # Recreate message
        message = {
            'evidence_id': evidence_id,
            'content_hash': content_hash,
            'metadata': metadata,
            'timestamp': signature.signed_at.isoformat()
        }
        message_bytes = json.dumps(message, sort_keys=True).encode('utf-8')
        
        # Verify
        verify_key = VerifyKey(signature.public_key, encoder=HexEncoder)
        signature_bytes = bytes.fromhex(signature.signature)
        
        try:
            verify_key.verify(message_bytes, signature_bytes)
            return True
        except Exception:
            return False

class ChainOfCustody:
    """Manages chain of custody signatures."""
    
    def __init__(self, signer: EvidenceSigner):
        self.signer = signer
        self.signatures: List[EvidenceSignature] = []
    
    def record_access(
        self,
        evidence_id: str,
        content_hash: str,
        action: str,
        accessor_id: str
    ) -> EvidenceSignature:
        """Record an access event in chain of custody."""
        metadata = {
            'action': action,  # 'created', 'accessed', 'modified', 'transferred'
            'accessor_id': accessor_id
        }
        sig = self.signer.sign_evidence(evidence_id, content_hash, metadata, accessor_id)
        self.signatures.append(sig)
        return sig
    
    def verify_chain(self, evidence_id: str, content_hash: str) -> bool:
        """Verify entire chain of custody."""
        relevant_sigs = [s for s in self.signatures if s.evidence_id == evidence_id]
        
        for sig in relevant_sigs:
            if not EvidenceSigner.verify_signature(
                evidence_id, content_hash, sig.model_dump(), sig
            ):
                return False
        return True
```

### Files to Create/Modify
- `mcp-servers/py-mcp-server/src/tools/evidence_signing.py` (NEW)
- `mcp-servers/py-mcp-server/requirements.txt` (MODIFY - add pynacl)
- `migrations/004_chain_of_custody.sql` (NEW)

---

## Progress Tracking

| Task | Priority | Status | Files Created | Files Modified |
|------|----------|--------|---------------|----------------|
| Hash Verification | CRITICAL | PENDING | - | - |
| Eastern Time | CRITICAL | PENDING | - | - |
| SQLite WAL Parser | CRITICAL | PENDING | - | - |
| Ed25519 Signing | HIGH | PENDING | - | - |

## Dependencies

- PostgreSQL 14+ (for pgcrypto, AT TIME ZONE)
- Python 3.11+
- pendulum (pip install pendulum)
- pynacl (pip install pynacl)

## Next Steps

1. Create migration files for PostgreSQL functions
2. Implement Python modules
3. Add MCP tool wrappers
4. Write unit tests
5. Update documentation

---

*Created: 2026-03-16 | Author: execution@opencode | Status: In Progress*
