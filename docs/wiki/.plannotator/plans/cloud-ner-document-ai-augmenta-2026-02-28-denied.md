
# Cloud NER & Document AI Augmentation Plan

## Philosophy: Local-First, Cloud-Augmented

Same pattern as your embeddings strategy: **GLiNER2 runs locally by default at $0 cost**. Cloud providers are opt-in augmentation for when you need higher accuracy, PII detection, document OCR, or emotion analysis.

---

## 1. Cloud NER Provider Comparison

| Criterion | Google Cloud NL API | Amazon Comprehend | IBM Watson NLU |
|-----------|-------------------|-------------------|----------------|
| **Free tier** | 5K units/mo (12 mo) | 50K units/mo (12 mo) | 30K items/mo (always) |
| **Paid pricing** | ~$1-2/1K units | $1/10K units (cheapest) | $0.003/item (10K chars) |
| **Entity types** | 12 fixed (PERSON, LOC, ORG, EVENT, DATE, NUMBER, ADDRESS, PHONE, PRICE, WORK_OF_ART, CONSUMER_GOOD, OTHER) | 9 fixed (PERSON, LOCATION, ORG, DATE, EVENT, QUANTITY, TITLE, COMMERCIAL_ITEM, OTHER) | Entities + concepts + semantic roles + emotion |
| **Custom entity types** | ❌ No (AutoML deprecated) | ✅ Yes (Custom Comprehend, $3/hr training) | ✅ Yes (Watson Knowledge Studio) |
| **PII detection** | ❌ No dedicated | ✅ Yes ($0.000002/unit — nearly free) | ❌ No dedicated |
| **Sentiment/Emotion** | Sentiment only | Sentiment + targeted sentiment | Sentiment + 5 emotions (sadness, joy, fear, disgust, anger) |
| **Semantic roles** | ❌ | ❌ | ✅ Subject-Action-Object |
| **Node.js SDK** | ✅ `@google-cloud/language` | ✅ `@aws-sdk/client-comprehend` | ✅ `ibm-watson` |
| **Batch processing** | ✅ | ✅ BatchDetectEntities | ✅ |
| **HIPAA** | ✅ (with BAA) | ✅ (with BAA) | ✅ Built-in |
| **Confidence scores** | ✅ probability (0-1) | ✅ score (0-1) | ✅ confidence |
| **Character offsets** | ✅ beginOffset | ✅ BeginOffset + EndOffset | ✅ |

### Winner by Use Case:
- **Cheapest NER augmentation:** Amazon Comprehend ($1/10K requests)
- **Best free tier:** Amazon Comprehend (50K units/mo, 12 months)
- **Best always-free:** IBM Watson NLU (30K items/mo, no expiry)
- **PII detection:** Amazon Comprehend (nearly free, dedicated API)
- **Emotion analysis:** IBM Watson NLU (5 discrete emotions — critical for custody docs)
- **Structured addresses:** Google Cloud NL API (parses street, city, state, zip)
- **Overall best fit for custody:** IBM Watson NLU — emotion + semantic roles + custom entities + always-free tier + HIPAA

---

## 2. Document AI Provider Comparison

| Criterion | Google Document AI | Amazon Textract |
|-----------|-------------------|-----------------|
| **What it does** | OCR + layout + entity extraction + classification | OCR + forms + tables |
| **Free tier** | ~1K pages/mo OCR | 1K pages/mo OCR (3 months only) |
| **OCR pricing** | $1.50/1K pages | $1.50/1K pages |
| **Layout parsing** | ✅ Layout Parser — context-aware chunks for RAG | ❌ No layout parser |
| **Supported formats** | PDF, HTML, DOCX, PPTX, XLSX | PDF, JPEG, PNG, TIFF only |
| **Custom extraction** | ✅ Gemini-powered (~$65/1K pages, expensive) | ❌ Queries only |
| **Form parsing** | ✅ Key-value, checkboxes, tables + basic NER | ✅ Key-value, tables |
| **Node.js SDK** | ✅ `@google-cloud/documentai` | ✅ `@aws-sdk/client-textract` |
| **Best for** | Document → structured chunks → feed to NER | Scanned PDFs → text extraction |

