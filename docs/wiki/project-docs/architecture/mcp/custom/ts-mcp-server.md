# TS MCP Server Tools — Complete Documentation

**Server:** dial-ts-core (port 8081)
**Transport:** HTTP (StreamableHTTPServerTransport)
**Tags:** `parser`, `database`, `ingestion`
**Status:** 18 built, 4 planned

---

## Parser Tools

### `parse_sms_xml`
- **Description:** Parse Android SMS/MMS XML exports (streaming, multi-GB support)
- **Input:** `file_path` (absolute path to XML file)
- **Output:** Array of NormalizedMessage objects
- **Features:** Stream processing, forensic call blocking detection (rejected/refused calls), normalized message format
- **File:** `ts-mcp-server/src/tools/SmsXmlParser.ts`
- **Status:** ✅ Built

### `parse_facebook_export`
- **Description:** Parse Facebook Messenger HTML/JSON exports
- **Input:** `file_path`, optional `own_name` for direction detection
- **Output:** Array of ParsedFacebookMessage objects
- **Features:** Dual structure support (div.message and _a6-g card formats), fuzzy date parsing, direction detection (inbound/outbound), message type classification
- **File:** `ts-mcp-server/src/tools/FacebookExportParser.ts`
- **Status:** ✅ Built

### `parse_imessage_pdf`
- **Description:** Parse iMessage PDF exports
- **Input:** `file_path` (absolute path to PDF)
- **Output:** Array of ImessageMessage objects
- **Features:** PDF text extraction via pdf-parse, multi-line message handling, timestamp parsing
- **File:** `ts-mcp-server/src/tools/ImessagePdfParser.ts`
- **Status:** ✅ Built

### `format_detector`
- **Description:** Confidence-scored format detection for any file
- **Input:** `file_path`
- **Output:** Detected format with confidence score
- **File:** TBD
- **Status:** ⏳ Planned (Phase B)

---

## Vault/Storage Tools

### `vault_log_ingestion`
- **Description:** Log new file into forensic DuckDB vault with SHA-256 hashing
- **Input:** `source_type`, `source_name`, optional `raw_content`, `binary_path`, `metadata`
- **Output:** IngestionLog with hash, ID, timestamps
- **Features:** SHA-256 hashing at first touch, UUIDv7 generation, write tracking initialization
- **File:** `ts-mcp-server/src/tools/DuckDbVault.ts`
- **Status:** ✅ Built

### `vault_get_pending_pass1`
- **Description:** Get files pending Pass 1 enrichment
- **Input:** None (default limit 50)
- **Output:** Array of IngestionLog objects with status='pending'
- **File:** `ts-mcp-server/src/tools/DuckDbVault.ts`
- **Status:** ✅ Built

### `vault_update_pass1_status`
- **Description:** Update Pass 1 processing status
- **Input:** `ingestion_id`, `status` (pending|processing|completed|failed)
- **Output:** Confirmation message
- **File:** `ts-mcp-server/src/tools/DuckDbVault.ts`
- **Status:** ✅ Built

### `vault_update_write_tracking`
- **Description:** Record which storage tier has which data
- **Input:** `ingestion_id`, `tier`, `written` (boolean)
- **Features:** Tracks data distribution across 4 tiers (lancedb, neo4j_semantic, neo4j_temporal, postgresql)
- **File:** `ts-mcp-server/src/tools/DuckDbVault.ts`
- **Status:** ✅ Built

### `postgres_write_record`
- **Description:** Insert record into PostgreSQL with parameterized queries
- **Input:** `table_name`, `data` (key-value object)
- **Output:** Inserted record with RETURNING clause
- **Features:** SQL injection safe, dynamic table insertion
- **File:** `ts-mcp-server/src/tools/PostgresWriter.ts`
- **Status:** ✅ Built

### `postgres_raw_query`
- **Description:** Execute parameterized SQL query
- **Input:** `sql` (parameterized query), optional `params` (array)
- **Output:** Query result rows
- **File:** `ts-mcp-server/src/tools/PostgresWriter.ts`
- **Status:** ✅ Built

---

## Admin Tools

