# Conversation & Log File Ingestion System - Design Thread Export

**Date:** January 6, 2026  
**Context:** Salem v. Kinzel Case - Forensic Unit Development  
**Purpose:** Design modular system for processing large conversation/log files for PostgreSQL ingestion

---

## Initial Requirements

### Core Goals
1. Process large conversation files and log files of varying types and formats
2. Chunk files if necessary before processing
3. Modular architecture from schemas to exports to functions
4. Handle multiple file formats (JSON, CSV, XML, logs, text)
5. PostgreSQL as target database
6. All components should be pluggable/extensible

---

## Architecture Evolution

### First Design - Basic Flow
Initial pipeline concept was too linear. Needed revision.

### Second Design - Chunk-First Approach

**Key Insight:** Chunk BEFORE trying to process, not after format detection.

```
Large File → Chunker (format-agnostic) → Format Detector → Schema Discovery → 
Field Mapping → Parser → Transformer → PostgreSQL Ingester
```

### Third Design - Schema-Aware with Validation

**Key Additions:**
1. Check known schemas FIRST before discovery (saves time)
2. Validate chunks after splitting (ensure structure integrity)
3. Repair broken structures WITHOUT data loss
4. Interactive field mapping with GUI option

```
File → Naming Strategy → Chunker → Validator → Repairer → 
Schema Matcher (check known schemas) → 
[If no match: Discovery + Mapping] → 
Process with Schema → Ingest
```

### Fourth Design - Transformation Layer

**Major Addition:** Transformation detection and configuration layer

```
File → Chunk + Name → Validate + Repair → Schema Match/Discovery → 
TRANSFORMATION DETECTION → TRANSFORMATION CONFIGURATION → 
Apply Transformations → Field Mapping → Ingest
```

### Fifth Design - Preview & Interactive Validation (Final)

**Critical Addition:** Preview and iterative validation before full processing

```
File → Chunk + Name → Validate + Repair → Schema Match/Discovery → 
Transformation Detection/Config → 
PREVIEW MODE (10 records) → [User Review] → 
[If issues: Interactive Fix] → [Process another 10] → 
[When satisfied: Full Processing] → Ingest
```

---

## Directory Structure

```
conversation-ingester/
├── config/
│   ├── database.json
│   ├── known_schemas/          # Pre-saved schemas
│   │   ├── slack_export.json
│   │   ├── discord_chat.json
│   │   ├── whatsapp_log.json
│   │   └── custom_conversation_v1.json
│   └── transformations/        # Saved transformation configs
│       ├── slack_transforms.json
│       └── sms_transforms.json
│
├── chunks/                     # Output directory for chunks
│   └── {filename}_{timestamp}/
│       ├── chunk_001.{ext}
│       ├── chunk_002.{ext}
│       └── metadata.json
│
├── src/
│   ├── core/
│   │   ├── chunker/
│   │   │   ├── base_chunker.py
│   │   │   ├── line_chunker.py
│   │   │   ├── size_chunker.py
│   │   │   ├── smart_chunker.py
│   │   │   └── chunk_namer.py
│   │   │
│   │   ├── validation/
│   │   │   ├── validator_factory.py
│   │   │   ├── json_validator.py
│   │   │   ├── csv_validator.py
│   │   │   ├── xml_validator.py
│   │   │   └── log_validator.py
│   │   │
│   │   ├── repair/
│   │   │   ├── json_repairer.py
│   │   │   ├── csv_repairer.py
│   │   │   ├── xml_repairer.py
│   │   │   └── repair_strategies.py
│   │   │
│   │   ├── schema_matching/
│   │   │   ├── schema_matcher.py
│   │   │   ├── fingerprinter.py
│   │   │   └── similarity.py
│   │   │
│   │   ├── discovery/
│   │   │   ├── field_scanner.py
│   │   │   ├── type_inferencer.py
│   │   │   ├── pattern_detector.py
│   │   │   └── sample_extractor.py
│   │   │
│   │   ├── mapping/
│   │   │   ├── mapper.py
│   │   │   ├── cli_interface.py
│   │   │   ├── web_interface.py
│   │   │   └── mapping_storage.py
│   │   │
│   │   ├── preview/            # NEW: Preview system
│   │   │   ├── preview_manager.py
│   │   │   ├── interactive_validator.py
│   │   │   └── formatters.py
│   │   │
│   │   ├── parser.py
│   │   ├── transformer.py
│   │   ├── validator.py
│   │   └── ingester.py
│   │
│   ├── transformers/
│   │   ├── detection/
│   │   │   ├── timezone_detector.py
│   │   │   ├── code_detector.py
│   │   │   ├── id_detector.py
│   │   │   └── pattern_detector.py
│   │   │
│   │   ├── transforms/
│   │   │   ├── timezone_transformer.py
│   │   │   ├── code_decoder.py
│   │   │   ├── id_enricher.py
│   │   │   ├── text_normalizer.py
│   │   │   ├── privacy_transformer.py
│   │   │   └── derived_field_calculator.py
│   │   │
│   │   ├── base_transformer.py
│   │   ├── pipeline.py
│   │   └── config_builder.py
│   │
│   ├── formats/
│   │   ├── detector.py
│   │   ├── json_handler.py
│   │   ├── csv_handler.py
│   │   ├── log_handler.py
│   │   └── text_handler.py
│   │
│   ├── schemas/
│   │   ├── postgres_schema.py
│   │   └── field_types.py
│   │
│   └── utils/
│       ├── file_utils.py
│       ├── registry.py
│       ├── naming.py
│       └── logger.py
│
├── web/                        # Optional web GUI (future)
│   ├── static/
│   ├── templates/
│   └── app.py
│
├── main.py
├── requirements.txt
└── README.md
```

