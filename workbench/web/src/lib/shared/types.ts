// Byline: Claude Code · Sonnet (agent) · 2026-07-19
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

/** Response body from `POST /api/promote/{id}` and each entry of `/api/promote-all`. */
export interface PromoteResult {
  id: string;
  status: StagedStatus;
  promote_result?: Record<string, unknown> | null;
  error?: string | null;
}

/** Local upload-widget progress state — not part of the API contract. */
export type UploadItemStatus = "uploading" | "complete" | "error";
