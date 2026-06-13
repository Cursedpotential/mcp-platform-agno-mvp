# Remediation #2: Zod Table Allowlist + Validation for PostgresWriter

## Context

`postgres_write_record` accepts any table name. `postgres_raw_query` accepts arbitrary SQL. Both need guardrails that fail loudly, log violations, and meet evidentiary standards.

## Full Table Inventory (3 SQL init files)

### `app` schema (14 tables)
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

| Table | Required Hash Field |
|-------|-------------------|
| `evidence.messages` | `content_hash` |
| `evidence.documents` | `file_hash` |
| `evidence.message_analysis` | `source_hash` |
| `evidence.behavioral_findings` | `source_hash` |
| `evidence.tool_execution_log` | `input_hash` |

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


---

# Plan Feedback

I've reviewed this plan and have 4 pieces of feedback:

## 1. Feedback on: "pp.pattern_categories	NO	Reference data
app.mcl_factors	NO	Reference data
app.hurtlex_categories	NO	Reference data
app.hurtlex_terms	NO	Reference data
app.analysis_modules	NO	Reference data
app.severity_weights"
> Reference data still needs to have an entry point to be modified add to added to removed whatever So maybe doesn't need an MCP It should probably have an API everything should at least have an API even if it's not exposed to the MCP

## 2. Feedback on: "evidence.hash_audit	NO"
> We need to be able to pull this as a report but not necessarily edit it again it probably could be exposed as an API and on the admin side in the GUI or something Or as a report I know best practice

## 3. Feedback on: "Table	Required Hash Field	
evidence.messages	content_hash
evidence.documents	file_hash
evidence.message_analysis	source_hash
evidence.behavioral_findings	source_hash
evidence.tool_execution_log	input_hash"
> This table I want you to take a minute and deep think and reflect on this and then sequential think and make sure you got it right so 2 thinking processes think it over twice do a good job

## 4. Feedback on: "All errors logged to stdout with severity prefix for monitoring"
> I believe you're telling me here that it's going to fail loudly which is good but it's also going to audit everything right like pretty much every action that happens will be audited correct

---