---

## Key Components Design

### 1. Chunk Naming Strategy

**Features:**
- Prompt user for custom name or use default
- Default format: `{source_file}_{timestamp}/`
- Individual chunks: `chunk_{N:03d}.{ext}`
- Store in `./chunks/{folder_name}/`

```python
class ChunkNamer:
    def prompt_for_name(self) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"{self.base_name}_{timestamp}"
        
        # Interactive prompt with default option
        # Returns folder name for chunks
```

### 2. Validation & Repair System

**Validation Goals:**
- Check structural integrity after chunking
- Detect incomplete records at boundaries
- Identify syntax errors
- NO data loss during validation

**Repair Strategies:**
- JSON: Close unclosed brackets/braces, fix trailing commas
- CSV: Handle incomplete rows at chunk boundaries
- XML: Close unclosed tags
- Log files: Ensure complete log entries

```python
class ChunkValidator:
    def validate_chunk(self, chunk_path, file_type) -> ValidationResult
    
class ChunkRepairer:
    def repair(self, validation_result, chunk_path) -> RepairResult
```

**Key Principle:** Repair structure, NEVER remove data. If a row is incomplete at chunk boundary, it stays for the next chunk to complete.

### 3. Schema Matching System

**Priority:** Check known schemas BEFORE discovery

**Process:**
1. Extract schema fingerprint from sample chunks
2. Compare against library of known schemas
3. Calculate similarity score (Jaccard + type matching)
4. If >85% match, use known schema
5. If no match, trigger schema discovery

```python
class SchemaLibrary:
    def match_schema(self, sample_chunk) -> Optional[SchemaMatch]
    def _calculate_similarity(self, discovered, known) -> float
```

**Benefits:**
- Saves time on repeated file types
- Ensures consistency across runs
- Builds institutional knowledge

### 4. Transformation System

**Philosophy:** Enrich and enhance data during ingestion, not after.

#### Transformer Types

**A. Timezone Transformer**
- Detects UTC timestamps
- Adds additional timezone columns (Eastern, Pacific, etc.)
- Option to keep or replace original
- Example: `timestamp` (UTC) → adds `timestamp_us_eastern`

**B. Code Decoder**
- Detects integer fields with small value ranges (2-10 unique values)
- Interactive mapping: `1=read, 2=unread, 3=blocked`
- Option to replace or add new decoded field
- Saves decoding templates for reuse

