// Byline: Claude Code · Sonnet (agent) · 2026-07-22 (C3: records, schemas, verify, parse-dryrun, flags; C4: knowledge search/browse + Graphiti pane added 2026-07-23)
// Byline: Codex · GPT-5 · 2026-08-13 (run reports and review actions)
/**
 * API client for the Knowledge Workbench.
 *
 * The static export (`output: "export"`) is served same-origin by the
 * platform's FastAPI backend, so the base URL is empty by default — every
 * call resolves relative to the page's own origin. `NEXT_PUBLIC_API_URL`
 * remains a supported override for local dev against a backend on a
 * different port (it is baked in at build time, same as the donor kit).
 */
import type {
  CustodyTier,
  CourtCase,
  CourtCaseStatus,
  EvidenceItemListResponse,
  EvidencePromotionResult,
  EvidenceReviewDecision,
  EvidenceReviewListResponse,
  EvidenceReviewResult,
  FileAnalysis,
  FileTextResponse,
  Flag,
  FlagCreateRequest,
  FlagStatus,
  FlagTargetKind,
  FlagUpdateRequest,
  GraphitiEpisodesResponse,
  GraphitiFactsResponse,
  GraphitiNodesResponse,
  HealthDepsResponse,
  KnowledgeContentsResponse,
  KnowledgeSourceRef,
  KnowledgeSourceResolution,
  KnowledgeSearchResponse,
  Matter,
  MatterDetail,
  MatterListResponse,
  ParseDryrunResponse,
  RecordMetaPatch,
  RecordRow,
  RecordsListResponse,
  RetryFromStage,
  RunAbortResponse,
  RunContinueResponse,
  RunCreateResponse,
  RunDetail,
  RunMode,
  RunReport,
  RunReviewAction,
  RunReviewActionRequest,
  RunRetryResponse,
  RunSummary,
  SchemasResponse,
  StagedFile,
  StagedFileMeta,
  ToolServerGroup,
  UploadResponse,
  VerifyResponse,
  Workflow,
} from "./shared/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

/** Typed API error with HTTP status code for caller-side branching. */
export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }

  /** True for 408, 429, 500, 502, 503, 504 — worth retrying. */
  get isRetryable(): boolean {
    return [408, 429, 500, 502, 503, 504].includes(this.status);
  }

  get isNotFound(): boolean {
    return this.status === 404;
  }

  get isConflict(): boolean {
    return this.status === 409;
  }

  /** 410 — the spine has retired the resource (e.g. a stale gate action
   * racing a run that moved on). Distinct from isConflict(409): a 409
   * means "not in the right state right now", a 410 means "gone for good". */
  get isGone(): boolean {
    return this.status === 410;
  }
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, init);
  } catch {
    // Network failure (offline, DNS, CORS, etc.)
    throw new ApiError("Network error — check your connection", 0);
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(
      body.detail || `API error: ${res.status}`,
      res.status,
    );
  }
  return res.json();
}

export async function getHealth() {
  return apiFetch<{ status: string }>("/health");
}

/** Console header's dependency status chips (C2.6 requirement 4) —
 * `{lancedb, object_store, pg, milvus, checked_at}`. */
export async function getHealthDeps() {
  return apiFetch<HealthDepsResponse>("/api/health/deps");
}

export interface ListFilesParams {
  status?: string;
  detected_type?: string;
}

export async function listFiles(params: ListFilesParams = {}) {
  const qs = new URLSearchParams();
  if (params.status) qs.set("status", params.status);
  if (params.detected_type) qs.set("detected_type", params.detected_type);
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  return apiFetch<StagedFile[]>(`/api/files${suffix}`);
}

export async function getFile(id: string) {
  return apiFetch<StagedFile>(`/api/files/${encodeURIComponent(id)}`);
}

