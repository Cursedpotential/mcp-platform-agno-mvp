// Byline: Claude Code · Sonnet (agent) · 2026-07-21 (C2.7: file text/analyze added)
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
  FileAnalysis,
  FileTextResponse,
  RunAbortResponse,
  RunContinueResponse,
  RunCreateResponse,
  RunDetail,
  RunMode,
  RunRetryResponse,
  RunSummary,
  StagedFile,
  StagedFileMeta,
  ToolServerGroup,
  UploadResponse,
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
 * Throws ApiError(409) if the source run isn't terminal-failed. */
export async function retryRun(runId: string) {
  return apiFetch<RunRetryResponse>(`/api/runs/${encodeURIComponent(runId)}/retry`, {
    method: "POST",
  });
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
