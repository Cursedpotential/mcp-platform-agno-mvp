# AI/ML Components Analysis Report

**Agent:** AI/ML Components Review
**Date:** February 28, 2026
**Project:** MCP_Tool_Platform

---

## Executive Summary

**Infrastructure Context:**
- Quadro M620 2GB VRAM (CUDA capable but limited)
- OpenRouter API (OpenCode) for LLMs/embeddings (Claude, OpenAI, Gemini subscriptions)
- Google Colab for training heavy models
- Light local processing only (2GB VRAM constraint)

The MCP_Tool_Platform implements a **Two-Pass Enrichment** model for forensic analysis:
- **Pass 1:** Captures immediate context (24-hour window, immutable)
- **Pass 2:** Provides longitudinal hindsight for pattern detection including gaslighting

**Status: Placeholder implementations dominate the ML pipeline**

**Recommendation:** Switch to API-first architecture using OpenRouter for embeddings and heavy NLP, lightweight spaCy for local NER.

---

## ML Model Stack

### NLP Models

| Model | Purpose | Status |
|-------|---------|--------|
| **spaCy** (`en_core_web_sm`/`en_core_web_trf`) | Named Entity Recognition, sentence segmentation | Active |
| **GLiNER** (`fastino/gliner2-base-v1`) | Zero-shot entity extraction for legal domain | Active |
| **BERTopic** + **Sentence-Transformers** | Topic detection and clustering | Active |
| **langdetect** | Language detection with confidence scoring | Active |

### Embedding Models

| Model | Dimensions | Purpose | Status |
|-------|------------|---------|--------|
| **OpenRouter** (OpenAI/Cohere) | 1536-3072-dim | Primary embeddings via API | Recommended |
| **Ollama** (`nomic-embed-text`) | 768-dim | Local fallback | Won't fit on 2GB GPU |
| **sentence-transformers** (`all-MiniLM-L6-v2`) | 384-dim | Local CPU fallback | Possible on Quadro |

### Graph/Temporal ML

| Component | Purpose | Status |
|-----------|---------|--------|
| **Graphiti** (Zep AI) | Temporal knowledge graphs with episodic memory | ~40% |
| **Neo4j** | Dual database (semantic_facts + temporal_memory) | ~40% |
| **Microsoft GraphRAG** | Community detection (Pass 2) | Planned |

---

## Critical ML Issues

### 1. Placeholder Embeddings (HIGH)

**File:** `server/mcp/storage/systemRouter.ts` (Line 192)

**Issue:** Zero-vector placeholders instead of real embeddings:
```typescript
const embeddingVector = new Float32Array(768); // Placeholder, real embedding in Pass 1
```

**Impact:** Vector search will not work

**Fix:** Replace with actual Ollama calls for embedding generation

---

### 2. Mock ML in FastAPI (HIGH)

**File:** `python-tools/main.py`

**Issue:** All endpoints return dummy data:
```python
@app.post("/analyze")
async def analyze(request: AnalysisRequest):
    return {
        "entities": [{"text": "Mock Entity", "type": "PERSON", "confidence": 0.95}],
        "sentiment": {"label": "POSITIVE", "score": 0.8}
    }
```

**Impact:** No actual ML processing occurring

**Fix:** Implement real model loading and inference

---

### 3. No Model Versioning (MEDIUM)

**Location:** All Python files

**Issue:** No tracking of model versions or experiment tracking

**Missing:**
- Model version tracking
- Experiment logging (MLflow, Weights & Biases)
- Performance metrics collection
- A/B testing framework

---

### 4. No Batch Processing (MEDIUM)

**File:** `server/python-tools/nlp_runner.py`

**Issue:** Single-item processing only:
```python
# Current: Single text processing
def extract_entities(text: str, types: List[str] = None):
    doc = get_spacy()(text)
    # ... process single doc
```

**Impact:** GPU underutilization, slow processing

**Fix:** Implement batch inference for embeddings and entity extraction

---

### 5. No Embedding Cache (MEDIUM)

**Issue:** Same texts re-embedded repeatedly

**Fix:** Add Redis or in-memory LRU cache for embeddings

---

### 6. Hardcoded Thresholds (LOW)

**File:** `server/python-tools/enrichment/gliner_extractor.py` (Line 40)

**Issue:** `threshold=0.5` not configurable

---

## Data Pipelines & Preprocessing

