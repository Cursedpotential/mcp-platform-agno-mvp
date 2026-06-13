# Handoff Document: Sprint One Fixes Required

**Date:** February 28, 2026
**For:** Gemini (Claude Code Agent)
**Project:** MCP_Tool_Platform
**Context:** Personal forensic legal case management application
**AI Infrastructure:** API-first architecture via OpenCode API (OpenRouter) - Claude, OpenAI, Gemini subscriptions. Local GPU: Quadro M620 (2GB VRAM, CUDA capable). Google Colab for training heavy models.

---

## Executive Summary

**Status: Sprint One is ~85% complete but NOT production-ready.**

Eight specialized agents analyzed the codebase and identified critical issues that must be fixed before the application is usable. This document prioritizes fixes for a **personal application** context - focusing on stability, security exposure, and breaking issues. Scaling and enterprise features are deprioritized.

---

## Critical Issues (Fix First - Breaking/Crash Risk)

### 1. MISSING FILE: semantic_facts.ts

**Priority: P0**
**File:** `server/mcp/storage/neo4j/semantic_facts.ts`

**Problem:** The file is imported by `systemRouter.ts` but **DOES NOT EXIST**.

```typescript
// From systemRouter.ts line 21 - THIS IMPORT FAILS
import { Neo4jSemanticFactsClient, getSemanticFactsClient } from './neo4j/semantic_facts';
```

**Fix Required:**
- Create `server/mcp/storage/neo4j/semantic_facts.ts`
- Implement `Neo4jSemanticFactsClient` class with same pattern as `temporal_memory.ts`
- Export `getSemanticFactsClient()` singleton getter
- Include methods: `initialize()`, `close()`, `addFact()`, `getFact()`, `searchFacts()`

**Reference:** See `temporal_memory.ts` for implementation pattern.

---

### 2. Storage Initialization Not Wired

**Priority: P0**
**File:** `server/core/index.ts`

**Problem:** TrinityRouter is instantiated but **never initialized**. Storage tiers (DuckDB, LanceDB) exist but are not connected to the application.

**Fix Required:**
```typescript
// In server/core/index.ts, add before startServer():
import { getTrinityRouter } from '../mcp/storage/systemRouter';

async function initializeStorage() {
  const router = getTrinityRouter();
  const result = await router.initializeAll();
  if (!result.success) {
    console.error('[FATAL] Storage initialization failed:', result.errors);
    process.exit(1);
  }
  console.log('[Storage] All tiers initialized successfully');
}

// Call before starting server:
await initializeStorage();
startServer().catch(console.error);
```

---

### 3. TypeScript Compilation Errors (~50 errors)

**Priority: P0**
**Command:** `npm run check` (runs `tsc --noEmit`)

**Problem:** The project cannot compile. Main issues:
- Drizzle ORM type mismatches in auth and forensics modules
- PostgreSQL vs MySQL table type confusion
- Missing exports in `server/core/db.ts`
- CopilotKit configuration type errors

**Fix Required:**
1. Run `npm run check` to see all errors
2. Fix Drizzle ORM imports - use MySQL types consistently:
   ```typescript
   // Change from:
   import { pgTable } from 'drizzle-orm/pg-core';
   // To:
   import { mysqlTable } from 'drizzle-orm/mysql-core';
   ```
3. Fix missing exports in `db.ts`:
   ```typescript
   // Add export for test files:
   export { db, pool };
   ```
4. Fix CopilotKit types (update to latest or add type declarations)

---

## Security Issues (Fix Second - Credential Exposure)

### 4. Hardcoded Credentials in Deploy Files

**Priority: P0 (Security)**
**Files:**
- `deploy/salem-trinity/phase3-vps3-platform/.env`
- `deploy/salem-trinity/phase3-vps3-platform/docker-compose.vps3-platform.yml`

**Problem:** Real passwords, API keys, and JWT secrets committed to git.

