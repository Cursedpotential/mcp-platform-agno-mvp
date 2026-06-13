---
title: Human-in-the-Loop Entity Resolution
version: 1.0.0
created: 2026-03-05 00:15
modified: 2026-03-05 00:15
author: execution@opencode
project: traceiq-forensic
status: active
---

# Human-in-the-Loop Entity Resolution

> **Before fuzzy matches are committed to memory and analyzed, a human must verify them.**

## The Problem

splink's fuzzy matching is powerful but can make mistakes:

| Match                        | Confidence | Correct? |
| ---------------------------- | ---------- | -------- |
| "KAILAH" ↔ "KYLA"              | 0.85       | ✅ Yes   |
| "Jake" ↔ "Jake from V&B"       | 0.92       | ✅ Yes   |
| "Mike" ↔ "Mike's Auto"         | 0.78       | ❌ No    |
| "Dad" ↔ "Dave"                 | 0.71       | ❌ No    |
| "Katrina" ↔ "Kate"             | 0.82       | ⚠️ Maybe |

**Incorrect matches pollute:**
- PostgreSQL sender_normalized
- Neo4j Person entities
- Semantica knowledge graph
- Evidence relationships

**Solution:** Human review before commit.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ HUMAN-IN-THE-LOOP ENTITY RESOLUTION WORKFLOW                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐   │
│  │  1. INGESTION (coordinator.ts)                                        │   │
│  │                                                                       │   │
│  │  └─ Messages → DuckDB (raw) → PostgreSQL (normalized messages)       │   │
│  │     sender = "KAILAH", "KYLA", "KAYLA" (original)                     │   │
│  │     sender_normalized = NULL (awaiting human review)                  │   │
│  └───────────────────────────────────────────────────────────────────────┘   │
│                              │                                              │
│                              ▼                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐   │
│  │  2. ENTITY RESOLUTION CANDIDATES (splink)                             │   │
│  │                                                                       │   │
│  │  splink generates candidate matches:                                  │   │
│  │                                                                       │   │
│  │  candidate_match_id | sender_a   | sender_b        | confidence      │   │
│  │  ───────────────────┼───────────┼─────────────────┼─────────────────│   │
│  │  match_001          | KAILAH    | KYLA            | 0.85            │   │
│  │  match_002          | KAILAH    | KAYLA           | 0.82            │   │
│  │  match_003          | Jake      | Jake from V&B   | 0.92            │   │
│  │  match_004          | Mike      | Mike's Auto     | 0.78 ⚠️        │   │
│  │  match_005          | Dad       | Dave            | 0.71 ⚠️        │   │
│  │                                                                       │   │
│  │  Status: PENDING (awaiting human review)                              │   │
│  │  Stored in: PostgreSQL entity_match_candidates table                  │   │
│  └───────────────────────────────────────────────────────────────────────┘   │
│                              │                                              │
│                              ▼                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐   │
│  │  3. HUMAN REVIEW (Web UI or CLI)                                      │   │
│  │                                                                       │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐   │   │
│  │  │  ENTITY RESOLUTION REVIEW                                       │   │   │
│  │  │                                                                 │   │   │
│  │  │  Candidate Match: match_001                                     │   │   │
│  │  │  ─────────────────────────────────────────────────────────────  │   │   │
│  │  │  Sender A: KAILAH                                               │   │   │
│  │  │  Sender B: KYLA                                                 │   │   │
│  │  │  Confidence: 85%                                                │   │   │
│  │  │                                                                 │   │   │
│  │  │  Context (3 sample messages):                                   │   │   │
│  │  │  • "KAILAH: Hey are you coming to the party?"                   │   │   │
│  │  │  • "KAILAH: I'll pick you up at 7"                              │   │   │
│  │  │  • "KYLA: Sounds good! See you then"                            │   │   │
│  │  │                                                                 │   │   │
│  │  │  Device sources:                                                │   │   │
│  │  │  • KAILAH: my_phone (142 messages)                              │   │   │
│  │  │  • KYLA: my_phone (38 messages)                                 │   │   │
│  │  │                                                                 │   │   │
│  │  │  [✓ APPROVE]  [✗ REJECT]  [⏭ SKIP]  [👨‍👩‍👧 MERGE INTO EXISTING]      │   │   │
│  │  └─────────────────────────────────────────────────────────────────┘   │   │
│  │                                                                       │   │
│  │  Human Decision:                                                      │   │
│  │  - approve: Merge into canonical entity                               │   │
│  │  - reject: Keep as separate entities                                  │   │
│  │  - skip: Defer decision (leave as PENDING)                            │   │
│  │  - merge_existing: Select existing entity to merge into               │   │
│  │                                                                       │   │
│  │  Status: APPROVED or REJECTED                                         │   │
│  │  Reviewed by: matt                                                    │   │
│  │  Reviewed at: 2026-03-05 00:15:00                                     │   │
│  └───────────────────────────────────────────────────────────────────────┘   │
│                              │                                              │
│                              ▼                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐   │
│  │  4. COMMIT APPROVED MATCHES                                           │   │
│  │                                                                       │   │
│  │  For each APPROVED match:                                             │   │
│  │                                                                       │   │
│  │  a) PostgreSQL: UPDATE sender_normalized                             │   │
│  │     UPDATE messaging_messages                                         │   │
│  │     SET sender_normalized = 'KAILAH'                                 │   │
│  │     WHERE sender IN ('KYLA', 'KAYLA')                                │   │
│  │                                                                       │   │
│  │  b) Neo4j: CREATE Person entity                                       │   │
│  │     MERGE (p:Person {canonical_name: 'KAILAH'})                      │   │
│  │     MERGE (v1:SenderVariant {name: 'KAILAH'})                        │   │
│  │     MERGE (v2:SenderVariant {name: 'KYLA'})                          │   │
│  │     MERGE (v3:SenderVariant {name: 'KAYLA'})                         │   │
│  │     MERGE (v2)-[:VARIANT_OF]->(p)                                     │   │
│  │     MERGE (v3)-[:VARIANT_OF]->(p)                                     │   │
│  │                                                                       │   │
│  │  c) Mark as COMMITTED in entity_match_candidates                      │   │
│  │     WHERE status = 'APPROVED'                                        │   │
│  │     SET status = 'COMMITTED'                                         │   │
│  └───────────────────────────────────────────────────────────────────────┘   │
│                              │                                              │
│                              ▼                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐   │
│  │  5. SEMANTICA (NOW RECEIVES CLEAN DATA)                               │   │
│  │                                                                       │   │
│  │  Semantica receives:                                                  │   │
│  │  - sender_normalized = "KAILAH" (canonical)                          │   │
│  │  - All variants already merged                                        │   │
│  │  - Knowledge graph has correct Person entities                        │   │
│  │                                                                       │   │
│  │  NO REPROCESSING NEEDED                                               │   │
│  └───────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Database Schema

