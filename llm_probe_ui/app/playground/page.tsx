"use client";

import { useCompletion } from "@ai-sdk/react";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { LLM_PROBE_URL } from "@/lib/config";
import { api, type Provider, type ProbesCatalog } from "@/lib/api";

export default function PlaygroundPage() {
  const { data: providers = [] } = useQuery<Provider[]>({ queryKey: ["providers"], queryFn: api.providers });
  const { data: catalog } = useQuery<ProbesCatalog>({ queryKey: ["probes"], queryFn: api.probes });

  const [provider, setProvider] = useState("");
  const [model, setModel] = useState("");
  const [models, setModels] = useState<string[]>([]);
  const [modelsLoading, setModelsLoading] = useState(false);
  const [maxTokens, setMaxTokens] = useState(500);
  const [temperature, setTemperature] = useState(0);
  const [topP, setTopP] = useState(1);
  const [presencePenalty, setPresencePenalty] = useState(0);
  const [frequencyPenalty, setFrequencyPenalty] = useState(0);
  const [reasoningEffort, setReasoningEffort] = useState<string>("");
  const [lastMeta, setLastMeta] = useState<string | null>(null);

  const providerMeta = providers.find((p) => p.name === provider);
  const supportsPenalty = providerMeta?.supports_penalty_params === true;

  const { completion, complete, input, setInput, isLoading, error, stop } = useCompletion({
    api: `${LLM_PROBE_URL}/playground/stream`,
    streamProtocol: "text",
  });

  useEffect(() => {
    if (providers.length && !provider) {
      const first = providers.find((x) => x.configured);
      if (first) setProvider(first.name);
    }
  }, [providers, provider]);

  useEffect(() => {
    if (!provider) return;
    setModelsLoading(true);
    api.models(provider)
      .then((m) => setModels(m.map((x) => x.id)))
      .catch(() => setModels([]))
      .finally(() => setModelsLoading(false));
  }, [provider]);

  function run() {
    if (!provider || !model || !input.trim()) return;
    const t0 = performance.now();
    const body: Record<string, unknown> = {
      provider, model, max_tokens: maxTokens, temperature,
      reasoning_effort: reasoningEffort || null, label: "frontend",
    };
    if (topP !== 1) body.top_p = topP;
    if (supportsPenalty) {
      if (presencePenalty !== 0) body.presence_penalty = presencePenalty;
      if (frequencyPenalty !== 0) body.frequency_penalty = frequencyPenalty;
    }
    complete(input, { body }).then(() => setLastMeta(`${((performance.now() - t0) / 1000).toFixed(2)}s`));
  }

  return (
    <div className="max-w-4xl mx-auto px-6 py-8 flex flex-col gap-5">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Playground</h1>
        <p className="text-sm text-text-dim mt-1">
          Any provider, any model, live — streamed straight from the model, no scoring.
          Use <code className="text-accent">reasoning_effort=none</code> if a model truncates or comes back empty.
        </p>
      </div>

      <div className="panel p-4 flex flex-col gap-4">
        <div className="flex flex-wrap gap-3">
          <select value={provider} onChange={(e) => setProvider(e.target.value)} className="field px-3 py-2 text-sm font-mono">
            {providers.map((p) => (
              <option key={p.name} value={p.name} disabled={!p.configured}>
                {p.name}{!p.configured ? " (no key)" : ""}{p.is_custom ? " ★" : ""}
              </option>
            ))}
          </select>

          <input
            list="model-options"
            value={model}
            onChange={(e) => setModel(e.target.value)}
            placeholder={modelsLoading ? "loading catalog…" : "model id"}
            className="field px-3 py-2 text-sm font-mono flex-1 min-w-[240px]"
          />
          <datalist id="model-options">
            {models.map((m) => (
              <option key={m} value={m} />
            ))}
          </datalist>
        </div>

        {catalog && (
          <div className="flex flex-wrap gap-2">
            {Object.entries(catalog.probes).map(([name, def]) => (
              <button key={name} onClick={() => setInput(def.prompt)} className="chip" title={def.description}>
                {name}
              </button>
            ))}
          </div>
        )}

        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          rows={5}
          placeholder="Type a prompt…"
          className="field px-3 py-2 text-sm font-mono resize-y"
        />

        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
          <SliderField label="max_tokens" value={maxTokens} min={20} max={4000} step={20} onChange={setMaxTokens} />
          <SliderField label="temperature" value={temperature} min={0} max={2} step={0.1} onChange={setTemperature} />
          <SliderField label="top_p" value={topP} min={0.05} max={1} step={0.05} onChange={setTopP} />
          <label className="flex flex-col gap-1 text-xs text-text-faint">
            <span>reasoning_effort</span>
            <select value={reasoningEffort} onChange={(e) => setReasoningEffort(e.target.value)} className="field px-2 py-1.5 text-sm">
              <option value="">(unset)</option>
              <option value="none">none</option>
              <option value="low">low</option>
              <option value="medium">medium</option>
              <option value="high">high</option>
            </select>
          </label>
          {supportsPenalty && (
            <>
              <SliderField label="presence_penalty" value={presencePenalty} min={-2} max={2} step={0.1} onChange={setPresencePenalty} />
              <SliderField label="frequency_penalty" value={frequencyPenalty} min={-2} max={2} step={0.1} onChange={setFrequencyPenalty} />
            </>
          )}
        </div>
        {providerMeta && providerMeta.supports_penalty_params !== true && (
          <div className="text-[11px] text-text-faint -mt-2">
            presence/frequency_penalty hidden — {providerMeta.supports_penalty_params === false ? "this provider rejects them" : "support unconfirmed for this provider"}.
          </div>
        )}

        <div className="flex items-center gap-3">
          {isLoading ? (
            <button onClick={stop} className="bg-bad text-white rounded-lg px-4 py-2 text-sm font-medium shadow-card">
              Stop
            </button>
          ) : (
            <button
              onClick={run}
              disabled={!provider || !model || !input.trim()}
              className="bg-accent text-bg rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-40 shadow-card"
            >
              Run
            </button>
          )}
          {lastMeta && !isLoading && <span className="text-xs text-text-faint">{lastMeta}</span>}
        </div>
      </div>

      {error && <div className="text-bad text-sm border border-bad/40 bg-bad-soft rounded-lg px-3 py-2">{error.message}</div>}

      <div className="panel min-h-[160px] p-4 font-mono text-sm whitespace-pre-wrap">
        {completion || <span className="text-text-faint">Output will stream here.</span>}
        {isLoading && <span className="animate-pulse text-accent">▌</span>}
      </div>
    </div>
  );
}

function SliderField({
  label, value, min, max, step, onChange,
}: {
  label: string; value: number; min: number; max: number; step: number; onChange: (v: number) => void;
}) {
  return (
    <label className="flex flex-col gap-1 text-xs text-text-faint">
      <span className="flex justify-between">
        <span>{label}</span>
        <span className="text-text tabular font-mono">{value}</span>
      </span>
      <input type="range" min={min} max={max} step={step} value={value} onChange={(e) => onChange(Number(e.target.value))} className="accent-accent" />
    </label>
  );
}
