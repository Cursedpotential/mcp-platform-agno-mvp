---
title: ContextForge Preliminary Scanning for Evidence Pipeline
version: 1.1.0
created: 2026-03-16 17:30
modified: 2026-03-16 17:45
author: thinking@opencode
project: dial-stack
status: draft
---

# ContextForge Preliminary Scanning for Evidence Pipeline

## The Question

Can ContextForge's existing plugins perform **preliminary scanning/tagging** to enrich evidence before it reaches our custom downstream tools?

## Short Answer

**YES** - ContextForge plugins can operate in "permissive" mode to:
1. **Detect and tag** content without blocking or modifying
2. **Add metadata** to the request/response context
3. **Pass enriched data** to downstream tools for **cross-verification**

## Two Tagging Approaches

ContextForge can tag evidence in two ways - **neither modifies the original file**:

### Approach 1: Metadata Tags (Request Context)

Tags flow through the request pipeline and get stored in PostgreSQL:

```
Evidence Upload → DuckDB (hash) → PostgreSQL (insert) → ContextForge (tag)
                                                              │
                                                              ▼
                                                    PostgreSQL (update with tags)
                                                              │
                                    ┌─────────────────────────┴─────────────────────┐
                                    ▼                                               ▼
                              LanceDB (embed)                               Neo4j (graph)
                              • Uses tags for                               • Uses tags for
                                prioritization                                 entity flags
```

**When it happens:** After PostgreSQL insert, before LanceDB/Neo4j processing

### Approach 2: Sidecar Files

Creates companion JSON files alongside originals:

```
evidence_001.pdf        ← Original (never modified)
evidence_001.pdf.json   ← Sidecar with all tags
```

**Sidecar structure:**
```json
{
  "original_hash": "sha256:abc123...",
  "uuid": "0192a1b2-c3d4-5e6f-...",
  "contextforge_tags": {
    "pii_detections": {
      "ssn": [{"match": "***-**-1234", "position": 45}],
      "email": [{"match": "t***@example.com", "position": 120}]
    },
    "content_moderation": {
      "hate": {"score": 0.85, "action": "tagged"},
      "violence": {"score": 0.12, "action": "none"}
    },
    "secrets_detected": {
      "aws_access_key_id": []
    }
  },
  "processed_at": "2026-03-16T17:45:00Z",
  "plugin_versions": {
    "pii_filter": "1.2.0",
    "content_moderation": "1.1.0"
  }
}
```

**When it happens:** Anytime - sidecar is separate from original file

---

## Recommended Pipeline Position

Per `docs/PIPELINE_DECISION.md` Option 2:

```
┌─────────────┐
│ DuckDB (T1) │  ← FIRST: Hash, dedup, master clock
│ transforms  │     - SHA-256 fingerprint
└──────┬──────┘     - Evidence integrity established
       │
       ▼
┌─────────────┐
│ PostgreSQL  │  ← SECOND: Canonical UUID mapping (UUIDv7)
│ (T2)        │     - Evidence records inserted
└──────┬──────┘     - Tags column added (empty initially)
       │
       ▼
┌─────────────────────────────────────────────────────────────────────┐
│ ContextForge Plugin Pipeline (TAGGING - no file modification)      │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │ PII Filter   │  │ Content      │  │ Secrets      │              │
│  │ (permissive) │→ │ Moderation   │→ │ Detection    │              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
│                                                                     │
│  Output: Tags stored in PostgreSQL tags column OR sidecar JSON     │
└─────────────────────────────────────────────────────────────────────┘
       │
       ├──────────────────────┐
       ▼                      ▼
┌─────────────┐        ┌─────────────┐
│ LanceDB     │        │ Neo4j (T4)  │
│ (T3)        │        │             │     ← PARALLEL
│ • Embed     │        │ • Semantica │
│ • Use tags  │        │ • Use tags  │
└─────────────┘        └─────────────┘
       │                      │
       └──────────┬───────────┘
                  ▼
        ┌─────────────────┐
        │ PostgreSQL (T2) │
        │ • ALL flags     │     ← Final storage with cross-verified tags
        │ • Cross-verify  │
        │ • Query by tags │
        └─────────────────┘
```