**C. ID Enricher** (planned)
- Resolves IDs to human-readable names
- Sources: CSV lookup, database, API, or self-referential

**D. Derived Field Calculator** (planned)
- Duration from start/end times
- Message length from text
- Business hours flag
- Day of week, hour of day

**E. Privacy Transformer** (planned)
- Hash emails
- Anonymize IPs (keep subnet)
- Redact phone numbers
- Pattern-based PII removal

**F. Text Normalizer** (planned)
- Trim whitespace
- Standardize line endings
- Optional lowercase
- Remove special characters

#### Transformation Pipeline

```python
class TransformationPipeline:
    def detect_and_configure(self, sample_chunks) -> List[BaseTransformer]
    def apply_transformations(self, record) -> Dict
    def get_enhanced_schema(self, base_schema) -> Schema
```

**Flow:**
1. Auto-detect applicable transformers from sample data
2. Configure each transformer interactively
3. Save configuration for reuse
4. Apply to all records during processing
5. Update schema with new fields

### 5. Preview & Interactive Validation System (NEW)

**Critical Feature:** Preview before full processing

#### Preview Manager

```python
class PreviewManager:
    def preview_first_batch(self, chunks, pipeline, batch_size=10) -> PreviewResult
    def display_preview(self, records, schema, transformations)
    def interactive_review(self, preview_result) -> ReviewDecision
```

**Preview Display Format:**

```
============================================================
📋 PREVIEW MODE - First 10 Records
============================================================

Record 1/10:
┌─────────────────────┬──────────────────────────────────┐
│ Field               │ Value                            │
├─────────────────────┼──────────────────────────────────┤
│ timestamp           │ 2024-01-15T10:30:00Z             │
│ timestamp_us_eastern│ 2024-01-15 05:30:00-05:00       │
│ user_id             │ 12345                            │
│ message             │ Hello world                      │
│ message_status      │ 1                                │
│ message_status_...  │ read                             │
└─────────────────────┴──────────────────────────────────┘

Record 2/10:
[...]

============================================================
Preview Summary:
  Records shown: 10
  Schema fields: 27
  Transformations applied: 2
  Errors detected: 0
  
Options:
  [c] Continue - Process entire file (247 chunks, ~500k records)
  [n] Next 10 - Preview another batch
  [m] Modify - Adjust transformations or mappings
  [f] Fix - Enter interactive mode to fix detected issues
  [q] Quit - Cancel processing
  
Your choice: _
```

#### Interactive Validation Flow

```
User chooses [n] - Next 10:
→ Process next batch of 10 records
→ Display preview again
→ Repeat until satisfied or issues found

User chooses [f] - Fix issues:
→ Enter interactive debugger
→ Show problematic records
→ Offer field-by-field inspection
→ Allow on-the-fly mapping adjustments
→ Re-preview with fixes

User chooses [m] - Modify:
→ Return to transformation configuration
→ Adjust timezone selections
→ Modify code decodings
→ Re-apply and preview
```

#### Error Detection & Interactive Fix

```python
class InteractiveValidator:
    def detect_issues(self, records) -> List[ValidationIssue]
    def interactive_fix_session(self, issues) -> FixResult
```

**Issue Types:**
- Field parsing failures
- Type mismatches
- Null/missing required fields
- Invalid foreign keys
- Transformation errors

**Interactive Fix Example:**

```
⚠️  Issues Detected in Preview

Issue 1/3: Field Parsing Error
  Record: #7
  Field: timestamp
  Value: "not-a-valid-date"
  Expected: ISO8601 datetime
  
  Options:
    [s] Skip this record
    [d] Use default value (current time)
    [m] Manual entry
    [i] Ignore this field
    [a] Apply fix to all similar
  
  Your choice: d
  ✓ Will use current timestamp for invalid dates
```

### 6. Complete Pipeline Integration

