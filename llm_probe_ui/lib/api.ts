import { LLM_PROBE_URL } from "./config";

export type Provider = {
  name: string;
  configured: boolean;
  base_url: string;
  supports_penalty_params: boolean | null;
  is_custom: boolean;
};

export type ProbeVariant = { key: string; label: string; prompt: string };
export type ProbeDef = { prompt: string; description: string; variants: ProbeVariant[] };
export type RetryPreset = { key: string; label: string };
export type ProbesCatalog = { probes: Record<string, ProbeDef>; retry_presets: RetryPreset[] };

export type BoardRow = {
  provider: string;
  model: string;
  tier0_ok: boolean;
  tier0_status: number | null;
  tier0_latency: number | null;
  tier0_note: string;
  tier0_full_content: string | null;
  tier0_full_error: string | null;
  tier0_patched: boolean;
  tool_use_ok?: boolean;
  tool_use_latency?: number;
  summarization_ok?: boolean;
  summarization_latency?: number;
  summarization_detail?: { hits?: string[]; missed?: string[]; content?: string; word_count?: number; key_facts_hit?: number };
  instruction_following_ok?: boolean;
  instruction_following_latency?: number;
  instruction_following_detail?: { content?: string; word_count?: number };
};

export type Summary = {
  total_models: number;
  live: number;
  tier1_tested: number;
  tool_use_pass: number;
  summarization_pass: number;
  instruction_following_pass: number;
  pass_all_three: number;
};

export type HistoryRow = {
  run_id: number;
  tier: string;
  probe: string;
  ok: boolean;
  http_status: number | null;
  latency_s: number | null;
  created_at: string;
  prompt_used: string | null;
  max_tokens_used: number | null;
  reasoning_effort_used: string | null;
  content: string | null;
  error: string | null;
  key_facts_hit?: number;
  hits?: string[];
  missed?: string[];
  word_count?: number;
};

export type RetryParams = {
  max_tokens?: number;
  temperature?: number;
  reasoning_effort?: string | null;
  top_p?: number;
  presence_penalty?: number;
  frequency_penalty?: number;
  prompt_override?: string;
};

async function get<T>(path: string): Promise<T> {
  const r = await fetch(`${LLM_PROBE_URL}${path}`, { cache: "no-store" });
  if (!r.ok) throw new Error(`${path} -> ${r.status}: ${await r.text().catch(() => "")}`);
  return r.json();
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const r = await fetch(`${LLM_PROBE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) throw new Error(`${path} -> ${r.status}: ${await r.text().catch(() => "")}`);
  return r.json();
}

async function del<T>(path: string): Promise<T> {
  const r = await fetch(`${LLM_PROBE_URL}${path}`, { method: "DELETE" });
  if (!r.ok) throw new Error(`${path} -> ${r.status}: ${await r.text().catch(() => "")}`);
  return r.json();
}

export const api = {
  providers: () => get<Provider[]>("/providers"),
  addProvider: (body: { name: string; base_url: string; api_key: string; models_url?: string; models_auth?: string; supports_penalty_params?: boolean | null }) =>
    post<Provider>("/providers", body),
  deleteProvider: (name: string) => del<{ deleted: string }>(`/providers/${encodeURIComponent(name)}`),
  models: (provider: string) => get<{ id: string }[]>(`/providers/${provider}/models`),
  trackedModels: (provider: string) => get<{ provider: string; model: string; note: string | null }[]>(`/providers/${provider}/tracked-models`),
  trackModel: (provider: string, model: string) => post(`/providers/${provider}/tracked-models/${encodeURIComponent(model)}`),
  untrackModel: (provider: string, model: string) => del(`/providers/${provider}/tracked-models/${encodeURIComponent(model)}`),
  board: () => get<BoardRow[]>("/results/board"),
  summary: () => get<Summary>("/results/summary"),
  history: (provider: string, model: string, probe?: string) =>
    get<HistoryRow[]>(`/results/history?provider=${encodeURIComponent(provider)}&model=${encodeURIComponent(model)}${probe ? `&probe=${probe}` : ""}`),
  probes: () => get<ProbesCatalog>("/probes"),
  retryProbe: (provider: string, model: string, probe: string, params: RetryParams, run_note?: string) =>
    post<Record<string, unknown>>("/probe/run", { provider, model, probe, persist: true, run_note, ...params }),
};
