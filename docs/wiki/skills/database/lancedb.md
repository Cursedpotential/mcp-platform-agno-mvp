# LanceDB — Skill Reference

## Overview
- **What**: Serverless vector database for embedding similarity search. Columnar format for fast multimodal retrieval. Pass 1 output destination.
- **Version**: Latest stable (Python API via py-mcp-server)
- **Category**: Database/Vectors
- **Installed In**: Docker volume `/data/lancedb`, connected via Py MCP Server lazy singleton
- **Role**: Multimodal vault — stores 768-dimensional entity/evidence embeddings for semantic retrieval

## Architecture

LanceDB indexes all **768-dimensional vectors** from Semantica's embedding generator (all-MiniLM-L6-v2 model). It serves as:
- **Multimodal vault**: Text embeddings, image embeddings, audio transcripts (all as vectors)
- **Fast similarity search**: Cosine distance for evidence retrieval ("find similar messages")
- **Evidence linking**: Metadata tracks back to DuckDB source_hash and PostgreSQL evidence table
- **Redundancy**: Dual storage with PostgreSQL pgvector (PG is authoritative on conflicts)

## Configuration

### Environment & Connection
```
LANCEDB_PATH: /data/lancedb (Docker volume)
LANCEDB_PORT: 8082 (Py MCP Server)
```

### Docker Service
```yaml
py-mcp-server:
  build: ./py-mcp-server
  restart: always
  ports:
    - "8082:8000"
  environment:
    - LANCEDB_PATH=/data/lancedb
  volumes:
    - lancedb_data:/data/lancedb

volumes:
  lancedb_data:  # Persists across container restarts
```

## Core Schema

### Embeddings Table
```python
# From py-mcp-server/src/server.py
import lancedb

db = lancedb.connect(LANCEDB_PATH)

# Create or open embeddings table
embeddings_table = db.create_table(
    "entity_embeddings",
    data=[{
        "id": "uuid-...",
        "entity_name": "John Doe",
        "entity_type": "person",
        "embedding": [0.123, 0.456, ..., 0.789],  # 768 dimensions
        "source_hash": "sha256-...",               # Link to DuckDB
        "platform": "sms",                         # From forensic evidence
        "confidence": 0.95,                        # NER confidence
        "created_at": "2025-03-12T10:30:00Z",
        "metadata": {
            "ingestion_id": "uuid-...",
            "evidence_count": 5,
            "last_mentioned": "2025-03-12T09:15:00Z"
        }
    }],
    mode="append"  # or "overwrite" for full reindex
)

# Index strategies (default: IVF)
# For cosine similarity (embedding distance)
```

### Evidence Embeddings Table
```python
# Store evidence-level embeddings for message similarity
evidence_table = db.create_table(
    "evidence_embeddings",
    data=[{
        "id": "uuid-evidence-...",
        "source_hash": "sha256-...",           # Chain of custody link
        "platform": "sms",
        "sender": "alice@example.com",
        "timestamp": "2025-03-12T10:30:00Z",
        "embedding": [0.1, 0.2, ..., 0.9],    # 768-dim text embedding
        "text_snippet": "Message content...",
        "confidence": 0.92,                    # Extraction confidence
        "metadata": {
            "entity_ids": ["uuid-1", "uuid-2"],  # Entities mentioned
            "relations_extracted": 3,
            "conflicts_detected": 0
        }
    }],
    mode="append"
)
```

## API Patterns (Py MCP Server)

### Lazy Singleton Pattern
```python
# From py-mcp-server/src/server.py
_lancedb_conn = None

def _get_lancedb():
    global _lancedb_conn
    if _lancedb_conn is None:
        import lancedb
        _lancedb_conn = lancedb.connect(LANCEDB_PATH)
        logger.info(f"[LanceDB] Connected to {LANCEDB_PATH}")
    return _lancedb_conn
```

### Vector Search Tool
```python
@mcp.tool()
def lancedb_vector_search(
    query_embedding: list,
    table_name: str = "entity_embeddings",
    limit: int = 10,
    filters: Optional[dict] = None
) -> str:
    """
    Search for similar entities or evidence by vector similarity.

    Args:
        query_embedding: 768-dimensional query vector
        table_name: 'entity_embeddings' or 'evidence_embeddings'
        limit: Number of top-k results
        filters: Optional metadata filters {'platform': 'sms'}

    Returns:
        JSON array of results with id, similarity score, metadata
    """
    db = _get_lancedb()
    table = db.open_table(table_name)

    query = table.search(query_embedding).limit(limit)

    if filters:
        for key, value in filters.items():
            query = query.where(f"{key} == '{value}'")

    results = query.to_list()
    return json.dumps(results, indent=2, default=str)
```