### Ingestion Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    INGESTION PIPELINE                            │
├─────────────────────────────────────────────────────────────────┤
│  1. SOURCE → DuckDB (SHA-256 at first touch)                    │
│     - SmsXmlReader: Parse SMS/iMessage XML exports              │
│                                                                  │
│  2. PASS 1 ENRICHMENT (24-hour window)                          │
│     ├─ BehavioralFlagExtractor: Pattern matching (303 patterns) │
│     ├─ GlinerExtractor: Named entity extraction                 │
│     ├─ RecognizersExtractor: Dates, currencies, phones          │
│     └─ Sentiment/Intent classification                          │
│                                                                  │
│  3. STORAGE → LanceDB (Multimodal Vault)                        │
│     ├─ Embeddings: 768-dim vectors                              │
│     ├─ Raw binaries: Images, PDFs, audio                        │
│     └─ Metadata: Chain of custody links                         │
│                                                                  │
│  4. PASS 2 ENRICHMENT (Longitudinal) - PLANNED                  │
│     ├─ GraphRAG: Community detection                            │
│     ├─ Graphiti: Contradiction detection                        │
│     └─ Pattern evolution analysis                               │
└─────────────────────────────────────────────────────────────────┘
```

### Two-Pass Enrichment Model

**Pass 1 (Blind Classification):**
- Uses only 24-hour context window
- Captures sentiment, intent, entities
- Real embeddings via Ollama (planned)
- **Immutable** — locked with SHA-256 reference
- Represents "how it felt at the time"

**Pass 2 (Hindsight Synthesis):**
- Longitudinal analysis (months/years)
- Microsoft GraphRAG community detection
- Graphiti contradiction detection
- Creates CONTRADICTS edges in Neo4j
- Represents patterns invisible to original participants
- Critical for gaslighting detection

---

## Python Bridge Patterns

### Current: Subprocess-Based

**File:** `server/mcp/python-bridge.ts`

```typescript
const result = await callPython("extract_entities", { text, types });
```

**Pros:**
- Isolation from Node.js process
- Access to full Python ML ecosystem
- Graceful degradation with JS fallbacks

**Cons:**
- Process spawn overhead
- JSON serialization bottleneck
- No shared memory

### Planned: FastAPI Service

**File:** `python-tools/main.py`

- Unified Python service via HTTP
- Models loaded once at startup
- Async endpoints for all ML operations

**Status:** Placeholder implementation — models commented out

---

## GPU Constraints (Quadro M620 2GB)

**What fits:**
- ✅ spaCy `en_core_web_sm` (small speedup over CPU)
- ✅ TextBlob/VADER (already fast on CPU)
- ✅ Very small sentence-transformers (384-dim, ~100MB)

**What doesn't fit (insufficient VRAM):**
- ❌ GLiNER2 (~4GB required)
- ❌ BERTopic (~2-4GB required)
- ❌ Ollama with standard models (3-8GB typical)
- ❌ Large embeddings (768+ dim at scale)

**Recommendation:** Use the Quadro for:
1. spaCy acceleration (modest gain)
2. Local fallback only if API unavailable (very limited)
3. Stick to API-first for production workloads

## Performance Bottlenecks

| Bottleneck | Impact | Mitigation |
|------------|--------|------------|
| Process spawn per call | High latency | Use FastAPI service |
| JSON serialization | Memory/CPU overhead | Use Arrow/Protobuf |
| No batching | API rate limit hit | Batch when possible |
| No caching | Redundant API calls | Add embedding cache |
| API latency | 100-500ms per call | Cache frequent embeddings |

---

## Key Files

**Python Bridge:**
- `server/mcp/python-bridge.ts` - TypeScript bridge
- `python-tools/main.py` - FastAPI service (placeholder)
- `server/python-tools/nlp_runner.py` - Main NLP interface
- `server/python-tools/topic_detector.py` - BERTopic clustering
- `server/python-tools/graphiti_runner.py` - Temporal graphs

**Extractors:**
- `server/python-tools/enrichment/gliner_extractor.py` - NER extraction
- `server/mcp/ingest/extractors/GlinerExtractor.ts` - TS bridge
- `server/mcp/ingest/extractors/BehavioralFlagExtractor.ts` - Pattern detection
- `server/mcp/ingest/extractors/RecognizersExtractor.ts` - Structured data

**Documentation:**
- `STORAGE_ARCHITECTURE.md` - 5-tier architecture
- `REQUIREMENTS.md` - 53 detailed requirements

---

## Recommendations

**Context:** User has no local GPU, uses OpenRouter API (OpenCode) for LLMs/embeddings, and Google Colab for training.

### Immediate (P0)

1. **Replace placeholder embeddings**
   - Use OpenRouter API (OpenAI text-embedding-3-small/large)
   - Update LanceDB schema for 1536 or 3072 dimensions
   - Remove zero-vector placeholders

2. **Implement lightweight FastAPI service**
   - Use spaCy `en_core_web_sm` for local NER (CPU-only)
   - Use TextBlob for local sentiment
   - Route heavy tasks to OpenRouter API
   - Add health check endpoint

3. **Remove unnecessary ML dependencies**
   - Skip GLiNER2 local setup (use API or Colab)
   - Skip sentence-transformers (use API embeddings)
   - Skip BERTopic (use Colab for topic modeling)

### Short-term (P1)

4. **Add embedding caching**
   - Simple in-memory LRU cache (hash → embedding)
   - Avoid re-embedding identical text

5. **Fix Python bridge error handling**
   - Add proper logging and retry logic
   - Add timeout handling

6. **Create Colab integration**
   - Webhook endpoint for Colab job results
   - Ngrok tunnel for local testing

### Long-term (P2)

7. **Optimize costs**
   - Track API usage per operation
   - Consider batching for OpenRouter when possible
   - Cache embeddings in LanceDB to avoid re-embedding

---

## Summary

The MCP_Tool_Platform demonstrates **sophisticated architectural thinking** for forensic AI/ML with its two-pass enrichment model and chain of custody design.

**However, the current implementation has significant gaps:**

1. **Placeholder implementations** dominate the ML pipeline
2. **No experiment tracking** or model versioning
3. **Suboptimal inference performance** due to subprocess architecture
4. **Missing n8n AI workflows** for automation
5. **Incomplete error handling** in ML pipelines

The foundation is solid, but the ML components need substantial work to reach production readiness.