**Fix Required:**
```bash
# 1. Immediately rotate ALL credentials
# 2. Remove from git history:
git filter-repo --path deploy/salem-trinity/phase3-vps3-platform/.env --invert-paths
# Or use BFG Repo-Cleaner

# 3. Create .env.example with placeholders:
MYSQL_ROOT_PASSWORD=REPLACE_WITH_STRONG_PASSWORD
NEO4J_PASSWORD=REPLACE_WITH_STRONG_PASSWORD
# etc.

# 4. Add .env to .gitignore (already done, verify)
```

**New credentials to generate:**
- MySQL root and user passwords
- PostgreSQL password
- Neo4j password (min 8 chars)
- JWT_SECRET (use `openssl rand -hex 32`)
- ENCRYPTION_KEY (use `openssl rand -hex 32`)
- API keys for external services

---

### 5. Weak/Placeholder Encryption Key

**Priority: P1**
**File:** `.env` (Line 22)

**Problem:**
```
ENCRYPTION_KEY=placeholder-key-replace-me-with-openssl-rand-hex-32
```

**Fix Required:**
1. Generate strong key: `openssl rand -hex 32`
2. Add validation at startup to fail if placeholder detected:
   ```typescript
   // In server/core/env.ts or startup
   if (ENV.encryptionKey?.includes('placeholder')) {
     throw new Error('FATAL: ENCRYPTION_KEY is set to placeholder value');
   }
   ```

---

### 6. Command Injection Vulnerability

**Priority: P1 (Crash Risk)**
**File:** `server/mcp/analysis/nlp-classifier.ts` (Lines 148, 198, 218)

**Problem:** User input passed directly to shell:
```typescript
const command = `python3 ${this.nlpRunnerPath} analyze_sentiment '${JSON.stringify({ text })}'`;
const { stdout } = await execAsync(command);
```

**Fix Required:**
```typescript
// Use spawn with argument array instead:
import { spawn } from 'child_process';

const result = await new Promise((resolve, reject) => {
  const proc = spawn('python3', [
    this.nlpRunnerPath,
    'analyze_sentiment',
    JSON.stringify({ text })
  ]);
  // ... handle stdout/stderr
});
```

---

### 7. SQL Injection in LanceDB Queries

**Priority: P1**
**File:** `server/mcp/storage/lancedb.ts` (Lines 223, 239, 255, 274)

**Problem:** String interpolation in SQL-like queries:
```typescript
.where(`source_hash = '${sourceHash}'`)
```

**Fix Required:**
Use parameterized queries or escape values:
```typescript
// Check if LanceDB supports parameters, or sanitize:
const escapedHash = sourceHash.replace(/'/g, "''");
.where(`source_hash = '${escapedHash}'`)
```

**Also affects:** `server/api/routers/patterns.ts` (LIKE clauses)

---

### 8. Path Traversal in Ingestion Router

**Priority: P1**
**File:** `server/api/routers/ingestion.ts` (Lines 13-25)

**Problem:** User-provided filePath used without validation:
```typescript
ingestLocalFile: protectedProcedure
  .input(z.object({ filePath: z.string() }))
  .mutation(async ({ input }) => {
    const result = await ingestEvidence(
      input.sourceType,
      fileName,
      null,
      input.filePath,  // No validation!
      { method: 'api_direct_path' }
    );
```

**Fix Required:**
```typescript
import { resolve } from 'path';

const allowedDir = resolve(process.env.EVIDENCE_DIR || './evidence');
const requestedPath = resolve(input.filePath);

if (!requestedPath.startsWith(allowedDir)) {
  throw new TRPCError({
    code: 'BAD_REQUEST',
    message: 'File path outside of allowed directory'
  });
}
```

---

### 9. CLI Bridge Authentication Bypass

**Priority: P1**
**File:** `cli-bridge/index.ts` (Lines 17-27)

