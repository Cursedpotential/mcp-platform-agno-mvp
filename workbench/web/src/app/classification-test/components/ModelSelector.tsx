'use client';

// Byline: Codex · GPT-5 · 2026-08-16

import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  comparisonApi,
  ProviderConfig,
  ProviderInfo,
  ProviderName,
  ProvidersListResponse,
} from '@/lib/classification-api';

const PROVIDER_LABELS: Record<ProviderName, string> = {
  ollama: 'Ollama',
  nvidia: 'NVIDIA NIM',
  openrouter: 'OpenRouter',
  anthropic: 'Anthropic',
  openai: 'OpenAI',
  google: 'Google',
  groq: 'Groq',
  portkey: 'Portkey Gateway',
};

interface ModelSelectorProps {
  providers: ProviderConfig[];
  onChange: (providers: ProviderConfig[]) => void;
}

function modelForProvider(info: ProviderInfo | undefined): string | undefined {
  if (!info) return undefined;
  if (info.models.includes(info.default_model)) return info.default_model;
  return info.models[0] ?? info.default_model;
}

export function reconcileProviderSelections(
  providers: ProviderConfig[],
  catalog: ProviderInfo[],
): ProviderConfig[] {
  const byProvider = new Map(catalog.map((info) => [info.provider, info]));
  return providers.map((config) => {
    const info = byProvider.get(config.provider);
    if (!info || info.models.length === 0) return config;
    if (config.model_id && info.models.includes(config.model_id)) return config;
    return { ...config, model_id: modelForProvider(info) };
  });
}

