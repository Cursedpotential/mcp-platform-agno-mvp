# Skill: Code Extraction

## Purpose
Extract code snippets, architecture decisions, and development context
from conversation segments.

## When to Use
- After topic segmentation identifies a `development` chunk
- Porting tools from alpha to current platform
- Rebuilding code that was discussed but not saved
- Documenting architecture decisions

## What to Extract

### 1. Code Snippets
Already extracted by the artifact extractor. Look for:
- Complete functions/classes
- Configuration blocks
- Database schemas
- API endpoint definitions
- Dockerfile/compose configurations

### 2. Architecture Decisions
Look for: design choices, trade-offs, reasoning
- "We chose DuckDB over PostgreSQL for the vault because..."
- "Modular MCP servers per language to avoid interop hell"
- "SHA-256 at first touch for chain of custody"

### 3. Goals and TODOs
Look for: stated objectives, pending tasks
- "Need to port the Facebook parser"
- "Add test coverage for SMS ingestion"
- "Wire the iMessage PDF parser"

### 4. Blockers
Look for: issues, errors, dependencies
- "Neo4j connection timeout on large graphs"
- "Parser fails on iOS 17+ exports"
- "Blocked: waiting for embedding model decision"

### 5. Design Patterns
Look for: reusable approaches, conventions
- "MCPTools(command=...) for stdio transport"
- "Agent instructions as sacred — define capabilities there"
- "PostgreSQL + pgvector for operational state"

## How to Use

Send `development` segments to the cheapest/fastest model:

```python
# Via Groq (fast, cheap)
from chatminer.segmenters import get_segmenter

# Use Groq for dev extraction (cost-effective)
segmenter = ConfigurableSegmenter(provider="groq")
```

Or manually with the artifact extractor:
```python
from chatminer.core.artifacts import extract_artifacts

dev_segments = [s for s in segments if s.topic_tag.value == "development"]
for seg in dev_segments:
    artifacts = extract_artifacts(seg.messages)
    code = [a for a in artifacts if a.artifact_type.value == "code_snippet"]
    for c in code:
        print(f"{c.language}: {c.title}")
        print(c.content)
```

## Storage
Code artifacts are stored in:
- `transcript_insight` table (type: code_artifact)
- `learned_knowledge` table (durable patterns)
- `evidence_artifacts` table (for code used as evidence)