### Upsert Tool (Write After Embeddings)
```python
@mcp.tool()
def lancedb_upsert(table_name: str, records: list) -> str:
    """
    Upsert embeddings after Pass 1 completion (deduplication by source_hash).

    Args:
        table_name: 'entity_embeddings' or 'evidence_embeddings'
        records: List of embedding records with source_hash for dedup

    Returns:
        Count of inserted/updated records
    """
    db = _get_lancedb()
    table = db.open_table(table_name)

    # Merge on source_hash to avoid duplicates
    # (LanceDB doesn't auto-deduplicate; must use merge strategy)
    table.add(records)

    return json.dumps({
        "inserted": len(records),
        "table": table_name,
        "total_rows": len(table.to_pandas())
    })
```

### List Collections Tool
```python
@mcp.tool()
def lancedb_list_collections() -> str:
    """List all embedding tables in LanceDB vault."""
    db = _get_lancedb()
    tables = db.table_names()
    return json.dumps({
        "collections": tables,
        "count": len(tables),
        "path": LANCEDB_PATH
    })
```

## Similarity Search Patterns

### Entity Disambiguation
```python
# Find other entities similar to a given entity
query_embedding = embeddings_from_text("John Doe")
similar = lancedb_vector_search(
    query_embedding=query_embedding,
    table_name="entity_embeddings",
    limit=5,
    filters={"entity_type": "person"}
)
# Results help identify duplicate or related entities
```

### Evidence Clustering
```python
# Find messages similar to a known coordinated message (for conspiracy detection)
evidence_query = embeddings_from_text("Meeting location agreed")
similar_evidence = lancedb_vector_search(
    query_embedding=evidence_query,
    table_name="evidence_embeddings",
    limit=20,
    filters={"platform": "sms"}
)
# Cosine distance < threshold = related messages
```

### Metadata Filtering with Similarity
```python
# Find evidence from specific sender with content similar to pattern
results = table.search(query_vec) \
    .where("sender = 'alice@example.com'") \
    .where("timestamp >= '2025-01-01'") \
    .limit(10) \
    .to_list()
```

## Known Gaps & Future Work

### Missing: Automatic Deduplication
Currently, upserting the same source_hash multiple times creates duplicates. Need:
```python
# Implement merge strategy (like PostgreSQL ON CONFLICT)
table.merge() \
    .when_matched_update_all() \
    .when_not_matched_insert_all() \
    .execute(new_records)
```

### Missing: Multimodal Media Storage
LanceDB supports image/audio embeddings, but pipeline currently only handles text:
- Need image embedding extractor (CLIP or similar)
- Need audio transcription → embedding pipeline
- Store binary paths, not raw data (too large for vector DB)

### Vector Dimension Issue
**Our vectors are 768-dimensional** (all-MiniLM-L6-v2), NOT 1536 (OpenAI). Ensure:
- All embedding generators output 768-dim
- All search queries use 768-dim vectors
- Schema validation on insert

## Integration Points

- **Semantica (Py MCP)**: `semantica_generate_embeddings()` produces 768-dim vectors → `lancedb_upsert()`
- **DuckDB**: source_hash from forensic vault → metadata linking in LanceDB records
- **PostgreSQL**: pgvector table mirrors LanceDB for redundancy; PG is authoritative on conflicts
- **DIAL Frontend**: Similarity search results feed into evidence dashboard (context retrieval)
- **Post-Analysis**: Export embeddings to downstream ML pipelines (clustering, anomaly detection)

## Common Pitfalls

- **Embedding Dimension Mismatch**: 768 ≠ 1536. Validate on every insert.
- **Metadata Cardinality**: Avoid 1000+ unique values in single field. Use IDs instead (link via source_hash).
- **Query Latency**: Cosine distance is O(n), not O(log n). Use IVF indexing for >100k records.
- **Deduplication**: No automatic uniqueness. Always track source_hash to prevent duplicates.
- **Memory Overload**: Columnar format is efficient, but 768-dim embeddings × millions of records ≈ multi-GB. Use pagination.
- **Schema Evolution**: Adding new fields requires table recreation. Plan schema upfront.

## References
- [LanceDB Documentation](https://lancedb.com/docs)
- [Vector Similarity Metrics](https://lancedb.com/docs/concepts/vector_search/)
- [Python API Reference](https://lancedb.com/docs/python/)
- [LanceDB Filtering](https://lancedb.com/docs/guides/)
- [all-MiniLM-L6-v2 Model](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2)
