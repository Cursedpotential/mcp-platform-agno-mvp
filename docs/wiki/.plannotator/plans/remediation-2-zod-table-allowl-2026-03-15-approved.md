# Remediation #2: Zod Table Allowlist + Validation for PostgresWriter

## Context

`postgres_write_record` accepts any table name. `postgres_raw_query` accepts arbitrary SQL. Both need guardrails that fail loudly, log violations, and meet evidentiary standards.

## Full Table Inventory (3 SQL init files)

### `app` schema (20 tables)
| Table | MCP Writable? | Reason |
|-------|:---:|--------|
| `app.users` | NO | Auth table — Keycloak manages |
| `app.api_keys` | NO | Auth table — admin only |
| `app.api_key_usage_logs` | NO | System-generated audit |
| `app.llm_providers` | YES | Admin tools manage these |
| `app.routing_rules` | NO | Admin-only config |
| `app.system_prompts` | YES | Admin tools manage these |
| `app.workflow_templates` | YES | Workflow engine |
| `app.behavioral_patterns` | YES | Analysis config |
| `app.pattern_categories` | NO | Reference data |
| `app.mcl_factors` | NO | Reference data |
| `app.hurtlex_categories` | NO | Reference data |
| `app.hurtlex_terms` | NO | Reference data |
| `app.analysis_modules` | NO | Reference data |
| `app.severity_weights` | NO | Reference data |
| `app.user_settings` | YES | User preferences |
| `app.review_queue` | YES | HITL review queue |
| `app.audit_log` | NO | System-generated audit — WORM |
| `app.evidence_chains` | NO | System-generated chain of custody |
| `app.evidence_master_index` | NO | System-generated index |
| `app.forensic_results` | YES | Analysis results |

### `evidence` schema (7 tables)
| Table | MCP Writable? | Extra Validation |
|-------|:---:|--------|
| `evidence.messages` | YES | Requires `content_hash` |
| `evidence.conversations` | YES | — |
| `evidence.documents` | YES | Requires `file_hash` |
| `evidence.hash_audit` | NO | System-generated |
| `evidence.message_analysis` | YES | Requires `source_hash` |
| `evidence.analysis_runs` | YES | — |
| `evidence.behavioral_findings` | YES | Requires `source_hash` |
| `evidence.tool_execution_log` | YES | Requires `input_hash` |

## Changes

### 1. PostgresWriter.ts — Zod allowlist + evidence validation

- Add `TableNameSchema` as Zod enum of all writable tables
- Add `EVIDENCE_HASH_REQUIRED` map: tables that require a hash field and which field name
- `writeRecord()`: validate table name, check hash fields for evidence tables, fail loudly with `[SECURITY]` or `[CHAIN-OF-CUSTODY]` prefix
- `query()`: restrict to `SELECT` only, log blocked attempts with `[SECURITY]` prefix
- All errors thrown (not swallowed), logged to stdout with severity prefix

### 2. index.ts — Update tool description

Change `postgres_raw_query` description to clarify it's read-only SELECT.

## Evidence Hash Requirements

Every hash column in the database was audited (grep for `_hash` across all 3 SQL init files — 11 columns total).

### Validated on MCP write (required — reject if missing)

| Table | Required Hash Field | What It Hashes | NOT NULL in schema? |
|-------|-------------------|----------------|:---:|
| `evidence.messages` | `content_hash` | SHA-256 of message body text | YES |
| `evidence.documents` | `file_hash` | SHA-256 of raw file bytes | YES (UNIQUE) |
| `evidence.message_analysis` | `source_hash` | SHA-256 of analyzed text (should match messages.content_hash) | YES |
| `evidence.behavioral_findings` | `source_hash` | SHA-256 of concatenated sorted source message content_hashes | YES |
| `evidence.tool_execution_log` | `input_hash` | SHA-256 of JSON-serialized tool input | YES |
| `app.forensic_results` | `source_hash` | SHA-256 of source evidence | NO (nullable in PG, but Zod requires it) |

### Not validated (not MCP-writable or computed separately)

| Table | Hash Column | Why excluded |
|-------|-------------|-------------|
| `app.evidence_chains` | `original_hash` | System-generated chain-of-custody — not MCP-writable |
| `app.evidence_master_index` | `source_hash` | System-generated evidence index — not MCP-writable |
| `app.api_keys` | `key_hash` | Auth table — not MCP-writable |
| `evidence.tool_execution_log` | `output_hash` | Computed after tool execution, not on initial write |
| `evidence.tool_execution_log` | `source_hash` (provenance) | Optional provenance link — nullable, not required |

### Hash format validation

All hash values must match `/^[a-f0-9]{64}$/` (lowercase hex, exactly 64 chars = SHA-256). Reject with `[CHAIN-OF-CUSTODY] Invalid hash format` if malformed.

## Files Modified
- `ts-mcp-server/src/tools/PostgresWriter.ts`
- `ts-mcp-server/src/index.ts`

## Verification
- Write to `evidence.messages` without `content_hash` → `[CHAIN-OF-CUSTODY]` error
- Write to `app.users` → `[SECURITY]` error
- Write to `app.review_queue` → succeeds
- `postgres_raw_query` with `DELETE FROM...` → `[SECURITY]` error
- `postgres_raw_query` with `SELECT * FROM...` → succeeds
- All errors logged to stdout with severity prefix for monitoring
