/** API client for classification and sentiment analysis.
 * Byline: Codex · GPT-5 · 2026-08-16
 */

const API_BASE = import.meta.env.VITE_API_BASE || '/api';

export type ProviderName = 'ollama' | 'nvidia' | 'openrouter' | 'anthropic' | 'openai' | 'google' | 'groq' | 'portkey';

export interface ProviderInfo {
  provider: ProviderName;
  available: boolean;
  default_model: string;
  models: string[];
  source: 'live' | 'unconfigured' | 'error';
  error?: string;
}

export interface ProvidersListResponse {
  providers: ProviderInfo[];
  refreshed_at: string;
  cache_hit: boolean;
}

export interface ClassificationRequest {
  text: string;
  categories: string[];
  provider: ProviderName;
  model_id?: string;
  temperature?: number;
  max_tokens?: number;
  system_prompt?: string;
}

export interface ClassificationResponse {
  category: string;
  confidence: number;
  reasoning: string;
  raw_response: string;
  provider: ProviderName;
  model_id: string;
  latency_ms: number;
  timestamp: string;
}

export interface BatchClassificationRequest {
  texts: string[];
  categories: string[];
  provider: ProviderName;
  model_id?: string;
  temperature?: number;
  max_tokens?: number;
  system_prompt?: string;
}

export interface BatchClassificationResponse {
  results: ClassificationResponse[];
  total_latency_ms: number;
  provider: ProviderName;
  model_id: string;
}

export interface SentimentRequest {
  text: string;
  provider: ProviderName;
  model_id?: string;
  temperature?: number;
  max_tokens?: number;
  include_emotions?: boolean;
}

export interface SentimentResponse {
  sentiment: 'positive' | 'negative' | 'neutral' | 'mixed';
  score: number;
  emotions: Record<string, number>;
  reasoning: string;
  raw_response: string;
  provider: ProviderName;
  model_id: string;
  latency_ms: number;
  timestamp: string;
}

export interface BatchSentimentRequest {
  texts: string[];
  provider: ProviderName;
  model_id?: string;
  temperature?: number;
  max_tokens?: number;
  include_emotions?: boolean;
}

export interface BatchSentimentResponse {
  results: SentimentResponse[];
  total_latency_ms: number;
  provider: ProviderName;
  model_id: string;
}

export interface ProviderConfig {
  provider: ProviderName;
  model_id?: string;
  temperature?: number;
  max_tokens?: number;
}

export interface ComparisonRequest {
  texts: string[];
  categories: string[];
  providers: ProviderConfig[];
  include_sentiment?: boolean;
  system_prompt?: string;
}

export interface ComparisonResult {
  text_index: number;
  text_preview: string;
  provider: ProviderName;
  model_id: string;
  classification?: ClassificationResponse;
  sentiment?: SentimentResponse;
  latency_ms: number;
}

export interface ComparisonSummary {
  total_texts: number;
  total_providers: number;
  avg_latency_ms: number;
  category_agreement_rate: number;
  sentiment_agreement_rate: number;
}

export interface ComparisonResponse {
  results: ComparisonResult[];
  summary: ComparisonSummary;
  timestamp: string;
}

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${url}`, {
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
    ...options,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

export const classificationApi = {
  classify: (request: ClassificationRequest) =>
    fetchJson<ClassificationResponse>('/classification/classify', {
      method: 'POST',
      body: JSON.stringify(request),
    }),

  batchClassify: (request: BatchClassificationRequest) =>
    fetchJson<BatchClassificationResponse>('/classification/batch', {
      method: 'POST',
      body: JSON.stringify(request),
    }),

  getCategories: () =>
    fetchJson<{ categories: string[] }>('/classification/categories'),

  getProviders: (refresh = false) =>
    fetchJson<ProvidersListResponse>(`/classification/providers?refresh=${refresh}`),
};

export const sentimentApi = {
  analyze: (request: SentimentRequest) =>
    fetchJson<SentimentResponse>('/sentiment/analyze', {
      method: 'POST',
      body: JSON.stringify(request),
    }),

  batchAnalyze: (request: BatchSentimentRequest) =>
    fetchJson<BatchSentimentResponse>('/sentiment/batch', {
      method: 'POST',
      body: JSON.stringify(request),
    }),
};

export const comparisonApi = {
  run: (request: ComparisonRequest) =>
    fetchJson<ComparisonResponse>('/comparison/run', {
      method: 'POST',
      body: JSON.stringify(request),
    }),

  getProviders: (refresh = false) =>
    fetchJson<ProvidersListResponse>(`/comparison/providers?refresh=${refresh}`),

  export: (runId: string, format: 'json' | 'csv', includeRaw = false) =>
    fetch(`${API_BASE}/comparison/export?format=${format}&include_raw=${includeRaw}&comparison_id=${runId}`, {
      method: 'POST',
    }).then(res => res.blob()),

  listRuns: () =>
    fetchJson<{ runs: string[] }>('/comparison/runs'),

  getRun: (runId: string) =>
    fetchJson<ComparisonResponse>(`/comparison/runs/${runId}`),
};