**Problem:** Allows all requests if API key not set:
```typescript
if (!API_KEY) {
  console.warn("WARNING: No CLI_BRIDGE_API_KEY configured. All requests allowed.");
  return next();
}
```

**Fix Required:**
```typescript
if (!API_KEY) {
  console.error("FATAL: CLI_BRIDGE_API_KEY not configured");
  process.exit(1);
}
```

---

## Missing Dependencies (Fix Third - Runtime Errors)

### 10. Missing @microsoft/recognizers-text-suite

**Priority: P1**
**File:** `package.json`

**Problem:** `RecognizersExtractor` imports this package but it's not in dependencies.

**Fix Required:**
```bash
pnpm add @microsoft/recognizers-text-suite
```

---

### 11. Python Dependencies (API-First Architecture)

**Priority: P1**
**Files:** `server/python-tools/requirements.txt` (create if missing)

**Given your API-first setup (no local GPU):**

```
# Core API framework
fastapi>=0.100.0
uvicorn[standard]

# Lightweight NLP (CPU-only, no GPU needed)
spacy>=3.0.0
en_core_web_sm
textblob

# Utilities
pydantic
python-multipart

# Optional: If you want local embeddings (alternative to API)
# sentence-transformers  # Only if not using OpenRouter embeddings

# For Google Colab integration (optional)
# pyngrok  # For exposing Colab notebooks
```

**Note:** Heavy models (GLiNER2, BERTopic, large transformers) should run in:
- Google Colab (your training environment)
- Via API through OpenRouter
- Hugging Face Inference API

**To install spaCy model:**
```bash
python -m spacy download en_core_web_sm
```

---

## Core Functionality Issues (Fix Fourth)

### 12. Placeholder Embeddings in LanceDB

**Priority: P1**
**File:** `server/mcp/storage/systemRouter.ts` (Line 192)

**Problem:** Zero-vector placeholders:
```typescript
const embeddingVector = new Float32Array(768); // All zeros!
```

**Fix Required:**
Use OpenCode API (OpenRouter) for embeddings via your existing subscriptions:

```typescript
// Via OpenAI embedding API through OpenRouter
const response = await fetch('https://openrouter.ai/api/v1/embeddings', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${process.env.OPENCODE_API_KEY}`,
    'HTTP-Referer': 'https://mcp-tool-platform.local'
  },
  body: JSON.stringify({
    model: 'openai/text-embedding-3-small', // or text-embedding-3-large
    input: text
  })
});
const { data } = await response.json();
const embedding = data[0].embedding;
```

**Alternative options via OpenRouter:**
- `openai/text-embedding-3-small` (1536-dim, cheap)
- `openai/text-embedding-3-large` (3072-dim, more accurate)
- `cohere/embed-english-v3` (1024-dim)

**Note:** Update LanceDB schema if changing from 768-dim.

---

### 13. Mock ML in FastAPI Service

**Priority: P1**
**File:** `python-tools/main.py`

**Problem:** All endpoints return dummy data.

**Fix Required:**
Given your API-first architecture (OpenRouter for LLMs, Google Colab for training), simplify the FastAPI service to:

1. **For embeddings:** Call OpenRouter API directly from TypeScript (see fix #12 above)
2. **For NER/Classification:** Use lightweight spaCy or call APIs:

```python
# In python-tools/main.py
import spacy
from typing import Optional

# Load small model (works on CPU, no GPU needed)
nlp = spacy.load("en_core_web_sm")

@app.post("/extract_entities")
async def extract_entities(request: ExtractionRequest):
    """Lightweight NER using spaCy (local CPU)"""
    doc = nlp(request.text)
    entities = [
        {"text": ent.text, "type": ent.label_, "start": ent.start_char, "end": ent.end_char}
        for ent in doc.ents
    ]
    return {"entities": entities}