export async function updateFileMeta(id: string, patch: Partial<StagedFileMeta>) {
  return apiFetch<StagedFile>(`/api/files/${encodeURIComponent(id)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
}

/** Full, untruncated extracted text for the Preview modal (C2.7). */
export async function getFileText(id: string) {
  return apiFetch<FileTextResponse>(`/api/files/${encodeURIComponent(id)}/text`);
}

/** Re-run the server's detect.py sniffing + basic shape stats (C2.7). */
export async function analyzeFile(id: string) {
  return apiFetch<FileAnalysis>(`/api/files/${encodeURIComponent(id)}/analyze`, {
    method: "POST",
  });
}

// ---------------------------------------------------------------------------
// Repair control surface
// ---------------------------------------------------------------------------

export interface RepairToolCard {
  id: string;
  category: string;
  description: string;
  execution_policy: "manual_or_auto" | "manual_approval_required" | string;
  side_effect: string;
}

export interface RepairParticipant {
  type: "agent" | "team";
  id: string;
  name: string;
  role: string;
  recommended: boolean;
  is_factory: boolean;
}

export async function listRepairTools() {
  return apiFetch<RepairToolCard[]>("/api/repairs/tools");
}

export async function listRepairParticipants() {
  return apiFetch<RepairParticipant[]>("/api/repairs/participants");
}

export async function runAutomaticRepairAssessment(path: string, format?: string) {
  return apiFetch<Record<string, unknown>>("/api/repairs/automatic-assessment", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path, format: format || null, sample_limit: 25 }),
  });
}

export async function executeRepairTool(
  toolId: string,
  payload: Record<string, unknown>,
  approved = false,
) {
  return apiFetch<Record<string, unknown>>("/api/repairs/execute", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tool_id: toolId, payload, approved }),
  });
}

export async function runRepairAgentReview(params: {
  participant: RepairParticipant;
  path: string;
  task: string;
  assessment?: Record<string, unknown>;
  sessionId?: string;
}) {
  return apiFetch<Record<string, unknown>>("/api/repairs/agent-review", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      participant_type: params.participant.type,
      participant_id: params.participant.id,
      path: params.path,
      task: params.task,
      assessment: params.assessment ?? null,
      session_id: params.sessionId ?? null,
    }),
  });
}

// ---------------------------------------------------------------------------
// Runs (C1 Operator Console)
// ---------------------------------------------------------------------------

export interface ListRunsParams {
  status?: string;
  limit?: number;
}

export async function listRuns(params: ListRunsParams = {}) {
  const qs = new URLSearchParams();
  if (params.status) qs.set("status", params.status);
  if (params.limit) qs.set("limit", String(params.limit));
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  return apiFetch<RunSummary[]>(`/api/runs${suffix}`);
}

export async function getRun(runId: string) {
  return apiFetch<RunDetail>(`/api/runs/${encodeURIComponent(runId)}`);
}

/** Start a run from an already-staged file (JSON body — no re-upload). */
export async function createRunFromStaged(params: {
  stagedId: string;
  workflow: Workflow | string;
  domain: string;
  mode: RunMode;
  custodyTier?: CustodyTier;
  sourceMeta?: Record<string, unknown>;
}) {
  return apiFetch<RunCreateResponse>("/api/runs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      staged_id: params.stagedId,
      workflow: params.workflow,
      domain: params.domain,
      mode: params.mode,
      custody_tier: params.custodyTier ?? null,
      source_meta: params.sourceMeta ?? null,
    }),
  });
}

/** Start a run from a freshly dropped file (multipart — never lands in staging). */
export async function createRunFromFile(params: {
  file: File;
  workflow: Workflow | string;
  domain: string;
  mode: RunMode;
  custodyTier?: CustodyTier;
  sourceMeta?: Record<string, unknown>;
}) {
  const formData = new FormData();
  formData.append("file", params.file);
  formData.append("workflow", params.workflow);
  formData.append("domain", params.domain);
  formData.append("mode", params.mode);
  if (params.custodyTier) formData.append("custody_tier", params.custodyTier);
  if (params.sourceMeta) formData.append("source_meta", JSON.stringify(params.sourceMeta));
  return apiFetch<RunCreateResponse>("/api/runs", { method: "POST", body: formData });
}

// ---------------------------------------------------------------------------
// Run gate controls (C2)
// ---------------------------------------------------------------------------

/** Release a gated (paused) run past its current stage boundary. Throws
 * ApiError(409) if the run isn't paused. */
export async function continueRun(runId: string) {
  return apiFetch<RunContinueResponse>(`/api/runs/${encodeURIComponent(runId)}/continue`, {
    method: "POST",
  });
}

/** Abort a running or gated run. While `running`, this takes effect at the
 * next stage boundary rather than instantly. Throws ApiError(409) if the
 * run is already terminal. */
export async function abortRun(runId: string) {
  return apiFetch<RunAbortResponse>(`/api/runs/${encodeURIComponent(runId)}/abort`, {
    method: "POST",
  });
}

/** Start a fresh run from a terminal-failed one. The returned `run_id` is
 * the NEW run (not the one passed in) — open that run to watch it.
 * Throws ApiError(409) if the source run isn't terminal-failed.
 *
 * `fromStage` (C2.6, optional): pass `"knowledge"` to skip straight to
 * re-running the knowledge stage over the parent's already-stored records
 * instead of a full custody->parse->store->knowledge rerun — see
 * `RetryFromStage`'s doc comment. Omit for the pre-C2.6 full-rerun. */
export async function retryRun(runId: string, fromStage?: RetryFromStage) {
  return apiFetch<RunRetryResponse>(`/api/runs/${encodeURIComponent(runId)}/retry`, {
    method: "POST",
    ...(fromStage
      ? { headers: { "Content-Type": "application/json" }, body: JSON.stringify({ from_stage: fromStage }) }
      : {}),
  });
}

export async function getRunReport(runId: string) {
  return apiFetch<RunReport>(`/api/runs/${encodeURIComponent(runId)}/report`);
}

export async function createRunReviewAction(runId: string, payload: RunReviewActionRequest) {
  return apiFetch<RunReviewAction>(`/api/runs/${encodeURIComponent(runId)}/review-actions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

// ---------------------------------------------------------------------------
// Records (C3 — parse-quality review + curation)
// ---------------------------------------------------------------------------

export interface ListRecordsParams {
  artifactId?: string;
  runId?: string;
  q?: string;
  limit?: number;
  offset?: number;
}

export async function listRecords(params: ListRecordsParams = {}) {
  const qs = new URLSearchParams();
  if (params.artifactId) qs.set("artifact_id", params.artifactId);
  if (params.runId) qs.set("run_id", params.runId);
  if (params.q) qs.set("q", params.q);
  if (params.limit) qs.set("limit", String(params.limit));
  if (params.offset) qs.set("offset", String(params.offset));
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  return apiFetch<RecordsListResponse>(`/api/records${suffix}`);
}

/** Curation-only edit (title/labels/attrs_patch) — never touches evidence
 * blobs/hashes. Returns the updated record row. */
export async function patchRecordMeta(recordId: string, patch: RecordMetaPatch) {
  return apiFetch<RecordRow>(`/api/records/${encodeURIComponent(recordId)}/meta`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
}

// ---------------------------------------------------------------------------
// Schemas (C3 — raw PG/Milvus inspection views)
// ---------------------------------------------------------------------------

export async function getSchemas() {
  return apiFetch<SchemasResponse>("/api/schemas");
}

// ---------------------------------------------------------------------------
// Verify (C3 — active hash verification)
// ---------------------------------------------------------------------------

export async function verifySha256(sha256: string) {
  return apiFetch<VerifyResponse>(`/api/verify/${encodeURIComponent(sha256)}`, {
    method: "POST",
  });
}

// ---------------------------------------------------------------------------
// Parse dry-run (C3 — "the real parser candidates")
// ---------------------------------------------------------------------------

/** Dry-run parse an already-staged file by sha256 — no run is created. */
export async function parseDryrunSha(sha256: string) {
  return apiFetch<ParseDryrunResponse>("/api/runs/parse-dryrun", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sha256 }),
  });
}