```sql
-- PostgreSQL: Entity match candidates
CREATE TABLE entity_match_candidates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Candidate match details
    sender_a TEXT NOT NULL,           -- Original sender name
    sender_b TEXT NOT NULL,           -- Potential match
    confidence FLOAT NOT NULL,        -- splink confidence score (0-1)
    match_method TEXT NOT NULL,       -- 'jaro_winkler', 'exact', 'lemmatized'
    
    -- Context for human review
    sample_messages_a JSONB,          -- 3 sample messages from sender_a
    sample_messages_b JSONB,          -- 3 sample messages from sender_b
    device_sources JSONB,             -- {sender_a: [devices], sender_b: [devices]}
    message_counts JSONB,             -- {sender_a: count, sender_b: count}
    
    -- Human review status
    status TEXT NOT NULL DEFAULT 'PENDING',  -- PENDING, APPROVED, REJECTED, COMMITTED
    reviewed_by TEXT,                 -- User who reviewed
    reviewed_at TIMESTAMP,            -- When reviewed
    review_notes TEXT,                -- Optional notes
    
    -- Canonical entity (if approved)
    canonical_name TEXT,              -- The chosen canonical name
    merged_into UUID,                 -- If merged into existing entity
    
    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    committed_at TIMESTAMP,           -- When committed to Neo4j
    
    UNIQUE(sender_a, sender_b)        -- No duplicate candidates
);

-- Index for efficient queries
CREATE INDEX idx_match_candidates_status ON entity_match_candidates(status);
CREATE INDEX idx_match_candidates_reviewed ON entity_match_candidates(reviewed_at DESC);
```