### Winner: Google Document AI
- **Layout Parser** is the killer feature — it creates context-aware chunks from PDFs/DOCX that are perfect for feeding into GLiNER2
- Supports DOCX (custody documents are often Word files)
- Same Google Cloud account as NL API (single billing)
- **Do NOT use Custom Extractor** — that's Gemini LLM extraction at $65/1K pages. GLiNER2 does this at $0.

---

## 3. Proposed Architecture: Configurable NER Pipeline

### Layer 1: Document Processing (optional, for scanned/complex docs)

```
Scanned PDF / Complex DOCX / Image
    │
    ├── Google Document AI Layout Parser (cloud, opt-in)
    │   └─ Context-aware chunks, tables, structure
    │
    └── Amazon Textract (cloud, alt provider)
        └─ Text extraction from scanned PDFs
    │
    ▼
Clean text chunks (ready for NER)
```

### Layer 2: Entity Extraction (local-first)

```
Clean text
    │
    ├── GLiNER2 (LOCAL, default, $0) ← PRIMARY
    │   ├─ Semantic: person, communication, event, location, org, legal_proceeding
    │   ├─ Relations: communicated_with, custody_of, lives_in
    │   ├─ Classification: sentiment, intent, urgency
    │   └─ Confidence scores + character spans
    │
    ├── Recognizers-Text (LOCAL, Node.js native, $0)
    │   ├─ DateTime: "March 15, 2024", "next Tuesday"
    │   ├─ Currency: "$2,500", "$15,000/month"
    │   ├─ Phone numbers, emails, URLs
    │   └─ Numbers, percentages
    │
    ▼
Merged local entities (deduplicated by character span overlap)
```

### Layer 3: Cloud Augmentation (opt-in, configurable)

```
Same text (sent only if cloud NER enabled)
    │
    ├── Amazon Comprehend (cheap NER + PII)
    │   ├─ Cross-validate PERSON, LOCATION, ORG, DATE entities
    │   ├─ PII detection ($0.000002/unit — flag SSNs, account numbers)
    │   └─ Targeted sentiment per entity
    │
    ├── Google Cloud NL API (address parsing)
    │   ├─ Structured ADDRESS extraction (street, city, state, zip)
    │   └─ Cross-validate entities with salience scores
    │
    ├── IBM Watson NLU (emotion + semantic roles)
    │   ├─ Emotion analysis: sadness, joy, fear, disgust, anger
    │   ├─ Semantic roles: subject → action → object
    │   └─ Concepts extraction (abstract topics)
    │
    ▼
Enriched entities (local + cloud merged)
```

### Layer 4: Validation & Storage (always runs)

```
Enriched entities
    │
    ├── Semantica (validation + provenance)
    │   ├─ Validate against existing graph
    │   ├─ W3C PROV-O provenance tracking
    │   ├─ Conflict detection
    │   └─ Write validated → Neo4j semantic_facts
    │
    └── Human-in-the-loop (Rule #8)
        └─ Surface conflicts for user resolution
```

---

## 4. Configuration Design

```typescript
// In environment config (same pattern as embeddings)
interface NERConfig {
  // Layer 1: Document Processing
  documentAI: {
    provider: 'none' | 'google-docai' | 'amazon-textract';
    // 'none' = text already clean, skip OCR/layout
  };

  // Layer 2: Local NER (always on)
  local: {
    gliner2: { enabled: true; model: 'fastino/gliner2-base-v1' | 'fastino/gliner2-large-v1' };
    recognizersText: { enabled: true };
  };

  // Layer 3: Cloud Augmentation (opt-in)
  cloudNER: {
    provider: 'none' | 'amazon-comprehend' | 'google-nl' | 'ibm-watson' | 'all';
    piiDetection: { enabled: boolean; provider: 'amazon-comprehend' }; // dedicated
    emotionAnalysis: { enabled: boolean; provider: 'ibm-watson' };    // dedicated
    addressParsing: { enabled: boolean; provider: 'google-nl' };      // dedicated
  };

  // Confidence thresholds
  thresholds: {
    localMinConfidence: 0.7;          // GLiNER2 entity minimum
    cloudCrossValidation: boolean;     // Require cloud agreement to promote confidence
    humanReviewBelow: 0.5;            // Send to HITL below this
  };
}
```

