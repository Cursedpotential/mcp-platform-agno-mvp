// Byline: Claude Code · Sonnet (agent) · 2026-07-19
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
  PromoteResult,
  StagedFile,
  StagedFileMeta,
  UploadResponse,
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

export async function promoteFile(id: string) {
  return apiFetch<PromoteResult>(`/api/promote/${encodeURIComponent(id)}`, {
    method: "POST",
  });
}

export async function promoteAll() {
  return apiFetch<PromoteResult[]>("/api/promote-all", { method: "POST" });
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