## Implementation

### 1. Generate Candidates (Semantica Pipeline)

```python
# python-tools/entity_resolution.py

import splink
from splink import DuckDBAPI, Linker, SettingsCreator, block_on
import splink.comparison_library as cl
import pandas as pd
from typing import List, Dict, Any
import uuid

class EntityResolutionCandidates:
    """Generate entity match candidates for human review."""
    
    def __init__(self, db_api: DuckDBAPI, postgres_conn):
        self.db_api = db_api
        self.postgres = postgres_conn
        
    def generate_candidates(
        self, 
        confidence_threshold: float = 0.7
    ) -> pd.DataFrame:
        """Generate candidate matches using splink."""
        
        # Pull unique senders from PostgreSQL
        df = pd.read_sql("""
            SELECT DISTINCT sender, COUNT(*) as message_count
            FROM messaging_messages
            WHERE sender_normalized IS NULL
            GROUP BY sender
        """, self.postgres)
        
        if df.empty:
            return pd.DataFrame()
        
        # Configure splink for name matching
        settings = SettingsCreator(
            link_type="dedupe_only",
            comparisons=[
                cl.JaroWinklerAtThresholds(
                    "sender",
                    distance_thresholds=[0.9, 0.8, 0.7],
                    term_frequency_adjustments=True
                ),
            ],
            blocking_rules_to_generate_predictions=[
                block_on("first_letter"),  # Block on first letter for efficiency
            ]
        )
        
        # Run splink
        linker = Linker(df, settings, self.db_api)
        linker.training.estimate_u_using_random_sampling(max_pairs=1e6)
        linker.training.estimate_parameters_using_expectation_maximisation(
            block_on("first_letter")
        )
        
        predictions = linker.inference.predict(
            threshold_match_weight=-10
        )
        
        # Filter by confidence threshold
        candidates = predictions.as_pandas_dataframe()
        candidates = candidates[candidates['match_probability'] >= confidence_threshold]
        
        return candidates
    
    def enrich_candidates(self, candidates_df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Enrich candidates with context for human review."""
        
        enriched = []
        
        for _, row in candidates_df.iterrows():
            candidate = {
                'id': str(uuid.uuid4()),
                'sender_a': row['sender_l'],
                'sender_b': row['sender_r'],
                'confidence': row['match_probability'],
                'match_method': 'jaro_winkler',
                'status': 'PENDING',
            }
            
            # Get sample messages for context
            candidate['sample_messages_a'] = self._get_sample_messages(row['sender_l'])
            candidate['sample_messages_b'] = self._get_sample_messages(row['sender_r'])
            
            # Get device sources
            candidate['device_sources'] = self._get_device_sources(
                row['sender_l'], 
                row['sender_r']
            )
            
            # Get message counts
            candidate['message_counts'] = {
                row['sender_l']: self._get_message_count(row['sender_l']),
                row['sender_r']: self._get_message_count(row['sender_r']),
            }
            
            enriched.append(candidate)
        
        return enriched
    
    def _get_sample_messages(self, sender: str, limit: int = 3) -> List[str]:
        """Get sample messages from sender for context."""
        result = pd.read_sql("""
            SELECT body FROM messaging_messages
            WHERE sender = %s
            ORDER BY RANDOM()
            LIMIT %s
        """, self.postgres, params=[sender, limit])
        
        return result['body'].tolist() if not result.empty else []
    
    def _get_device_sources(self, sender_a: str, sender_b: str) -> Dict[str, List[str]]:
        """Get device sources for both senders."""
        result_a = pd.read_sql("""
            SELECT DISTINCT device_id FROM messaging_messages
            WHERE sender = %s
        """, self.postgres, params=[sender_a])
        
        result_b = pd.read_sql("""
            SELECT DISTINCT device_id FROM messaging_messages
            WHERE sender = %s
        """, self.postgres, params=[sender_b])
        
        return {
            sender_a: result_a['device_id'].tolist() if not result_a.empty else [],
            sender_b: result_b['device_id'].tolist() if not result_b.empty else [],
        }
    
    def _get_message_count(self, sender: str) -> int:
        """Get message count for sender."""
        result = pd.read_sql("""
            SELECT COUNT(*) as count FROM messaging_messages
            WHERE sender = %s
        """, self.postgres, params=[sender])
        
        return int(result['count'].iloc[0]) if not result.empty else 0
    
    def store_candidates(self, candidates: List[Dict[str, Any]]) -> int:
        """Store candidates in PostgreSQL for human review."""
        
        count = 0
        for candidate in candidates:
            try:
                self.postgres.execute("""
                    INSERT INTO entity_match_candidates (
                        id, sender_a, sender_b, confidence, match_method,
                        sample_messages_a, sample_messages_b, device_sources, 
                        message_counts, status
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (sender_a, sender_b) DO NOTHING
                """, (
                    candidate['id'],
                    candidate['sender_a'],
                    candidate['sender_b'],
                    candidate['confidence'],
                    candidate['match_method'],
                    candidate['sample_messages_a'],
                    candidate['sample_messages_b'],
                    candidate['device_sources'],
                    candidate['message_counts'],
                    candidate['status'],
                ))
                count += 1
            except Exception as e:
                print(f"Error storing candidate: {e}")
        
        return count


# Run pipeline
if __name__ == "__main__":
    import os
    import psycopg2
    from duckdb import DuckDBPyConnection
    import duckdb
    
    # Connect to databases
    duckdb_conn = duckdb.connect("evidence.duckdb")
    db_api = DuckDBAPI(connection=duckdb_conn)
    
    postgres_conn = psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        database=os.getenv("POSTGRES_DB", "forensic_evidence"),
        user=os.getenv("POSTGRES_USER", "evidence"),
        password=os.getenv("POSTGRES_PASSWORD", "evidence")
    )
    
    # Generate candidates
    resolver = EntityResolutionCandidates(db_api, postgres_conn)
    
    print("Generating entity match candidates...")
    candidates_df = resolver.generate_candidates(confidence_threshold=0.7)
    
    if not candidates_df.empty:
        print(f"Found {len(candidates_df)} potential matches")
        
        print("Enriching candidates with context...")
        enriched = resolver.enrich_candidates(candidates_df)
        
        print("Storing candidates for human review...")
        count = resolver.store_candidates(enriched)
        print(f"Stored {count} candidates")
    else:
        print("No candidates found")
```

