// Byline: Claude Code · Sonnet (agent) · 2026-07-21
/**
 * API client for the C2.5 Ops Copilot — POST /api/copilot/ask + /continue,
 * GET /api/copilot/health + /models + /presets.
 *
 * Deliberately a SEPARATE file from lib/api-client.ts (an addition, not an
 * edit to it) — two other agents are working in parallel on workbench/web
 * this sprint and api-client.ts / lib/shared/types.ts are shared surfaces
 * outside this build's collision-safe scope; this file only ever ADDS new
 * exports. It re-exports `ApiError` from api-client.ts (read-only import)
 * for a consistent error shape, and mirrors that file's same
 * origin-relative fetch pattern (`NEXT_PUBLIC_API_URL` override, same-origin
 * default for the static export served by the FastAPI backend).
 */
import { ApiError } from "./api-client";

export { ApiError };

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

async function copilotFetch<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, init);
  } catch {
    throw new ApiError("Network error — check your connection", 0);
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(body.detail || `API error: ${res.status}`, res.status);
  }
  return res.json();
}

/** Which console page a copilot question was asked from, if any. */
export type CopilotPage = "runs" | "intake" | "tools" | null;

/** Optional console context attached to the FIRST message of a session —
 * follow-ups (POST /api/copilot/continue) don't re-send this; the session
 * already carries it from the first turn. */
export interface CopilotContext {
  page?: CopilotPage;
  run_id?: string | null;
  file_id?: string | null;
}

export interface CopilotAskResponse {
  reply: string;
  session_id: string;
  model: string;
}

/** Start a NEW copilot session. */
export async function copilotAsk(params: {
  prompt: string;
  model?: string;
  context?: CopilotContext;
}) {
  return copilotFetch<CopilotAskResponse>("/api/copilot/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      prompt: params.prompt,
      model: params.model ?? null,
      context: params.context ?? null,
    }),
  });
}

/** Continue an existing copilot session (follow-up turn). */
export async function copilotContinue(params: {
  sessionId: string;
  prompt: string;
  model?: string;
}) {
  return copilotFetch<CopilotAskResponse>("/api/copilot/continue", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: params.sessionId,
      prompt: params.prompt,
      model: params.model ?? null,
    }),
  });
}

export interface CopilotHealth {
  reachable: boolean;
  connected_providers: number;
  detail?: string | null;
}

export async function copilotHealth() {
  return copilotFetch<CopilotHealth>("/api/copilot/health");
}

/** One connected OpenCode provider's model ids — never carries a "key"
 * field; the backend redacts by construction (see app/service/copilot.py
 * list_models() docstring), not by stripping. */
export interface CopilotModelGroup {
  provider: string;
  label: string;
  models: string[];
}

export async function copilotModels() {
  return copilotFetch<CopilotModelGroup[]>("/api/copilot/models");
}

/** What kind of console context a preset expects attached, if any. */
export type CopilotPresetWants = "file" | "run" | null;

export interface CopilotPreset {
  id: string;
  label: string;
  prompt: string;
  wants_context: CopilotPresetWants;
}

export async function copilotPresets() {
  return copilotFetch<CopilotPreset[]>("/api/copilot/presets");
}