### `admin_list_llm_providers`
- **Description:** List all configured LLM providers with status
- **Input:** None
- **Output:** Array of provider configs (id, name, base_url, is_active, priority, usage_count, cost)
- **File:** `ts-mcp-server/src/tools/AdminTools.ts`
- **Status:** ✅ Built

### `admin_upsert_llm_provider`
- **Description:** Add/update an LLM provider
- **Input:** `provider_name`, `api_key_encrypted`, optional `base_url`, `is_active`, `priority`
- **Output:** Updated/inserted provider record
- **File:** `ts-mcp-server/src/tools/AdminTools.ts`
- **Status:** ✅ Built

### `admin_list_system_prompts`
- **Description:** List all system prompts with versions
- **Input:** None
- **Output:** Array of prompts (id, name, description, tool_name, version, is_active, usage_count)
- **File:** `ts-mcp-server/src/tools/AdminTools.ts`
- **Status:** ✅ Built

### `admin_upsert_system_prompt`
- **Description:** Add/update a system prompt with version tracking
- **Input:** `name`, `prompt_text`, optional `description`, `tool_name`, `variables`
- **Output:** New prompt version record
- **Features:** Auto-increments version, parent_id linkage for history
- **File:** `ts-mcp-server/src/tools/AdminTools.ts`
- **Status:** ✅ Built

---

## Review Queue Tools (HITL)

### `review_list_pending`
- **Description:** List items awaiting human review
- **Input:** optional `limit` (default 50)
- **Output:** Array of review items with confidence, match_method, tool_output, context
- **File:** `ts-mcp-server/src/tools/ReviewQueue.ts`
- **Status:** ✅ Built

### `review_approve`
- **Description:** Approve an item and commit to production
- **Input:** `id`, `reviewed_by`, optional `notes`
- **Output:** Updated review record
- **File:** `ts-mcp-server/src/tools/ReviewQueue.ts`
- **Status:** ✅ Built

### `review_reject`
- **Description:** Reject an item with reason
- **Input:** `id`, `reviewed_by`, optional `notes`
- **Output:** Updated review record
- **File:** `ts-mcp-server/src/tools/ReviewQueue.ts`
- **Status:** ✅ Built

### `review_submit`
- **Description:** Submit low-confidence AI result for human review
- **Input:** `review_type`, optional `entity_a`, `entity_b`, `confidence`, `match_method`, `tool_name`, `tool_output`, `context`
- **Output:** New review queue record with status='PENDING'
- **File:** `ts-mcp-server/src/tools/ReviewQueue.ts`
- **Status:** ✅ Built

---

## Health Check

### `ping`
- **Description:** Ping the TS MCP server to verify it is running
- **Input:** None
- **Output:** "Pong from dial-ts-core!"
- **Status:** ✅ Built

---

## Utility Functions (Could Be Exposed as Tools)

| Function | Source | Description |
|----------|--------|-------------|
| `generateUUIDv7()` | DuckDbService.ts | Generate time-ordered UUID |
| `hashContent()` | DuckDbService.ts | Calculate SHA-256 hash |
| `getIngestionById()` | DuckDbService.ts | Retrieve ingestion record by ID |
| `getIngestionByHash()` | DuckDbService.ts | Retrieve ingestion by SHA-256 hash |
| `getPendingPass2()` | DuckDbService.ts | Get files pending Pass 2 (24hr window) |
| `healthCheck()` | DuckDbService.ts | Check DuckDB connection health |
| `detectFormat()` | ImessagePdfParser.ts | Detect if file is PDF |
| `detectDirection()` | FacebookExportParser.ts | Determine message direction |
| `detectMessageType()` | FacebookExportParser.ts | Classify message type |

---

## Gaps & Issues

1. **No DuckDB read/query tool** — Can only write, not retrieve
2. **No format detection** — Must know file type before parsing
3. **No WhatsApp parser** — Missing major messaging platform
4. **No full-text search** — Cannot search evidence by content
5. **Lazy singleton incomplete** — Connection pooling not working
6. **No registry pattern** — Tool dispatch uses if-chain
7. **No deduplication check** — Duplicate ingestions possible
8. **No batch operations** — All tools are single-record