### 2. Human Review (CLI)

```python
# python-tools/entity_review_cli.py

import psycopg2
from typing import Dict, Any, List
from datetime import datetime

class EntityReviewCLI:
    """CLI for human review of entity match candidates."""
    
    def __init__(self, postgres_conn, reviewer: str):
        self.postgres = postgres_conn
        self.reviewer = reviewer
        
    def get_pending_candidates(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get pending candidates for review."""
        cursor = self.postgres.cursor()
        cursor.execute("""
            SELECT id, sender_a, sender_b, confidence, match_method,
                   sample_messages_a, sample_messages_b, device_sources, 
                   message_counts
            FROM entity_match_candidates
            WHERE status = 'PENDING'
            ORDER BY confidence DESC
            LIMIT %s
        """, (limit,))
        
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    def display_candidate(self, candidate: Dict[str, Any]) -> None:
        """Display candidate for human review."""
        print("\n" + "=" * 70)
        print(f"CANDIDATE MATCH: {candidate['sender_a']} ↔ {candidate['sender_b']}")
        print("=" * 70)
        print(f"Confidence: {candidate['confidence'] * 100:.1f}%")
        print(f"Method: {candidate['match_method']}")
        print()
        
        print(f"Sender A: {candidate['sender_a']}")
        print(f"  Message count: {candidate['message_counts'][candidate['sender_a']]}")
        print(f"  Devices: {', '.join(candidate['device_sources'][candidate['sender_a']])}")
        print(f"  Sample messages:")
        for msg in candidate['sample_messages_a'][:3]:
            print(f"    • {msg[:80]}...")
        print()
        
        print(f"Sender B: {candidate['sender_b']}")
        print(f"  Message count: {candidate['message_counts'][candidate['sender_b']]}")
        print(f"  Devices: {', '.join(candidate['device_sources'][candidate['sender_b']])}")
        print(f"  Sample messages:")
        for msg in candidate['sample_messages_b'][:3]:
            print(f"    • {msg[:80]}...")
        print()
    
    def get_user_decision(self, candidate: Dict[str, Any]) -> str:
        """Get user decision for candidate."""
        self.display_candidate(candidate)
        
        while True:
            print("Options:")
            print("  [A] Approve - Merge into canonical entity")
            print("  [R] Reject  - Keep as separate entities")
            print("  [S] Skip    - Defer decision")
            print("  [C] Choose  - Specify canonical name")
            print("  [E] Edit    - Edit match")
            print()
            
            choice = input("Your decision [A/R/S/C/E]: ").strip().upper()
            
            if choice in ['A', 'R', 'S', 'C', 'E']:
                return choice
            print("Invalid choice. Please try again.")
    
    def approve_candidate(self, candidate: Dict[str, Any], canonical_name: str) -> None:
        """Approve and commit candidate."""
        cursor = self.postgres.cursor()
        
        # Update candidate status
        cursor.execute("""
            UPDATE entity_match_candidates
            SET status = 'APPROVED',
                reviewed_by = %s,
                reviewed_at = %s,
                canonical_name = %s
            WHERE id = %s
        """, (self.reviewer, datetime.now(), canonical_name, candidate['id']))
        
        self.postgres.commit()
        print(f"✓ Approved: {candidate['sender_a']} + {candidate['sender_b']} → {canonical_name}")
    
    def reject_candidate(self, candidate: Dict[str, Any], notes: str = None) -> None:
        """Reject candidate."""
        cursor = self.postgres.cursor()
        
        cursor.execute("""
            UPDATE entity_match_candidates
            SET status = 'REJECTED',
                reviewed_by = %s,
                reviewed_at = %s,
                review_notes = %s
            WHERE id = %s
        """, (self.reviewer, datetime.now(), notes, candidate['id']))
        
        self.postgres.commit()
        print(f"✗ Rejected: {candidate['sender_a']} ≠ {candidate['sender_b']}")
    
    def skip_candidate(self, candidate: Dict[str, Any]) -> None:
        """Skip candidate (leave as PENDING)."""
        print(f"⏭ Skipped: {candidate['sender_a']} ↔ {candidate['sender_b']}")
    
    def run_review_session(self) -> None:
        """Run interactive review session."""
        print("=" * 70)
        print("ENTITY RESOLUTION REVIEW")
        print(f"Reviewer: {self.reviewer}")
        print("=" * 70)
        
        while True:
            candidates = self.get_pending_candidates(limit=1)
            
            if not candidates:
                print("\nNo more pending candidates. Review session complete.")
                break
            
            candidate = candidates[0]
            decision = self.get_user_decision(candidate)
            
            if decision == 'A':
                # Approve with longer name as canonical
                canonical = max(candidate['sender_a'], candidate['sender_b'], key=len)
                self.approve_candidate(candidate, canonical)
            
            elif decision == 'R':
                notes = input("Rejection notes (optional): ").strip()
                self.reject_candidate(candidate, notes or None)
            
            elif decision == 'S':
                self.skip_candidate(candidate)
            
            elif decision == 'C':
                canonical = input("Enter canonical name: ").strip()
                if canonical:
                    self.approve_candidate(candidate, canonical)
            
            elif decision == 'E':
                print("Edit functionality coming soon...")
                continue
            
            print()


if __name__ == "__main__":
    import os
    
    # Connect to PostgreSQL
    postgres_conn = psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        database=os.getenv("POSTGRES_DB", "forensic_evidence"),
        user=os.getenv("POSTGRES_USER", "evidence"),
        password=os.getenv("POSTGRES_PASSWORD", "evidence")
    )
    
    # Create tables if not exist
    cursor = postgres_conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS entity_match_candidates (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            sender_a TEXT NOT NULL,
            sender_b TEXT NOT NULL,
            confidence FLOAT NOT NULL,
            match_method TEXT NOT NULL DEFAULT 'jaro_winkler',
            sample_messages_a JSONB,
            sample_messages_b JSONB,
            device_sources JSONB,
            message_counts JSONB,
            status TEXT NOT NULL DEFAULT 'PENDING',
            reviewed_by TEXT,
            reviewed_at TIMESTAMP,
            review_notes TEXT,
            canonical_name TEXT,
            merged_into UUID,
            created_at TIMESTAMP DEFAULT NOW(),
            committed_at TIMESTAMP,
            UNIQUE(sender_a, sender_b)
        );
        
        CREATE INDEX IF NOT EXISTS idx_match_candidates_status 
        ON entity_match_candidates(status);
    """)
    postgres_conn.commit()
    
    # Run review session
    reviewer = os.getenv("USER", "reviewer")
    cli = EntityReviewCLI(postgres_conn, reviewer)
    cli.run_review_session()
```