@app.post("/analyze_sentiment")
async def analyze_sentiment(request: SentimentRequest):
    """Sentiment via API or lightweight model"""
    # Option 1: Call OpenRouter for high-quality sentiment
    # Option 2: Use TextBlob or VADER (local, no GPU)
    from textblob import TextBlob
    blob = TextBlob(request.text)
    return {
        "polarity": blob.sentiment.polarity,
        "subjectivity": blob.sentiment.subjectivity
    }
```

**Dependencies to add:**
```
spacy>=3.0.0
en_core_web_sm
textblob
```

**Note:** For GLiNER2 specifically (if needed), you can:
- Run it in Google Colab and expose via ngrok
- Or use the Hugging Face Inference API
- Or use an OpenRouter model with few-shot prompting for entity extraction

---

### 14. Python Bridge Error Handling

**Priority: P2**
**File:** `server/mcp/python-bridge.ts`

**Problem:** Race conditions, no timeout handling, silent failures.

**Fix Required:**
```typescript
return new Promise((resolve, reject) => {
  let resolved = false;
  const timer = setTimeout(() => {
    if (!resolved) {
      resolved = true;
      reject(new Error('Python bridge timeout'));
    }
  }, timeout);

  proc.on("close", code => {
    if (!resolved) {
      resolved = true;
      clearTimeout(timer);
      resolve(result);
    }
  });

  proc.on("error", err => {
    if (!resolved) {
      resolved = true;
      clearTimeout(timer);
      reject(err);
    }
  });
});
```

---

## Test Coverage (Fix Fifth)

### 15. Add Critical Tests

**Priority: P2**
**Missing Test Files:**
- `server/mcp/storage/duckdb.test.ts`
- `server/mcp/storage/lancedb.test.ts`
- `server/mcp/storage/systemRouter.test.ts`
- `server/mcp/ingest/readers/SmsXmlReader.test.ts`
- `server/mcp/ingest/forensicHasher.test.ts`

**Critical Test Cases:**
```typescript
// DuckDB - Hash consistency (legal admissibility depends on this!)
it('should produce consistent SHA-256 hashes', async () => {
  const content = "test evidence";
  const hash1 = await duckdb.hashContent(content);
  const hash2 = await duckdb.hashContent(content);
  expect(hash1).toBe(hash2);
  expect(hash1).toHaveLength(64);
});