/** Dry-run parse a fresh, not-yet-staged file — no run is created. */
export async function parseDryrunFile(file: File) {
  const formData = new FormData();
  formData.append("file", file);
  return apiFetch<ParseDryrunResponse>("/api/runs/parse-dryrun", { method: "POST", body: formData });
}

// ---------------------------------------------------------------------------
// Corroboration flags (C3 — requirements addendum 6)
// ---------------------------------------------------------------------------

export interface ListFlagsParams {
  status?: FlagStatus;
  targetKind?: FlagTargetKind;
}

export async function listFlags(params: ListFlagsParams = {}) {
  const qs = new URLSearchParams();
  if (params.status) qs.set("status", params.status);
  if (params.targetKind) qs.set("target_kind", params.targetKind);
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  return apiFetch<Flag[]>(`/api/flags${suffix}`);
}

export async function createFlag(payload: FlagCreateRequest) {
  return apiFetch<Flag>("/api/flags", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function updateFlag(flagId: string, patch: FlagUpdateRequest) {
  return apiFetch<Flag>(`/api/flags/${encodeURIComponent(flagId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
}

// ---------------------------------------------------------------------------
// Knowledge (C4 — Weaviate-backed, case/lane-scoped search/browse)
// ---------------------------------------------------------------------------

export interface SearchKnowledgeParams {
  caseId?: string;
  lane?: string;
  limit?: number;
}

export async function searchKnowledge(query: string, params: SearchKnowledgeParams = {}) {
  const qs = new URLSearchParams({ q: query });
  qs.set("case_id", params.caseId || "primary");
  if (params.lane) qs.set("lane", params.lane);
  if (params.limit) qs.set("limit", String(params.limit));
  return apiFetch<KnowledgeSearchResponse>(`/api/knowledge/search?${qs.toString()}`);
}

export interface ListKnowledgeContentsParams {
  caseId: string;
  lane: string;
  limit?: number;
  offset?: number;
}

export async function listKnowledgeContents(params: ListKnowledgeContentsParams) {
  const qs = new URLSearchParams();
  qs.set("case_id", params.caseId);
  qs.set("lane", params.lane);
  if (params.limit) qs.set("limit", String(params.limit));
  if (params.offset) qs.set("offset", String(params.offset));
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  return apiFetch<KnowledgeContentsResponse>(`/api/knowledge/contents${suffix}`);
}

// ---------------------------------------------------------------------------
// Matter workspace (framework-neutral spine API, via Workbench proxy)
// ---------------------------------------------------------------------------

export async function listMatters(limit = 50, offset = 0) {
  const qs = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  return apiFetch<MatterListResponse>(`/api/matters?${qs.toString()}`);
}

export async function createMatter(payload: {
  title: string;
  description?: string;
  partition_key?: string;
  created_by?: "owner";
}) {
  return apiFetch<Matter>("/api/matters", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function getMatter(matterId: string) {
  return apiFetch<MatterDetail>(`/api/matters/${encodeURIComponent(matterId)}`);
}

export async function createCourtCase(
  matterId: string,
  payload: {
    caption: string;
    court_name?: string;
    docket_number?: string;
    jurisdiction?: string;
    case_type?: string;
    status?: CourtCaseStatus;
    filed_on?: string;
    closed_on?: string;
    is_primary?: boolean;
    created_by?: "owner";
  },
) {
  return apiFetch<CourtCase>(`/api/matters/${encodeURIComponent(matterId)}/court-cases`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function resolveKnowledgeSource(matterId: string, source: KnowledgeSourceRef) {
  return apiFetch<KnowledgeSourceResolution>(
    `/api/matters/${encodeURIComponent(matterId)}/knowledge/resolve`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(source),
    },
  );
}

export async function createEvidenceItem(
  matterId: string,
  payload: {
    court_case_id: string;
    source: KnowledgeSourceRef & { normalized_record_id: string };
    title: string;
    description?: string;
    quote?: string;
    evidence_type?: string;
    created_by?: "owner";
  },
) {
  return apiFetch<EvidencePromotionResult>(
    `/api/matters/${encodeURIComponent(matterId)}/evidence-items`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
}

export async function listEvidenceItems(matterId: string, limit = 50, offset = 0) {
  const qs = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  return apiFetch<EvidenceItemListResponse>(
    `/api/matters/${encodeURIComponent(matterId)}/evidence-items?${qs.toString()}`,
  );
}

export async function reviewEvidenceItem(
  matterId: string,
  evidenceItemId: string,
  payload: {
    decision: EvidenceReviewDecision;
    rationale: string;
    reviewer?: "owner";
  },
) {
  return apiFetch<EvidenceReviewResult>(
    `/api/matters/${encodeURIComponent(matterId)}/evidence-items/${encodeURIComponent(evidenceItemId)}/reviews`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
}

export async function listEvidenceReviews(matterId: string, evidenceItemId: string) {
  return apiFetch<EvidenceReviewListResponse>(
    `/api/matters/${encodeURIComponent(matterId)}/evidence-items/${encodeURIComponent(evidenceItemId)}/reviews`,
  );
}

// ---------------------------------------------------------------------------
// Graphiti (C4 — Graph memory pane, read-only)
// ---------------------------------------------------------------------------

export async function searchGraphitiFacts(query: string, limit?: number, groupId = "platform") {
  const qs = new URLSearchParams({ q: query, kind: "facts" });
  qs.set("group_id", groupId);
  if (limit) qs.set("limit", String(limit));
  return apiFetch<GraphitiFactsResponse>(`/api/graphiti/search?${qs.toString()}`);
}

export async function searchGraphitiNodes(query: string, limit?: number, groupId = "platform") {
  const qs = new URLSearchParams({ q: query, kind: "nodes" });
  qs.set("group_id", groupId);
  if (limit) qs.set("limit", String(limit));
  return apiFetch<GraphitiNodesResponse>(`/api/graphiti/search?${qs.toString()}`);
}

export async function listGraphitiEpisodes(last?: number, groupId = "platform") {
  const qs = new URLSearchParams();
  qs.set("group_id", groupId);
  if (last) qs.set("last", String(last));
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  return apiFetch<GraphitiEpisodesResponse>(`/api/graphiti/episodes${suffix}`);
}

// ---------------------------------------------------------------------------
// Tool Explorer (MCP servers)
// ---------------------------------------------------------------------------

export async function listTools() {
  return apiFetch<ToolServerGroup[]>("/api/tools");
}

/** Raw tool-call result — shape is whatever the target MCP tool returns. */
export type ToolCallResult = unknown;

export async function callTool(server: string, name: string, args: Record<string, unknown>) {
  return apiFetch<ToolCallResult>("/api/tools/call", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ server, name, arguments: args }),
  });
}

/** Upload a file with progress reporting (non-streaming — one JSON response). */
export function uploadFile(
  file: File,
  onProgress?: (percent: number) => void,
): Promise<UploadResponse> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const formData = new FormData();
    formData.append("file", file);

    xhr.upload.addEventListener("progress", (e) => {
      if (e.lengthComputable && onProgress) {
        onProgress(Math.round((e.loaded / e.total) * 100));
      }
    });

    xhr.addEventListener("load", () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText));
        } catch {
          reject(new ApiError("Malformed response from server", xhr.status));
        }
      } else {
        try {
          const body = JSON.parse(xhr.responseText);
          reject(new ApiError(body.detail || `Upload failed: ${xhr.status}`, xhr.status));
        } catch {
          reject(new ApiError(`Upload failed: ${xhr.status}`, xhr.status));
        }
      }
    });

    xhr.addEventListener("error", () =>
      reject(new ApiError("Network error — check your connection", 0)),
    );
    xhr.addEventListener("abort", () =>
      reject(new ApiError("Upload aborted", 0)),
    );

    xhr.open("POST", `${API_BASE}/api/upload`);
    xhr.send(formData);
  });
}