### 3. Commit Approved Matches (Post-Review)

```python
# python-tools/entity_commit.py

import psycopg2
from neo4j import GraphDatabase
from typing import List, Dict, Any

class EntityCommit:
    """Commit approved entity matches to PostgreSQL + Neo4j."""
    
    def __init__(self, postgres_conn, neo4j_driver):
        self.postgres = postgres_conn
        self.neo4j = neo4j_driver
        
    def get_approved_candidates(self) -> List[Dict[str, Any]]:
        """Get all approved candidates ready for commit."""
        cursor = self.postgres.cursor()
        cursor.execute("""
            SELECT id, sender_a, sender_b, canonical_name, confidence
            FROM entity_match_candidates
            WHERE status = 'APPROVED'
            ORDER BY confidence DESC
        """)
        
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    def commit_to_postgres(self, candidate: Dict[str, Any]) -> None:
        """Update sender_normalized in PostgreSQL."""
        cursor = self.postgres.cursor()
        
        cursor.execute("""
            UPDATE messaging_messages
            SET sender_normalized = %s
            WHERE sender IN (%s, %s)
        """, (
            candidate['canonical_name'],
            candidate['sender_a'],
            candidate['sender_b']
        ))
        
        rows_updated = cursor.rowcount
        self.postgres.commit()
        
        return rows_updated
    
    def commit_to_neo4j(self, candidate: Dict[str, Any]) -> None:
        """Create Person entity and variants in Neo4j."""
        with self.neo4j.session() as session:
            session.run("""
                // Create or merge canonical Person
                MERGE (p:Person {canonical_name: $canonical_name})
                SET p.last_updated = datetime()
                
                // Create variants
                WITH p
                UNWIND [$sender_a, $sender_b] as variant_name
                MERGE (v:SenderVariant {name: variant_name})
                MERGE (v)-[:VARIANT_OF]->(p)
                SET v.match_confidence = $confidence,
                    v.reviewed_at = datetime()
            """, 
                canonical_name=candidate['canonical_name'],
                sender_a=candidate['sender_a'],
                sender_b=candidate['sender_b'],
                confidence=candidate['confidence']
            )
    
    def mark_committed(self, candidate: Dict[str, Any]) -> None:
        """Mark candidate as committed."""
        cursor = self.postgres.cursor()
        cursor.execute("""
            UPDATE entity_match_candidates
            SET status = 'COMMITTED',
                committed_at = NOW()
            WHERE id = %s
        """, (candidate['id'],))
        self.postgres.commit()
    
    def run_commit(self) -> None:
        """Commit all approved candidates."""
        candidates = self.get_approved_candidates()
        
        if not candidates:
            print("No approved candidates to commit.")
            return
        
        print(f"Committing {len(candidates)} approved candidates...")
        
        for candidate in candidates:
            print(f"\nCommitting: {candidate['sender_a']} + {candidate['sender_b']} → {candidate['canonical_name']}")
            
            # Commit to PostgreSQL
            rows = self.commit_to_postgres(candidate)
            print(f"  ✓ PostgreSQL: Updated {rows} rows")
            
            # Commit to Neo4j
            self.commit_to_neo4j(candidate)
            print(f"  ✓ Neo4j: Created Person entity")
            
            # Mark as committed
            self.mark_committed(candidate)
            print(f"  ✓ Status: COMMITTED")
        
        print(f"\n✓ All {len(candidates)} candidates committed successfully!")


if __name__ == "__main__":
    import os
    
    # Connect to databases
    postgres_conn = psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        database=os.getenv("POSTGRES_DB", "forensic_evidence"),
        user=os.getenv("POSTGRES_USER", "evidence"),
        password=os.getenv("POSTGRES_PASSWORD", "evidence")
    )
    
    neo4j_driver = GraphDatabase.driver(
        os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        auth=(
            os.getenv("NEO4J_USER", "neo4j"),
            os.getenv("NEO4J_PASSWORD", "password")
        )
    )
    
    # Run commit
    committer = EntityCommit(postgres_conn, neo4j_driver)
    committer.run_commit()
    
    neo4j_driver.close()
    postgres_conn.close()
```