// SmsXmlReader - Blocked call detection
it('should identify blocked calls (type 5 and 6)', async () => {
  const docs = await reader.loadData(mockFilePath);
  const blocked = docs.find(d => d.metadata.call_type?.includes('blocked'));
  expect(blocked).toBeDefined();
});
```

---

## Architecture/Config Issues (Fix Last)

### 16. Drizzle Dialect Mismatch

**Priority: P2**
**Files:** `drizzle.config.ts` vs `drizzle/schema.ts`

**Problem:** Config says PostgreSQL but code uses MySQL.

**Fix Options:**
- **Option A (Recommended):** Align everything to MySQL since that's what's implemented
  ```typescript
  // drizzle.config.ts
  export default {
    dialect: 'mysql',
    // ... rest of config
  };
  ```
- **Option B:** Migrate to PostgreSQL (more work)

---

### 17. Hardcoded Defaults in Neo4j Config

**Priority: P2**
**File:** `server/mcp/plugins/graph-db.ts` (Lines 33-36)

**Problem:**
```typescript
password: process.env.NEO4J_PASSWORD || "password",
```

**Fix Required:**
```typescript
const password = process.env.NEO4J_PASSWORD;
if (!password) {
  throw new Error('NEO4J_PASSWORD environment variable is required');
}
```

---

## Summary: Fix Order

### Phase 1: Make It Run (P0)
1. Create missing `semantic_facts.ts` file
2. Wire TrinityRouter initialization in `server/core/index.ts`
3. Fix TypeScript compilation errors (`npm run check`)

### Phase 2: Secure It (P0-P1)
4. Rotate hardcoded credentials, remove from git history
5. Generate proper ENCRYPTION_KEY
6. Fix command injection in `nlp-classifier.ts`
7. Fix SQL injection in `lancedb.ts` and `patterns.ts`
8. Fix path traversal in `ingestion.ts`
9. Fix CLI bridge auth bypass

### Phase 3: Make It Work (P1)
10. Add missing `@microsoft/recognizers-text-suite` dependency
11. Add Python dependencies to requirements.txt
12. Replace placeholder embeddings with Ollama integration
13. Wire FastAPI service with real ML models

### Phase 4: Harden It (P2)
14. Fix Python bridge error handling
15. Add critical test coverage
16. Fix Drizzle dialect mismatch
17. Remove hardcoded Neo4j defaults

---

## Files to Review

All agent reports saved in `.planning/agent-reviews/`:
1. `01-sprint-one-verification.md`
2. `02-security-audit.md`
3. `03-code-evaluation.md`
4. `04-code-quality-audit.md`
5. `05-test-coverage-analysis.md`
6. `06-codebase-structure-analysis.md`
7. `07-data-engineering-assessment.md`
8. `08-ai-ml-components-analysis.md`

---

## Testing Checklist

After fixes, verify:
- [ ] `npm run check` passes with zero errors
- [ ] `npm test` passes
- [ ] Server starts and initializes all storage tiers
- [ ] Can ingest a sample XML file without errors
- [ ] SHA-256 hashes are consistent
- [ ] No hardcoded credentials in repo
- [ ] CLI bridge rejects requests without API key
- [ ] File paths outside evidence directory are rejected

---

**Note:** Skip these for now (per user request):
- n8n workflow improvements
- Scaling/performance optimizations (batch processing, caching)
- Enterprise features (rate limiting, RBAC, comprehensive audit logging)
- MLflow/Weights & Biases integration
- Local GPU setup (Ollama, CUDA, etc.)

---

## Appendix: AI Architecture for Your Setup

Given your infrastructure (OpenRouter API + Google Colab + Quadro M620 2GB):

### Recommended Approach

| Component | Implementation | Why |
|-----------|----------------|-----|
| **Embeddings** | OpenRouter API (OpenAI/Cohere) | 1536-3072 dim, high quality, pay-per-use |
| **NER** | spaCy `en_core_web_sm` | Local CPU/GPU, fast, no API latency |
| **Sentiment** | TextBlob or API | TextBlob is local; API is higher quality |
| **Classification** | OpenRouter API | GPT-4o-mini or Claude Haiku via OpenRouter |
| **Heavy ML** | Google Colab | Training, GLiNER2, BERTopic when needed |
| **Vector DB** | LanceDB | Already implemented, stores API embeddings |
| **Fallback** | Quadro M620 (2GB) | Small models if API down (limited by VRAM) |

### OpenRouter Setup

**Environment variables:**
```bash
OPENCODE_API_KEY=your_openrouter_key
OPENCODE_MODEL=gpt-4o-mini  # or claude-3-haiku, gemini-pro, etc.
```

**Embedding endpoint:**
```bash
POST https://openrouter.ai/api/v1/embeddings
Authorization: Bearer $OPENCODE_API_KEY
```

### Simplified Python Service

Since you're API-first, the Python bridge can be minimal:
- spaCy for fast local NER
- Pass-through to APIs for heavy lifting
- Google Colab webhook for training jobs

This eliminates:
- Large model downloads (2GB VRAM can't fit most transformer models)
- Complex local ML setup

### Quadro M620 (2GB) Limitations

Your GPU can accelerate:
- ✅ spaCy (small speedup for NER)
- ✅ Small embedding models (if you want local fallback)

Cannot run (insufficient VRAM):
- ❌ GLiNER2 (needs ~4GB+)
- ❌ Large transformer models (BERT, GPT, etc.)
- ❌ Ollama with most models (2GB too small)

**Recommendation:** Keep the API-first approach. Use the Quadro only for:
- spaCy acceleration (optional)
- Local fallback if internet down (very limited)
- Google Colab is better for any real training