export function ModelSelector({ providers, onChange }: ModelSelectorProps) {
  const [catalogResponse, setCatalogResponse] = useState<ProvidersListResponse | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(true);
  const [catalogError, setCatalogError] = useState<string | null>(null);

  const catalog = useMemo(() => catalogResponse?.providers ?? [], [catalogResponse]);
  const byProvider = useMemo(
    () => new Map(catalog.map((info) => [info.provider, info])),
    [catalog],
  );

  const loadCatalog = useCallback(async (refresh: boolean) => {
    setIsRefreshing(true);
    setCatalogError(null);
    try {
      setCatalogResponse(await comparisonApi.getProviders(refresh));
    } catch (error) {
      setCatalogError(error instanceof Error ? error.message : 'Model catalog refresh failed');
    } finally {
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    comparisonApi.getProviders(false)
      .then((response) => {
        if (active) setCatalogResponse(response);
      })
      .catch((error: unknown) => {
        if (active) {
          setCatalogError(error instanceof Error ? error.message : 'Model catalog load failed');
        }
      })
      .finally(() => {
        if (active) setIsRefreshing(false);
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (catalog.length === 0) return;
    const reconciled = reconcileProviderSelections(providers, catalog);
    if (JSON.stringify(reconciled) !== JSON.stringify(providers)) {
      onChange(reconciled);
    }
  }, [catalog, onChange, providers]);

  const updateProvider = (index: number, update: Partial<ProviderConfig>) => {
    const next = [...providers];
    next[index] = { ...next[index], ...update };
    onChange(next);
  };

  const handleProviderChange = (index: number, provider: ProviderName) => {
    updateProvider(index, {
      provider,
      model_id: modelForProvider(byProvider.get(provider)),
    });
  };

  const addProvider = () => {
    if (providers.length >= 5) return;
    const selected = new Set(providers.map((config) => config.provider));
    const candidate = catalog.find((info) => info.available && !selected.has(info.provider))
      ?? catalog.find((info) => info.available)
      ?? catalog[0];
    const provider = candidate?.provider ?? 'portkey';
    onChange([
      ...providers,
      {
        provider,
        model_id: modelForProvider(candidate),
        temperature: 0,
        max_tokens: 1024,
      },
    ]);
  };

  const removeProvider = (index: number) => {
    if (providers.length <= 1) return;
    onChange(providers.filter((_, itemIndex) => itemIndex !== index));
  };

  return (
    <div className="space-y-4 rounded-lg bg-white p-4 shadow">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-semibold text-gray-900">Model providers</h3>
          <p className="mt-1 text-xs text-gray-500">
            Portkey calls are traced. Direct providers are diagnostic bypasses.
          </p>
        </div>
        <div className="flex gap-3 text-sm font-medium">
          <button
            type="button"
            onClick={() => void loadCatalog(true)}
            disabled={isRefreshing}
            className="text-blue-600 hover:text-blue-700 disabled:text-gray-400"
          >
            {isRefreshing ? 'Refreshing…' : 'Refresh models'}
          </button>
          <button
            type="button"
            onClick={addProvider}
            disabled={providers.length >= 5}
            className="text-blue-600 hover:text-blue-700 disabled:text-gray-400"
          >
            + Add
          </button>
        </div>
      </div>

      {catalogError && (
        <div role="alert" className="rounded border border-red-200 bg-red-50 p-2 text-sm text-red-700">
          {catalogError}
        </div>
      )}

      {catalogResponse && (
        <p className="text-xs text-gray-500">
          Catalog refreshed {new Date(catalogResponse.refreshed_at).toLocaleString()}
          {catalogResponse.cache_hit ? ' (cached)' : ''}.
        </p>
      )}

      <div className="space-y-4">
        {providers.map((providerConfig, index) => {
          const info = byProvider.get(providerConfig.provider);
          const modelListId = `model-options-${index}`;
          const routeLabel = providerConfig.provider === 'portkey'
            ? 'Gateway-traced'
            : 'Direct diagnostic bypass';

          return (
            <div key={index} className="space-y-3 rounded-lg border border-gray-200 p-4">
              <div className="flex items-center justify-between gap-3">
                <select
                  aria-label={`Provider ${index + 1}`}
                  value={providerConfig.provider}
                  onChange={(event) => handleProviderChange(index, event.target.value as ProviderName)}
                  className="rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {(catalog.length > 0 ? catalog : Object.keys(PROVIDER_LABELS).map((provider) => ({ provider }))).map((entry) => {
                    const provider = entry.provider as ProviderName;
                    const providerInfo = byProvider.get(provider);
                    return (
                      <option key={provider} value={provider}>
                        {PROVIDER_LABELS[provider]}{providerInfo && !providerInfo.available ? ' — unavailable' : ''}
                      </option>
                    );
                  })}
                </select>

                {providers.length > 1 && (
                  <button
                    type="button"
                    onClick={() => removeProvider(index)}
                    className="text-sm font-medium text-red-500 hover:text-red-700"
                  >
                    Remove
                  </button>
                )}
              </div>

              <div className="text-xs">
                <span className={providerConfig.provider === 'portkey' ? 'text-green-700' : 'text-amber-700'}>
                  {routeLabel}
                </span>
                <span className="text-gray-500">
                  {' · '}{info?.models.length ?? 0} live models
                </span>
              </div>

              {info?.error && (
                <p className="rounded bg-amber-50 p-2 text-xs text-amber-800">{info.error}</p>
              )}

              <div className="grid grid-cols-2 gap-3">
                <div className="col-span-2">
                  <label htmlFor={`model-${index}`} className="mb-1 block text-xs font-medium text-gray-500">
                    Model
                  </label>
                  <input
                    id={`model-${index}`}
                    list={modelListId}
                    value={providerConfig.model_id ?? ''}
                    onChange={(event) => updateProvider(index, { model_id: event.target.value })}
                    placeholder={info?.default_model ?? 'Refresh or enter a model ID'}
                    className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                  <datalist id={modelListId}>
                    {info?.models.map((model) => <option key={model} value={model} />)}
                  </datalist>
                </div>

                <div>
                  <label htmlFor={`temperature-${index}`} className="mb-1 block text-xs font-medium text-gray-500">
                    Temperature
                  </label>
                  <input
                    id={`temperature-${index}`}
                    type="number"
                    value={providerConfig.temperature ?? 0}
                    onChange={(event) => updateProvider(index, { temperature: Number(event.target.value) })}
                    min={0}
                    max={2}
                    step={0.1}
                    className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>

                <div>
                  <label htmlFor={`max-tokens-${index}`} className="mb-1 block text-xs font-medium text-gray-500">
                    Max tokens
                  </label>
                  <input
                    id={`max-tokens-${index}`}
                    type="number"
                    value={providerConfig.max_tokens ?? 1024}
                    onChange={(event) => updateProvider(index, { max_tokens: Number(event.target.value) })}
                    min={1}
                    max={8192}
                    step={1}
                    className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
