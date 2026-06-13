# MCP Tool Catalog

This document defines all tools exposed by the MCP Tool Shop server. Each tool is designed to be called by LLMs, agents, or other platforms.

## Tool Design Principles

1. **Atomic Operations** - Each tool does ONE thing well
2. **Clear Input Schema** - JSON Schema for all parameters
3. **Structured Output** - Consistent, parseable JSON responses
4. **Composable** - Tools can be chained by calling agents
5. **Confidence Scores** - All extractions include confidence metrics
6. **Error Handling** - Warnings and errors in standardized format

---

## Tool Categories

### 1. OCR Tools (`ocr.*`)

| Tool                      | Description                         |
| ------------------------- | ----------------------------------- |
| `ocr.extract_text`        | Extract all text from image         |
| `ocr.extract_from_pdf`    | Extract text from PDF pages         |
| `ocr.detect_text_regions` | Detect text bounding boxes          |
| `ocr.detect_handwriting`  | Detect and extract handwritten text |

### 2. Screenshot Parser Tools (`screenshot.*`)

| Tool                              | Description                      |
| --------------------------------- | -------------------------------- |
| `screenshot.detect_platform`      | Identify messaging platform      |
| `screenshot.extract_messages`     | Extract individual messages      |
| `screenshot.extract_timestamps`   | Extract and normalize timestamps |
| `screenshot.detect_reactions`     | Detect emoji reactions           |
| `screenshot.detect_read_receipts` | Detect delivery/read status      |
| `screenshot.extract_metadata`     | Extract EXIF and file metadata   |

### 3. Content Analysis Tools (`content.*`)

| Tool                          | Description                         |
| ----------------------------- | ----------------------------------- |
| `content.analyze_sentiment`   | Analyze emotional sentiment         |
| `content.detect_toxicity`     | Detect toxic/harmful language       |
| `content.detect_manipulation` | Detect manipulation tactics         |
| `content.extract_entities`    | Extract named entities              |
| `content.detect_pii`          | Detect personally identifiable info |
| `content.redact_pii`          | Redact PII from text                |
| `content.classify_intent`     | Classify message intent             |
| `content.detect_language`     | Detect text language                |

### 4. Image Analysis Tools (`image.*`)

| Tool                           | Description                        |
| ------------------------------ | ---------------------------------- |
| `image.detect_harmful_content` | Detect inappropriate content       |
| `image.detect_faces`           | Detect faces with emotions         |
| `image.detect_objects`         | Detect objects and scenes          |
| `image.analyze_quality`        | Analyze image quality/manipulation |
| `image.compare_images`         | Compare two images for similarity  |

### 5. Forensics Tools (`forensics.*`)

| Tool                                | Description                      |
| ----------------------------------- | -------------------------------- |
| `forensics.analyze_patterns`        | Analyze communication patterns   |
| `forensics.detect_gaslighting`      | Detect gaslighting patterns      |
| `forensics.detect_coercive_control` | Detect coercive control patterns |
| `forensics.detect_love_bombing`     | Detect love bombing patterns     |
| `forensics.score_severity`          | Score overall severity           |
| `forensics.generate_timeline`       | Generate event timeline          |
| `forensics.analyze_hurtlex`         | Analyze using HurtLex lexicon    |
| `forensics.detect_contradictions`   | Detect statement contradictions  |

### 6. LLM Tools (`llm.*`)

| Tool                     | Description                   |
| ------------------------ | ----------------------------- |
| `llm.chat`               | Chat completion with routing  |
| `llm.embed`              | Generate embeddings           |
| `llm.summarize`          | Summarize text                |
| `llm.classify`           | Classify text into categories |
| `llm.extract_structured` | Extract structured data       |

### 7. Document Tools (`document.*`)

| Tool                      | Description                  |
| ------------------------- | ---------------------------- |
| `document.parse`          | Parse document (any format)  |
| `document.chunk`          | Split document into chunks   |
| `document.extract_tables` | Extract tables from document |
| `document.extract_forms`  | Extract form fields          |

### 8. Schema Tools (`schema.*`)

| Tool                      | Description                      |
| ------------------------- | -------------------------------- |
| `schema.detect`           | Auto-detect data schema          |
| `schema.validate`         | Validate data against schema     |
| `schema.transform`        | Transform data between schemas   |
| `schema.resolve_platform` | Resolve platform-specific schema |

---

## Workflow Tools (`workflow.*`)

| Tool                                  | Description                              |
| ------------------------------------- | ---------------------------------------- |
| `workflow.screenshot_to_conversation` | Full screenshot parsing pipeline         |
| `workflow.analyze_communication`      | Full forensics analysis pipeline         |
| `workflow.process_evidence_batch`     | Batch process multiple files             |
| `workflow.extract_and_classify`       | OCR + entity extraction + classification |
| `workflow.legal_evidence_package`     | Prepare evidence for legal submission    |

---

## Standard Response Format

All tools return:

```json
{
  "success": true,
  "data": { ... },
  "metadata": { "processing_time_ms": 1234 },
  "warnings": [],
  "errors": []
}
```