## Workflow Commands

```bash
# Step 1: Generate candidates (run after ingestion)
python python-tools/entity_resolution.py

# Step 2: Human review (interactive CLI)
python python-tools/entity_review_cli.py

# Step 3: Commit approved matches to PostgreSQL + Neo4j
python python-tools/entity_commit.py

# Step 4: Run Semantica (now with clean data)
python python-tools/semantica_pipeline.py
```

## Integration with Ingestion Pipeline

```python
# In coordinator.ts or separate script

# After ingestion completes, trigger entity resolution
async function postIngestionProcessing():
    # 1. Generate entity resolution candidates
    await runPythonScript("python-tools/entity_resolution.py")
    
    # 2. Notify human that review is needed
    await notifyHumanReviewReady()
    
    # 3. Wait for human review (manual step)
    # Human runs: python python-tools/entity_review_cli.py
    
    # 4. After review, commit approved matches
    await runPythonScript("python-tools/entity_commit.py")
    
    # 5. Now run Semantica with clean data
    await runPythonScript("python-tools/semantica_pipeline.py")
```

## Benefits

| Benefit | Description |
| ------- | ----------- |
| **Data Quality** | No incorrect matches polluting knowledge graph |
| **Audit Trail** | Who approved what, when, with what confidence |
| **Defer Decision** | Skip uncertain matches for later review |
| **Context** | Sample messages, device sources, counts for informed decision |
| **Reversible** | Can re-review if mistake found later |

---

*Human judgment + Machine efficiency = Clean knowledge graph.*