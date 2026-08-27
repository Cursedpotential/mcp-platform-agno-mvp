import { LLM_PROBE_URL } from "./config";

export type Provider = { name: string; configured: boolean; base_url: string };

export type BoardRow = {
  provider: string;
  model: string;
  tier0_ok: boolean;
  tier0_latency: number | null;
  tier0_note: string;
  tier0_full_content: string | null;
  tier0_full_error: string | null;
  tier0_patched: boolean;
  tool_use_ok?: boolean;
  tool_use_latency?: number;
  summarization_ok?: boolean;
  summarization_latency?: number;
  summarization_detail?: { hits?: string[]; missed?: string[]; content?: string; word_count?: number };
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

async function get<T>(path: string): Promise<T> {
  const r = await fetch(`${LLM_PROBE_URL}${path}`, { cache: "no-store" });
  if (!r.ok) throw new Error(`${path} -> ${r.status}`);
  return r.json();
}

export const api = {
  providers: () => get<Provider[]>("/providers"),
  models: (provider: string) => get<{ id: string }[]>(`/providers/${provider}/models`),
  board: () => get<BoardRow[]>("/results/board"),
  summary: () => get<Summary>("/results/summary"),
};
