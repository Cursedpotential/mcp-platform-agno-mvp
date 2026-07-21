// Byline: Claude Code · Sonnet (agent) · 2026-07-20
/**
 * Types for the Knowledge Workbench staged-file record.
 *
 * Inlined from the donor kit's `packages/shared` (this app is no longer part
 * of a pnpm workspace, so there is no `@vibe-coding-starter-kit/shared` to
 * depend on) and rewritten to match the workbench FastAPI backend's contract
 * — see `workbench/api/app/types/documents.py::StagedFile` for the source of
 * truth this mirrors.
 */

/** Lifecycle of a staged file record. */
export type StagedStatus = "staged" | "promoting" | "promoted" | "failed";

/** Which promote path a staged file should take. */
export type DetectedType = "doc" | "chat_export";

/** The only four domains the workbench classifies staged files into. */
export const DOMAIN_OPTIONS = [
  "timeline_relationship",
  "personal_history",
  "platform_design",
  "legal_strategy",
] as const;

export type Domain = (typeof DOMAIN_OPTIONS)[number];

/** User-editable classification metadata for a staged file. */
export interface StagedFileMeta {
  domain?: string | null;
  category?: string | null;
  source_platform?: string | null;
}

/** A row in the backend's `staged_files` table. */
export interface StagedFile {
  id: string;
  name: string;
  size: number;
  mime: string;
  detected_type: DetectedType;
  /** Extracted text preview, capped server-side; "" for binary formats. */
  text?: string;
  meta: StagedFileMeta;
  r2_key: string;
  status: StagedStatus;
  promote_result?: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

/** Response body from `POST /api/upload` — a staged file plus a duplicate flag. */
export interface UploadResponse extends StagedFile {
  duplicate?: boolean;
}

/** Local upload-widget progress state — not part of the API contract. */
export type UploadItemStatus = "uploading" | "complete" | "error";

// ---------------------------------------------------------------------------
// Runs (C1 Operator Console) — mirrors the spine's C0 run ledger
// (server/evidence/run_ledger.py, server/api/run_routes.py,
// sql/0005_workflow_run_ledger.sql), a parallel build that landed in this
// same working tree while this frontend was in progress. Field shapes below
// were cross-checked against that actual code (not just the build brief's
// prose), which is how the run/stage status-vocabulary mismatch below was
// caught before it shipped.
// ---------------------------------------------------------------------------

/** Lifecycle of a spine run — matches the `analysis.workflow_run.status`
 * CHECK constraint (sql/0005_workflow_run_ledger.sql) exactly. */
export type RunStatus = "running" | "paused" | "completed" | "failed";

/** Lifecycle of a single STAGE within a run — matches the
 * `analysis.workflow_run_stage.status` CHECK constraint exactly. NOTE this
 * is a different vocabulary than RunStatus ("success"/"skipped", not
 * "completed") — a real gotcha found while cross-checking the spine's
 * actual implementation (server/evidence/run_ledger.py) against the build
 * brief, which only documented run-level status. */
export type StageStatus = "pending" | "running" | "success" | "failed" | "skipped";

/** The only two workflows the spine currently documents. */
export const WORKFLOW_OPTIONS = ["chat-transcript", "sms-xml"] as const;
export type Workflow = (typeof WORKFLOW_OPTIONS)[number];

export type RunMode = "auto" | "supervised";

/** Supervised-gate state on a run (C2). Set only for supervised-mode runs;
 * `null` for auto-mode runs and non-gated states. Per the C2 spine contract
 * (console/c2-spine, a parallel branch this frontend codes against):
 * `status==='paused' && gate_state==='waiting'` means the run is stopped at
 * a gate, and the NEXT pending stage (lowest seq with status 'pending') is
 * the gated one. */
export type GateState = "waiting" | "released" | "abort" | null;

/** Evidence-chain depth for a run's source file (C2). `light` = whole-file
 * hash only; `full` = every intermediate hashed into the custody chain. The
 * spine defaults this per-workflow when omitted at run-creation time
 * (chat-transcript -> light, sms-xml -> full). */
export type CustodyTier = "full" | "light";

/** One row of a run's stage list, as embedded in `GET /v1/runs` list items.
 *
 * `content` (C2.6 requirement 3, optional): the spine's `list_runs()` now
 * includes each stage's `content` text (truncated server-side to 500 chars)
 * so a failed run's table row can show a truncated error snippet without a
 * second round-trip to `GET /v1/runs/{id}`. */
export interface RunStageSummary {
  seq: number;
  name: string;
  status: StageStatus;
  content?: string | null;
}

/** Typed `output` shapes per stage — keyed by convention on stage `name`
 * ("custody" | "parse" | "store" | "knowledge"). Field names verified
 * against the real implementation (server/evidence/workflows.py's
 * `_ledger_stage_output`), not just the build brief's prose description. */
export interface CustodyOutput {
  sha256?: string | null;
  artifact_id?: string | null;
  duplicate?: boolean;
  /** The build brief called this "blob path"; the actual ledger key is `blob_key`. */
  blob_key?: string | null;
  [key: string]: unknown;
}

export interface ParseOutput {
  parser_id?: string | null;
  attempts?: unknown[];
  schema_recognized?: boolean;
  record_count?: number;
  /** Already JSON-stringified + truncated to 500 chars server-side
   * (`json.dumps(r, default=str)[:500]`) — render as text, not re-parse. */
  sample_records?: string[];
  parse_stats?: Record<string, unknown>;
  /** sms-xml only (fallback-parser substitution occurred); chat-transcript never sets this. */
  alt_parse?: boolean;
  [key: string]: unknown;
}

export interface StoreOutput {
  rows_stored?: number;
  table?: string;
  [key: string]: unknown;
}

export interface KnowledgeOutput {
  docs_ingested?: number;
  domain?: string | null;
  skipped?: boolean;
  [key: string]: unknown;
}

export type StageOutput = CustodyOutput | ParseOutput | StoreOutput | KnowledgeOutput | Record<string, unknown>;

/** A stage as returned by `GET /v1/runs/{run_id}` (the detail view) —
 * `SELECT *` off `analysis.workflow_run_stage`, so `stage_id`/`run_id` also
 * ride along; only the fields the console renders are declared here. */
export interface RunStageDetail {
  seq: number;
  name: string;
  status: StageStatus;
  content?: string | null;
  output?: StageOutput | null;
  started_at?: string | null;
  finished_at?: string | null;
}

/** Fields common to both `GET /v1/runs` list rows and the `GET /v1/runs/{id}`
 * detail's top level (both are `SELECT *` off `analysis.workflow_run`). */
export interface RunFields {
  run_id: string;
  workflow: string;
  mode: RunMode;
  source_name: string | null;
  source_path?: string | null;
  sha256: string | null;
  artifact_id?: string | null;
  domain: string | null;
  status: RunStatus;
  /** The runner's own end-of-run summary dict (run_chat_transcript/run_sms_xml's return value). */
  summary?: Record<string, unknown> | null;
  /** Set only if an exception escaped the workflow runner itself (rare — most
   * failures surface as a failed STAGE with `content`, not this). */
  error?: string | null;
  created_at: string;
  updated_at: string;
  /** C2: supervised-gate state — see `GateState` doc comment. */
  gate_state: GateState;
  /** C2: the run this one was created from via POST /v1/runs/{id}/retry,
   * or null for a run that wasn't a retry. */
  parent_run_id: string | null;
  /** C2: evidence-chain depth — see `CustodyTier` doc comment. */
  custody_tier: CustodyTier;
}

/** One row of `GET /v1/runs`. */
export interface RunSummary extends RunFields {
  stages: RunStageSummary[];
}

/** `GET /v1/runs/{run_id}` — the summary fields plus full stage detail. */
export interface RunDetail extends RunFields {
  stages: RunStageDetail[];
}

/** `POST /api/runs` 202 response. */
export interface RunCreateResponse {
  run_id: string;
  workflow: string;
  mode: string;
}

/** `POST /api/runs/{id}/continue` 200 response (C2). 409 if not paused. */
export interface RunContinueResponse {
  run_id: string;
  status: RunStatus;
}

/** `POST /api/runs/{id}/abort` 200 response (C2) — `status` is always
 * 'failed'. 409 if the run is already terminal. */
export interface RunAbortResponse {
  run_id: string;
  status: RunStatus;
}

/** `POST /api/runs/{id}/retry` 202 response (C2) — `run_id` is the NEW run;
 * `parent_run_id` is the failed run that was retried. 409 if the source run
 * isn't terminal-failed. */
export interface RunRetryResponse {
  run_id: string;
  parent_run_id: string;
}

/** `POST /api/runs/{id}/retry` optional JSON body (C2.6). Omit entirely for
 * the full-rerun behavior; `"knowledge"` re-runs ONLY the knowledge stage
 * over the parent's already-stored records (server/evidence/workflows.py's
 * `run_knowledge_from_store`) — the fix for the custody-dedupe/no-new-rows
 * trap where a plain retry could report docs_ingested=0 without actually
 * re-ingesting anything. */
export type RetryFromStage = "knowledge";

// ---------------------------------------------------------------------------
// Dependency health strip (C2.6 requirement 4)
// ---------------------------------------------------------------------------

/** One dependency's health, as returned by both the spine's
 * `GET /v1/health/deps` and the workbench's `GET /api/health/deps`. */
export interface DepStatus {
  status: "ok" | "error";
  error?: string;
}

/** `GET /api/health/deps` response — the workbench's own lancedb/object_store
 * checks merged with a proxy of the spine's pg/milvus checks. */
export interface HealthDepsResponse {
  pg: DepStatus;
  milvus: DepStatus;
  lancedb: DepStatus;
  object_store: DepStatus;
  checked_at: string;
}

// ---------------------------------------------------------------------------
// MCP Tool Explorer
// ---------------------------------------------------------------------------

/** A (subset of) JSON Schema, as carried on an MCP tool's `inputSchema`. */
export interface JsonSchema {
  type?: string;
  properties?: Record<string, JsonSchema>;
  required?: string[];
  enum?: (string | number)[];
  items?: JsonSchema;
  description?: string;
  default?: unknown;
  [key: string]: unknown;
}

/** One tool as returned by an MCP server's `tools/list`. */
export interface McpTool {
  name: string;
  description?: string;
  inputSchema?: JsonSchema;
}

/** One entry of `GET /api/tools` — a configured server, its tools, or an error. */
export interface ToolServerGroup {
  key: string;
  label: string;
  tools?: McpTool[];
  error?: string;
}