```python
class IngestionPipeline:
    def process_file(self, source_file: Path):
        # Phase 1: Setup
        namer = ChunkNamer(source_file)
        folder_name = namer.prompt_for_name()
        
        # Phase 2: Chunking
        chunks = self.chunker.chunk_file(source_file, folder_name, namer)
        
        # Phase 3: Validation & Repair
        for chunk in chunks:
            validation = self.validator.validate_chunk(chunk)
            if not validation.valid:
                self.repairer.repair(validation, chunk)
        
        # Phase 4: Schema Matching
        schema_match = self.schema_library.match_schema(chunks[0])
        if schema_match:
            schema = schema_match.schema
        else:
            schema = self.discovery.scan_chunks(chunks[:10])
        
        # Phase 5: Transformation Detection & Config
        transform_pipeline = TransformationPipeline()
        transformers = transform_pipeline.detect_and_configure(chunks[:10])
        if transformers:
            schema = transform_pipeline.get_enhanced_schema(schema)
        
        # Phase 6: PREVIEW MODE
        preview_manager = PreviewManager()
        while True:
            preview_result = preview_manager.preview_first_batch(
                chunks=chunks,
                pipeline=transform_pipeline,
                batch_size=10
            )
            
            preview_manager.display_preview(
                records=preview_result.records,
                schema=schema,
                transformations=transformers
            )
            
            decision = preview_manager.interactive_review(preview_result)
            
            if decision.action == 'continue':
                break
            elif decision.action == 'next_batch':
                # Preview next 10
                continue
            elif decision.action == 'modify':
                # Re-configure transformations
                transformers = transform_pipeline.detect_and_configure(chunks[:10])
            elif decision.action == 'fix':
                # Interactive fix session
                validator = InteractiveValidator()
                issues = validator.detect_issues(preview_result.records)
                fix_result = validator.interactive_fix_session(issues)
                # Apply fixes to pipeline
                transform_pipeline.apply_fixes(fix_result)
            elif decision.action == 'quit':
                return
        
        # Phase 7: Field Mapping (if needed)
        if not schema_match:
            mapper = FieldMapper()
            mapping = mapper.create_mapping_interactive(schema)
        
        # Phase 8: Full Processing
        self.ingest_chunks(chunks, schema, transform_pipeline, mapping)
```

---

## Usage Examples

### Basic Run - Known Schema

```bash
$ python main.py process slack_export.json

============================================================
Processing: slack_export.json
============================================================

=== Chunk Output Configuration ===
Source file: slack_export.json
Default output: ./chunks/slack_export_20241102_143022/

Options:
  [Enter] - Use default name
  [Custom name] - Specify custom folder name

Your choice: [Enter]

✓ Output location: ./chunks/slack_export_20241102_143022/

📦 Chunking file...
✓ Created 247 chunks

🔍 Validating chunks...
  Chunk 1/247: ✓ Valid
  [...]
  Chunk 247/247: ✓ Valid

🔎 Checking against known schemas...
✓ Matched schema: slack_export
  Confidence: 94.3%

🔄 Transformation Analysis
✓ Loaded saved transformations: slack_transforms.json

📋 PREVIEW MODE - First 10 Records
[Preview display...]

Options:
  [c] Continue - Process entire file
  [n] Next 10 - Preview another batch
  [q] Quit

Your choice: c

============================================================
📥 Ingesting to PostgreSQL...
============================================================
✓ Processed 247 chunks (500,482 records)
✓ Inserted into table: slack_messages
✓ Duration: 2m 34s
```

### Complex Run - New Format with Issues

```bash
$ python main.py process unknown_format.log

[... chunking and validation ...]

🔎 Checking against known schemas...
✗ No known schema matched

🔬 Discovering schema from data...
✓ Discovered 15 fields

🔄 Transformation Analysis

✓ TimezoneTransformer
  Confidence: 90%
  Found UTC timestamps in: timestamp

  Apply this transformation? [Y/n]: y

[... transformation configuration ...]

📋 PREVIEW MODE - First 10 Records

Record 1/10:
  timestamp: 2024-01-15T10:30:00Z
  user_id: 12345
  action: login
  status: 1
  [...]

⚠️  Issues Detected:
  - Record #7: Invalid timestamp format
  - Record #9: Missing required field 'user_id'

Options:
  [c] Continue (with warnings)
  [n] Next 10
  [f] Fix issues interactively
  [q] Quit

Your choice: f

=== Interactive Fix Session ===

Issue 1/2: Invalid timestamp
  Record #7
  Field: timestamp
  Value: "not-a-valid-date"
  
  Options:
    [s] Skip this record
    [d] Use default value
    [m] Manual entry
    [a] Apply to all similar
  
  Your choice: d
  ✓ Will use current timestamp for invalid dates

Issue 2/2: Missing required field
  Record #9
  Field: user_id
  Value: null
  
  Options:
    [s] Skip this record
    [n] Make field nullable
    [d] Use default value
  
  Your choice: n
  ✓ Field 'user_id' marked as nullable

✓ All issues resolved

[Return to preview with fixes applied...]
```