**Pipeline Order:**
1. **DuckDB (T1)** - Hash, dedup, master clock
2. **PostgreSQL (T2)** - UUIDv7 assigned, canonical mapping
3. **ContextForge** - Tags added (no file modification)
4. **LanceDB (T3) + Neo4j (T4)** - Parallel processing with tags available
   - **Semantica** operates within Neo4j (T4) for entity extraction
5. **PostgreSQL (T2)** - Final storage with all flags
6. **WunderGraph Cosmo (GraphQL)** - Federates all tiers for retrieval

**Key Points:**
1. **Original file NEVER modified** - ContextForge tags are metadata only
2. **Tags stored in PostgreSQL** - New column or sidecar JSON
3. **Semantica (Neo4j T4)** can use tags - Prioritize entity extraction based on flags
4. **Cross-verification** - Custom tools + ContextForge both detect, results compared
5. **GraphQL Federation** - WunderGraph Cosmo provides unified retrieval across all tiers

---

## Complete Pipeline: Ingestion → Storage → Retrieval

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        INGESTION PIPELINE                                    │
│                   (Per PIPELINE_DECISION.md Option 2)                        │
└─────────────────────────────────────────────────────────────────────────────┘

Raw Evidence
     │
     ▼
┌─────────────┐
│ DuckDB (T1) │  ← Hash, dedup, master clock
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ PostgreSQL  │  ← UUIDv7, canonical mapping
│ (T2)        │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ ContextForge Plugin Pipeline (TAGGING ONLY - no file modification)         │
│ Output: contextforge_tags stored in PostgreSQL                              │
└─────────────────────────────────────────────────────────────────────────────┘
       │
       ├──────────────────────┐
       ▼                      ▼
┌─────────────┐        ┌─────────────┐
│ LanceDB     │        │ Neo4j (T4)  │
│ (T3)        │        │             │     ← PARALLEL
│ • Embed     │        │ • Semantica │
│ • Vectors   │        │ • Entities  │
└──────┬──────┘        └──────┬──────┘
       │                      │
       └──────────┬───────────┘
                  ▼
        ┌─────────────────┐
        │ PostgreSQL (T2) │  ← Final storage with ALL flags
        └────────┬────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        RETRIEVAL LAYER                                       │
│                   WunderGraph Cosmo (GraphQL Federation)                     │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                              │
│  ┌─────────────────┐                                                         │
│  │ WunderGraph     │  ← Federated GraphQL API                                │
│  │ Cosmo Router    │    - Single endpoint for all queries                   │
│  └────────┬────────┘    - Type-safe across all tiers                        │
│           │                                                                  │
│           ├─────────────────────────────────────────────────────────────┐   │
│           │                                                             │   │
│           ▼             ▼                 ▼               ▼            │   │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐       │   │
│  │ PostgreSQL  │ │ LanceDB     │ │ Neo4j       │ │ DuckDB      │       │   │
│  │ Subgraph    │ │ Subgraph    │ │ Subgraph    │ │ Subgraph    │       │   │
│  │ (T2)        │ │ (T3)        │ │ (T4)        │ │ (T1)        │       │   │
│  │             │ │             │ │             │ │             │       │   │
│  │ • Tags      │ │ • Vectors   │ │ • Entities  │ │ • Hashes    │       │   │
│  │ • Metadata  │ │ • Semantic  │ │ • Relations │ │ • Dedup     │       │   │
│  │ • Flags     │ │   Search    │ │ • Semantica │ │ • Clock     │       │   │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘       │   │
│                                                                         │   │
└─────────────────────────────────────────────────────────────────────────────┘