---

## 5. Cost Analysis

### Scenario: 1,000 custody documents/month (~550 chars avg)

| Component | Monthly Cost | Notes |
|-----------|-------------|-------|
| GLiNER2 (local) | $0 | CPU, no API calls |
| Recognizers-Text (local) | $0 | Node.js, no API calls |
| Semantica (local) | $0 | Local Python service |
| **Local total** | **$0** | |
| + Amazon Comprehend NER | ~$6 | 60K units × $0.0001 |
| + Amazon Comprehend PII | ~$0.12 | 60K units × $0.000002 |
| + Google NL API entities | ~$60-120 | 60K units × $0.001-0.002 |
| + IBM Watson NLU | ~$18 | 6K items × $0.003 |
| **All cloud total** | **~$84-144** | |
| **Recommended combo** | **~$6.12** | Comprehend NER + PII only |

### vs. Original MS GraphRAG LLM Extraction
- LLM entity extraction: ~$50-200/month for same volume
- GLiNER2 replaces this at $0
- Cloud augmentation is OPTIONAL and cheap ($6/mo for Comprehend)

---

## 6. Recommendation: Tiered Approach

### Tier 0 — MVP (Phase 1-2 of integration plan)
- GLiNER2 (local, $0) — primary NER
- Recognizers-Text (local, $0) — structured entities
- Semantica (local, $0) — validation/provenance
- **Cost: $0/month**

### Tier 1 — Add PII Detection (Phase 3)
- Everything in Tier 0
- + Amazon Comprehend PII detection ($0.12/mo)
- **Why:** SSNs, account numbers in custody docs must be flagged
- **Cost: ~$0.12/month**

### Tier 2 — Add Emotion Analysis (Phase 4)
- Everything in Tier 1
- + IBM Watson NLU emotion analysis ($0 for 30K items/mo free tier)
- **Why:** Detecting anger, fear, sadness in communications is CRITICAL for custody
- **Cost: $0/month (free tier)**

### Tier 3 — Full Cloud Augmentation (Phase 5+)
- Everything in Tier 2
- + Amazon Comprehend NER for cross-validation ($6/mo)
- + Google Document AI Layout Parser (for scanned PDFs)
- + Google NL API for address parsing (if needed)
- **Cost: ~$10-30/month**

### IBM Watson NLU for Custody — Why It Matters

Watson's emotion analysis returns 5 discrete emotions with scores per text segment:
```json
{
  "emotion": {
    "sadness": 0.82,
    "anger": 0.65,
    "fear": 0.31,
    "joy": 0.02,
    "disgust": 0.15
  }
}
```

For a custody application, this is GOLD:
- High anger + high fear in text messages → possible intimidation pattern
- Consistent sadness in child communications → emotional impact evidence
- Semantic roles ("He THREATENED to take the kids") → subject-action-object extraction
- Maps directly to MCL 722.23 Factor (j) — domestic violence indicators

---

## 7. Files to Update (if approved)

1. **`.planning/INTEGRATION_PLAN.md`** — Add Cloud NER section to revised plan
2. **`.planning/research/STACK.md`** — Add cloud NER providers to stack options
3. **`docs/ARCHITECTURE_SSOT.md`** — Add configurable NER pipeline to architecture
4. **New: `server/mcp/ner/config.ts`** — NER configuration types (future implementation)
5. **New: `server/mcp/ner/providers/`** — Provider adapters (future implementation)

---

## 8. Open Questions for You

1. **Do you have existing Google Cloud / AWS / IBM Cloud accounts?** (affects which free tiers are available)
2. **Is IBM Watson NLU emotion analysis a "must-have" or "nice-to-have"?** (I think it's critical for custody)
3. **Should Document AI (Google) be part of MVP or deferred?** (depends on whether you're processing scanned PDFs now)
4. **PII detection priority?** (Comprehend PII at $0.12/mo seems like a no-brainer)


---

# Plan Feedback

I've reviewed this plan and have 1 piece of feedback:

## 1. General feedback about the plan
> docling and docstrsange for ocr and docs, with textrasct as fall back, and for ner locl with ibm for more adnaced or failback keep textract and recognition wired in fior alts or specific taks (screenshota of messages)

---