---

## Key Design Principles

1. **Chunk First, Ask Questions Later**
   - Don't try to understand format before chunking
   - Chunking is format-agnostic
   - Enables processing files larger than RAM

2. **Validate and Repair Without Data Loss**
   - Structure repairs only (close brackets, complete rows)
   - Never delete or modify actual data
   - Incomplete records stay for next chunk

3. **Schema Awareness Before Discovery**
   - Check known schemas first
   - Build institutional knowledge
   - Faster processing on repeated formats

4. **Transform During Ingestion, Not After**
   - Enrichment happens in the pipeline
   - Timezone conversions, code decoding, derived fields
   - Output is analysis-ready

5. **Preview Before Commit**
   - ALWAYS show sample before full processing
   - Interactive validation and fixing
   - Iterative refinement (another 10, another 10...)

6. **Modular and Extensible**
   - Plugin architecture for parsers
   - Transformer system for enrichment
   - Easy to add new formats
   - Configuration-driven

7. **CLI First, GUI Second**
   - Build CLI for MVP
   - Add modern web GUI later
   - Both share same core logic

8. **Save Configurations for Reuse**
   - Schema definitions
   - Transformation configs
   - Field mappings
   - Decoding templates

---

## Transformation Examples

### Timezone Transformation

**Input:**
```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "event": "message_sent"
}
```

**Output:**
```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "timestamp_us_eastern": "2024-01-15T05:30:00-05:00",
  "event": "message_sent"
}
```

### Code Decoder Transformation

**Input:**
```json
{
  "message_status": 1,
  "message_type": 0
}
```

**Output:**
```json
{
  "message_status": 1,
  "message_status_decoded": "read",
  "message_type": 0,
  "message_type_decoded": "sms"
}
```

### Combined Transformations

**Input:**
```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "user_id": 12345,
  "message": "Hello world",
  "status": 1,
  "type": 0
}
```

**After All Transformations:**
```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "timestamp_us_eastern": "2024-01-15T05:30:00-05:00",
  "user_id": 12345,
  "message": "Hello world",
  "message_length": 11,
  "status": 1,
  "status_decoded": "read",
  "type": 0,
  "type_decoded": "sms",
  "hour_of_day": 5,
  "day_of_week": "Monday",
  "is_business_hours": false
}
```

---

## Next Steps - Implementation Priority

### Phase 1: Foundation (Week 1)
1. ✓ Architecture design complete
2. ⏳ Chunk naming system
3. ⏳ Basic chunker (line-based, size-based)
4. ⏳ File format detector

### Phase 2: Validation & Repair (Week 1-2)
5. ⏳ Validator factory + JSON/CSV validators
6. ⏳ Repairer system (JSON, CSV)
7. ⏳ Validation result models

### Phase 3: Schema System (Week 2)
8. ⏳ Schema library + known schemas storage
9. ⏳ Schema fingerprinting
10. ⏳ Schema similarity matching
11. ⏳ Schema discovery (if no match)

### Phase 4: Transformations (Week 2-3)
12. ⏳ Base transformer interface
13. ⏳ Timezone transformer
14. ⏳ Code decoder transformer
15. ⏳ Transformation pipeline
16. ⏳ Configuration save/load

### Phase 5: Preview System (Week 3)
17. ⏳ Preview manager
18. ⏳ Interactive validator
19. ⏳ Issue detection
20. ⏳ Fix session handler