Query Example:
query FindEvidenceByTags($tags: [String!]!) {
  evidence(where: {contextforge_tags: {_contains: $tags}}) {
    id
    file_path
    contextforge_tags
    custom_tool_tags
    entities {        # From Neo4j (T4) via Semantica
      name
      type
    }
    embeddings {      # From LanceDB (T3)
      similarity
    }
  }
}
```

**Retrieval Flow:**
1. Client sends GraphQL query to WunderGraph Cosmo Router
2. Router resolves query across relevant subgraphs
3. PostgreSQL subgraph returns tags, metadata, flags
4. Neo4j subgraph (Semantica) returns entities and relationships
5. LanceDB subgraph returns vectors and similarity scores
6. DuckDB subgraph returns hash verification data
7. Router assembles unified response for client

---

## PostgreSQL Schema for Cross-Verification

```sql
CREATE TABLE evidence (
    id UUID PRIMARY KEY,  -- UUIDv7 from PostgreSQL
    original_hash TEXT NOT NULL,  -- SHA-256 from DuckDB
    file_path TEXT NOT NULL,  -- Original file location (never modified)
    content_extracted TEXT,  -- Text content for analysis

    -- ContextForge tags
    contextforge_tags TEXT[],  -- ['contains_ssn', 'high_hate_score']
    contextforge_metadata JSONB,  -- Full detection details

    -- Custom tool results
    custom_tool_tags TEXT[],  -- ['pii_detected', 'hate_score_0.85']
    custom_tool_metadata JSONB,  -- Full tool results

    -- Cross-verification
    verification_status TEXT DEFAULT 'pending',  -- 'verified', 'discrepancy', 'needs_review'

    created_at TIMESTAMPTZ DEFAULT NOW(),
    processed_at TIMESTAMPTZ
);

-- Indexes for tag queries
CREATE INDEX idx_contextforge_tags ON evidence USING GIN(contextforge_tags);
CREATE INDEX idx_custom_tool_tags ON evidence USING GIN(custom_tool_tags);
CREATE INDEX idx_verification_status ON evidence(verification_status);
```

### Cross-Verification Query Examples

```sql
-- Find evidence where both ContextForge and custom tools detected PII
SELECT id, file_path, contextforge_tags, custom_tool_tags
FROM evidence
WHERE 'contains_ssn' = ANY(contextforge_tags)
  AND 'pii_detected' = ANY(custom_tool_tags);