### Phase 6: Integration & Testing (Week 3-4)
21. ⏳ Complete pipeline integration
22. ⏳ PostgreSQL ingester
23. ⏳ End-to-end testing
24. ⏳ Documentation

### Phase 7: Additional Features (Week 4+)
25. ⏳ Web GUI (Flask/FastAPI)
26. ⏳ Additional transformers (ID enricher, privacy, etc.)
27. ⏳ More file format handlers
28. ⏳ Performance optimization

---

## Technical Dependencies

```
# requirements.txt
psycopg2-binary>=2.9.0      # PostgreSQL driver
pytz>=2024.1                # Timezone handling
python-dateutil>=2.8.2      # Date parsing
jsonschema>=4.0.0           # JSON schema validation
pandas>=2.0.0               # CSV handling (optional)
sqlalchemy>=2.0.0           # ORM (optional)
pydantic>=2.0.0             # Data validation
click>=8.0.0                # CLI framework
rich>=13.0.0                # CLI formatting (optional)
flask>=3.0.0                # Web GUI (future)
```

---

## Database Schema Considerations

### Base Tables

```sql
-- Ingestion metadata
CREATE TABLE ingestion_runs (
    id SERIAL PRIMARY KEY,
    source_file TEXT NOT NULL,
    chunk_folder TEXT NOT NULL,
    schema_name TEXT,
    transformation_config JSONB,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    total_chunks INT,
    total_records INT,
    status TEXT,
    error_log TEXT
);

-- Chunk processing status
CREATE TABLE chunk_status (
    id SERIAL PRIMARY KEY,
    ingestion_run_id INT REFERENCES ingestion_runs(id),
    chunk_number INT,
    chunk_file TEXT,
    validation_status TEXT,
    repair_log JSONB,
    records_processed INT,
    errors JSONB,
    processed_at TIMESTAMPTZ
);
```

### Target Data Tables

Schema dynamically generated based on discovered/matched schema plus transformations.

---

## Forensic Use Case Notes

For Salem case specifically:

### Critical Transformations
1. **Timezone normalization** - All timestamps to Eastern (court is in Michigan)
2. **Code decoding** - SMS status codes, message types
3. **Privacy protection** - Hash or redact PII where needed
4. **Pattern preservation** - "Nuance IS the abuse" - don't over-summarize

### Chain of Custody
- Chunk metadata includes SHA-256 hashes
- Transformation logs in database
- Original chunks preserved
- Full audit trail of all modifications

### Court Admissibility
- Document validation steps
- Document repair decisions
- Preserve source data integrity
- Timestamped processing logs

---

## Additional Transformer Ideas Discussed

1. **ID Enricher** - Resolve IDs to names from lookup tables
2. **Text Normalizer** - Standardize text fields
3. **Privacy Transformer** - Hash emails, anonymize IPs
4. **Derived Field Calculator** - Duration, length, business hours
5. **URL Expander** - Follow shortened URLs
6. **Phone Number Normalizer** - E.164 format
7. **Duplication Marker** - Flag potential duplicates

---

## Questions Still Open

1. **Performance optimization** - Parallel chunk processing?
2. **Error handling** - How aggressive should retry logic be?
3. **PostgreSQL connection** - Pooling strategy?
4. **Web GUI framework** - Flask vs FastAPI vs Streamlit?
5. **Large file thresholds** - When to recommend external processing?

---

## Contact & Context

**Project:** Salem v. Kinzel Forensic Processing System  
**Case #:** 2025-53985-DC  
**Court:** Genesee County 7th Circuit (Judge Weier)  
**Purpose:** Process digital evidence for coercive control pattern detection

**Related Systems:**
- Salem Forensic Trinity (parent system)
- Chronicle (voice interview app)
- TraceIQ (Google Timeline processor)
- Chat Miner (conversation parser)

**Infrastructure:**
- Supabase PostgreSQL (main database)
- Neo4j Aura (graph relationships)
- Qdrant Cloud (vector search)
- Coolify (deployment)

---

## End of Export

This export captures the complete design conversation through the preview and interactive validation phase. Next implementation step is building the preview manager and interactive validation system.