-- Find discrepancies (ContextForge detected, custom tools didn't)
SELECT id, file_path, contextforge_tags, custom_tool_tags
FROM evidence
WHERE 'contains_ssn' = ANY(contextforge_tags)
  AND 'pii_detected' != ALL(custom_tool_tags);

-- Mark for manual review
UPDATE evidence
SET verification_status = 'needs_review'
WHERE array_length(contextforge_tags, 1) > 0
  AND verification_status = 'pending';
```

---

## How Plugin Metadata Works

### PluginResult.metadata

Every plugin hook returns a `PluginResult` with a `metadata` field:

```python
class PluginResult(BaseModel, Generic[T]):
    continue_processing: bool = True
    modified_payload: Optional[Any] = None
    violation: Optional[PluginViolation] = None
    metadata: Optional[dict[str, Any]] = None  # <-- THIS IS THE KEY
    http_headers: Optional[dict[str, str]] = None
```

### Plugin Modes

| Mode | Behavior | Use Case |
|------|----------|----------|
| `enforce` | Block on violation | Security gate |
| `permissive` | Log + add metadata, don't block | **Tagging/scanning** |
| `disabled` | Skip entirely | Bypass for specific tools |

---

## Relevant Plugins for Preliminary Scanning

### 1. PII Filter Plugin (`pii_filter`)

**What it detects:**
- SSN (US), BSN (Dutch)
- Credit cards (all major formats)
- Email addresses
- Phone numbers (US + international)
- IP addresses
- Dates of birth
- Passport numbers
- Driver's license numbers
- Bank account numbers
- Medical record numbers
- AWS keys, API keys
- Custom patterns

**Metadata output (when `include_detection_details: true`):**
```json
{
  "pii_detections": {
    "tool_pre_invoke": {
      "ssn": [
        {"match": "***-**-1234", "position": 45, "strategy": "partial"}
      ],
      "email": [
        {"match": "j***@example.com", "position": 120}
      ],
      "credit_card": []
    }
  },
  "pii_filter_stats": {
    "total_detections": 3,
    "total_masked": 2
  }
}
```

**Configuration for tagging-only mode:**
```yaml
- name: PIIFilterPlugin
  mode: "permissive"  # Log + metadata, don't block
  config:
    include_detection_details: true
    block_on_detection: false  # Never block
    default_mask_strategy: "redact"
    detect_ssn: true
    detect_email: true
    detect_phone: true
    detect_credit_card: true
    detect_aws_keys: true
```

---

### 2. Content Moderation Plugin (`content_moderation`)

**What it detects:**
- Hate speech
- Violence
- Sexual content
- Self-harm
- Harassment
- Spam
- Profanity
- Toxic content

**Providers:**
- IBM Watson NLU
- IBM Granite Guardian (local via Ollama)
- OpenAI Moderation API
- Azure Content Safety
- AWS Comprehend

**Metadata output:**
```json
{
  "content_moderation": {
    "categories": {
      "hate": {"score": 0.85, "action": "warn"},
      "violence": {"score": 0.12, "action": "none"},
      "self_harm": {"score": 0.02, "action": "none"}
    },
    "provider": "ibm_watson",
    "timestamp": "2026-03-16T17:30:00Z"
  }
}
```

**Configuration for tagging-only mode:**
```yaml
- name: ContentModerationPlugin
  mode: "permissive"
  config:
    provider: "ibm_watson"
    categories:
      hate:
        threshold: 0.7
        action: "warn"  # Not "block"
      violence:
        threshold: 0.8
        action: "warn"
      self_harm:
        threshold: 0.6
        action: "warn"
```

---

### 3. Harmful Content Detector (`harmful_content_detector`)

**What it detects:**
- Self-harm keywords
- Violence keywords
- Hate speech keywords

**Metadata output:**
```python
# From the source code:
return PromptPrehookResult(
    metadata={"harmful_categories": cats} if cats else {}
)
```

**Example metadata:**
```json
{
  "harmful_categories": ["self_harm", "violence"]
}
```

**Configuration:**
```yaml
- name: HarmfulContentDetectorPlugin
  mode: "permissive"
  config:
    block_on: []  # Don't block any category
    redact: false  # Don't modify content
```

---

### 4. Secrets Detection Plugin (`secrets_detection`)

**What it detects:**
- AWS Access Key IDs (`AKIA...`)
- AWS Secret Access Keys
- Google API keys (`AIza...`)
- Slack tokens (`xox...`)
- Private key blocks (RSA, DSA, EC, OpenSSH)
- JWT tokens
- Hex secrets (32+ chars)
- Base64 secrets (24+ chars)

**Metadata output:**
```json
{
  "secrets_detected": {
    "aws_access_key_id": [
      {"match": "AKIA...", "position": 45}
    ],
    "jwt_like": []
  },
  "secrets_count": 1
}
```

**Configuration for tagging-only:**
```yaml
- name: SecretsDetectionPlugin
  mode: "permissive"
  config:
    block_on_detection: false
    redact: false  # Don't modify, just tag
    min_findings_to_block: 999  # Never block
```

---

## How to Access Metadata in Downstream Tools

### Option 1: Context Propagation

Plugins add metadata to `PluginContext`, which flows through the request:

```
Evidence Upload → ContextForge Gateway
                        ↓
                  [Plugin Pipeline]
                  - PII Filter (permissive) → adds pii_detections
                  - Content Moderation (permissive) → adds content_moderation
                  - Secrets Detection (permissive) → adds secrets_detected
                        ↓
                  [Metadata Enriched Request]
                        ↓
                  TS MCP Server (evidence_parser)
                        ↓
                  Receives metadata in request context
```

### Option 2: Tool Wrapper

Wrap the tool call to extract metadata:

```python
# In ContextForge, after plugin processing:
async def invoke_tool_with_metadata(tool_name: str, params: dict, context: PluginContext):
    # Plugins have already run, context.metadata is populated
    enriched_params = {
        **params,
        "_plugin_metadata": context.metadata
    }
    
    # Call the actual tool
    result = await tool.invoke(enriched_params)
    
    # Tool can access:
    # - context.metadata["pii_detections"]
    # - context.metadata["content_moderation"]
    # - context.metadata["secrets_detected"]
    
    return result
```

### Option 3: Post-Invoke Hook

Use a custom plugin to route metadata to downstream tools:

```python
class MetadataRouterPlugin(Plugin):
    """Routes plugin metadata to downstream tools."""
    
    async def tool_post_invoke(self, payload: ToolPostInvokePayload) -> ToolPostInvokeResult:
        # Get all plugin metadata
        metadata = payload.context.metadata
        
        # Send to downstream processing
        if "pii_detections" in metadata:
            await self._send_to_pii_handler(metadata["pii_detections"])
        
        if "content_moderation" in metadata:
            await self._send_to_moderation_handler(metadata["content_moderation"])
        
        return ToolPostInvokeResult(continue_processing=True)
```

---

## Proposed Configuration for Evidence Pipeline

### Phase 1: Tagging-Only Mode

```yaml
# config.yaml - Preliminary scanning configuration
plugin_settings:
  parallel_execution_within_band: true
  plugin_timeout: 30
  fail_on_plugin_error: false

plugins:
  # PII Detection - Tag but don't block
  - name: PIIFilterPlugin
    kind: "plugins.pii_filter.pii_filter.PIIFilterPlugin"
    hooks: ["tool_pre_invoke"]
    mode: "permissive"
    priority: 10  # Run first
    config:
      include_detection_details: true
      block_on_detection: false
      default_mask_strategy: "redact"
      detect_ssn: true
      detect_email: true
      detect_phone: true
      detect_credit_card: true
      detect_aws_keys: true
      detect_ip_address: true

  # Content Moderation - Tag but don't block
  - name: ContentModerationPlugin
    kind: "plugins.content_moderation.content_moderation.ContentModerationPlugin"
    hooks: ["tool_pre_invoke"]
    mode: "permissive"
    priority: 20
    config:
      provider: "ibm_watson"
      categories:
        hate: {threshold: 0.6, action: "warn"}
        violence: {threshold: 0.7, action: "warn"}
        self_harm: {threshold: 0.5, action: "warn"}
        harassment: {threshold: 0.6, action: "warn"}

  # Secrets Detection - Tag but don't block
  - name: SecretsDetectionPlugin
    kind: "plugins.secrets_detection.secrets_detection.SecretsDetectionPlugin"
    hooks: ["tool_pre_invoke"]
    mode: "permissive"
    priority: 30
    config:
      block_on_detection: false
      redact: false

  # Harmful Content - Tag but don't block
  - name: HarmfulContentDetectorPlugin
    kind: "plugins.harmful_content_detector.harmful_content_detector.HarmfulContentDetectorPlugin"
    hooks: ["tool_pre_invoke"]
    mode: "permissive"
    priority: 40
    config:
      block_on: []
      redact: false
```

### Phase 2: Selective Enforcement

After preliminary tagging works, add enforcement for specific tools:

```yaml
plugins:
  # Enforce PII blocking only for public-facing tools
  - name: PIIFilterPlugin
    conditions:
      - tools: ["export_to_public", "share_evidence"]
        mode: "enforce"  # Block on these tools
      - tools: ["evidence_parser", "extract_entities"]
        mode: "permissive"  # Just tag for internal tools
```

---

## Integration with Dial-Stack Tools

### Example: Evidence Parser Enhancement

**Before (no ContextForge):**
```typescript
// TS MCP Server - evidence_parser.ts
async function parseEvidence(content: string) {
  // Parse content
  const parsed = await parse(content);
  
  // No prior knowledge of PII, secrets, etc.
  return parsed;
}
```

**After (with ContextForge metadata):**
```typescript
// TS MCP Server - evidence_parser.ts
interface PluginMetadata {
  pii_detections?: {
    ssn?: Array<{match: string, position: number}>;
    email?: Array<{match: string, position: number}>;
    credit_card?: Array<{match: string, position: number}>;
  };
  content_moderation?: {
    categories: {
      hate?: {score: number, action: string};
      violence?: {score: number, action: string};
    };
  };
  secrets_detected?: {
    aws_access_key_id?: Array<{match: string, position: number}>;
  };
}

async function parseEvidence(content: string, metadata?: PluginMetadata) {
  // Parse content
  const parsed = await parse(content);
  
  // Enrich with plugin metadata
  if (metadata) {
    parsed.tags = [];
    
    if (metadata.pii_detections?.ssn?.length) {
      parsed.tags.push("contains_ssn");
      parsed.pii_locations = metadata.pii_detections.ssn;
    }
    
    if (metadata.content_moderation?.categories?.hate?.score > 0.7) {
      parsed.tags.push("high_hate_score");
      parsed.moderation_flags = metadata.content_moderation.categories;
    }
    
    if (metadata.secrets_detected?.aws_access_key_id?.length) {
      parsed.tags.push("contains_aws_credentials");
      parsed.requires_redaction = true;
    }
  }
  
  return parsed;
}
```

---

## Benefits of Preliminary Scanning

### For Evidence Processing

| Plugin | Tag Added | Downstream Use |
|--------|-----------|----------------|
| PII Filter | `contains_ssn`, `contains_email`, `contains_phone` | Auto-redact before storage |
| Content Moderation | `high_hate_score`, `violence_detected` | Flag for human review |
| Secrets Detection | `contains_credentials`, `contains_api_keys` | Secure handling required |
| Harmful Content | `self_harm_keywords` | Priority review queue |

### For Semantica Entity Extraction

```yaml
# Semantica can use tags to prioritize entity types
plugins:
  - name: PIIFilterPlugin
    conditions:
      - tools: ["extract_entities"]
        mode: "permissive"
        config:
          # Tag entities that PII filter found
          # Semantica can use this to validate its own entity extraction
```

### For DuckDB Storage

```sql
-- Evidence table with plugin tags
CREATE TABLE evidence (
    id UUID PRIMARY KEY,
    content TEXT,
    tags TEXT[],  -- ['contains_ssn', 'high_hate_score']
    pii_locations JSONB,  -- From PII filter metadata
    moderation_scores JSONB,  -- From content moderation
    created_at TIMESTAMP
);

-- Query evidence by tags
SELECT * FROM evidence WHERE 'contains_ssn' = ANY(tags);
```

---

## Performance Considerations

### Plugin Overhead

| Plugin | Mode | Overhead | Notes |
|--------|------|----------|-------|
| PII Filter (Python) | permissive | ~5-10ms | Per request |
| PII Filter (Rust) | permissive | ~1-2ms | 5-100x faster |
| Content Moderation (AI) | permissive | ~50-200ms | Depends on provider |
| Secrets Detection | permissive | ~2-5ms | Regex-based |
| Harmful Content | permissive | ~1-3ms | Keyword-based |

### Recommended Order

1. **Fast local plugins first** (Rust PII, Secrets, Harmful Content)
2. **AI-based plugins second** (Content Moderation with Watson/Granite)
3. **Custom routing last** (MetadataRouterPlugin)

---

## Implementation Steps

### Step 1: Configure ContextForge

```bash
# Deploy ContextForge with tagging-only config
docker run -d \
  -p 4444:4444 \
  -v ./config-tagging.yaml:/app/plugins/config.yaml \
  ghcr.io/ibm/mcp-context-forge:1.0.0-RC-2
```

### Step 2: Update TS MCP Server

```typescript
// Add metadata parameter to tool signatures
export async function evidenceParser(
  content: string,
  _plugin_metadata?: PluginMetadata  // Injected by ContextForge
): Promise<ParsedEvidence> {
  // ... existing logic ...
}
```

### Step 3: Update Py MCP Server

```python
# Add metadata parameter to tool signatures
@mcp.tool()
async def extract_entities(
    content: str,
    _plugin_metadata: Optional[dict] = None  # Injected by ContextForge
) -> dict:
    # ... existing logic ...
```

### Step 4: Test Metadata Flow

```bash
# Test request through ContextForge
curl -X POST http://localhost:4444/tools/evidence_parser \
  -H "Content-Type: application/json" \
  -d '{"content": "My SSN is 123-45-6789 and my email is test@example.com"}'

# Response should include plugin metadata
```

---

## Conclusion

**Yes, ContextForge can perform preliminary scanning and tagging.**

Key points:
1. Use `mode: "permissive"` to tag without blocking
2. Set `include_detection_details: true` for rich metadata
3. Access metadata via `_plugin_metadata` parameter in tools
4. Use metadata to prioritize/route downstream processing
5. Add `tags` field to evidence records for filtering

This approach:
- **Reduces duplicate work** - PII/secrets detected once, tagged for all downstream
- **Enables prioritization** - High-risk content flagged for immediate review
- **Preserves chain of custody** - All detections logged with timestamps
- **Allows selective enforcement** - Permissive for internal, enforce for external

---

## References

- (source: ContextForge plugins/pii_filter/pii_filter.py)
- (source: ContextForge plugins/content_moderation/content_moderation.py)
- (source: ContextForge plugins/harmful_content_detector/harmful_content_detector.py)
- (source: ContextForge mcpgateway/plugins/framework/models.py)
- (context: mem0 - dial-stack ContextForge research)
