"use client";

import { useCompletion } from "@ai-sdk/react";
import { useEffect, useState } from "react";
import { LLM_PROBE_URL } from "@/lib/config";
import { api, type Provider } from "@/lib/api";

type ProbeDef = { prompt: string; description: string };

export default function PlaygroundPage() {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [provider, setProvider] = useState("");
  const [model, setModel] = useState("");
  const [models, setModels] = useState<string[]>([]);
  const [modelsLoading, setModelsLoading] = useState(false);
  const [maxTokens, setMaxTokens] = useState(500);
  const [temperature, setTemperature] = useState(0);
  const [reasoningEffort, setReasoningEffort] = useState<string>("");
  const [probeDefs, setProbeDefs] = useState<Record<string, ProbeDef>>({});
  const [lastMeta, setLastMeta] = useState<string | null>(null);

  const { completion, complete, input, setInput, isLoading, error, stop } = useCompletion({
    api: `${LLM_PROBE_URL}/playground/stream`,
    streamProtocol: "text",
  });

  useEffect(() => {
    api.providers().then((p) => {
      setProviders(p);
      const first = p.find((x) => x.configured);
      if (first) setProvider(first.name);
    }).catch(() => {});
    fetch(`${LLM_PROBE_URL}/probes`).then((r) => r.json()).then(setProbeDefs).catch(() => {});
  }, []);

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
    complete(input, {
      body: {
        provider,
        model,
        max_tokens: maxTokens,
        temperature,
        reasoning_effort: reasoningEffort || null,
        label: "frontend",
      },
    }).then(() => setLastMeta(`${((performance.now() - t0) / 1000).toFixed(2)}s`));
  }

  return (
    <div className="max-w-4xl mx-auto px-6 py-8 flex flex-col gap-5">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Playground</h1>
        <p className="text-sm text-text-dim mt-1">
          Any provider, any model, live — streamed straight from the model, no scoring.
          Use <code className="text-accent">reasoning_effort=none</code> if a model truncates or comes back empty.
        </p>
      </div>

      <div className="flex flex-wrap gap-3">
        <select
          value={provider}
          onChange={(e) => setProvider(e.target.value)}
          className="bg-surface border border-border rounded-lg px-3 py-2 text-sm font-mono"
        >
          {providers.map((p) => (
            <option key={p.name} value={p.name} disabled={!p.configured}>
              {p.name}{!p.configured ? " (no key)" : ""}
            </option>
          ))}
        </select>

        <input
          list="model-options"
          value={model}
          onChange={(e) => setModel(e.target.value)}
          placeholder={modelsLoading ? "loading catalog…" : "model id"}
          className="bg-surface border border-border rounded-lg px-3 py-2 text-sm font-mono flex-1 min-w-[240px]"
        />
        <datalist id="model-options">
          {models.map((m) => (
            <option key={m} value={m} />
          ))}
        </datalist>
      </div>

      {Object.keys(probeDefs).length > 0 && (
        <div className="flex flex-wrap gap-2">
          {Object.entries(probeDefs).map(([name, def]) => (
            <button
              key={name}
              onClick={() => setInput(def.prompt)}
              className="text-xs font-mono border border-border rounded-full px-3 py-1 text-text-dim hover:border-accent hover:text-accent transition-colors"
              title={def.description}
            >
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
        className="bg-surface border border-border rounded-lg px-3 py-2 text-sm font-mono resize-y"
      />

      <div className="flex flex-wrap items-center gap-3">
        <label className="text-xs text-text-faint flex items-center gap-2">
          max_tokens
          <input
            type="number"
            value={maxTokens}
            onChange={(e) => setMaxTokens(Number(e.target.value))}
            className="w-20 bg-surface border border-border rounded px-2 py-1 text-sm font-mono"
          />
        </label>
        <label className="text-xs text-text-faint flex items-center gap-2">
          temperature
          <input
            type="number"
            step="0.1"
            value={temperature}
            onChange={(e) => setTemperature(Number(e.target.value))}
            className="w-16 bg-surface border border-border rounded px-2 py-1 text-sm font-mono"
          />
        </label>
        <label className="text-xs text-text-faint flex items-center gap-2">
          reasoning_effort
          <select
            value={reasoningEffort}
            onChange={(e) => setReasoningEffort(e.target.value)}
            className="bg-surface border border-border rounded px-2 py-1 text-sm font-mono"
          >
            <option value="">(unset)</option>
            <option value="none">none</option>
            <option value="low">low</option>
            <option value="medium">medium</option>
            <option value="high">high</option>
          </select>
        </label>

        <div className="flex-1" />

        {isLoading ? (
          <button onClick={stop} className="bg-bad text-white rounded-lg px-4 py-2 text-sm font-medium">
            Stop
          </button>
        ) : (
          <button
            onClick={run}
            disabled={!provider || !model || !input.trim()}
            className="bg-accent text-bg rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-40"
          >
            Run
          </button>
        )}
      </div>

      {error && (
        <div className="text-bad text-sm border border-bad/40 bg-bad-soft rounded-lg px-3 py-2">
          {error.message}
        </div>
      )}

      <div className="border border-border rounded-lg bg-surface min-h-[160px] p-4 font-mono text-sm whitespace-pre-wrap">
        {completion || <span className="text-text-faint">Output will stream here.</span>}
        {isLoading && <span className="animate-pulse text-accent">▌</span>}
      </div>
      {lastMeta && !isLoading && <div className="text-xs text-text-faint">{lastMeta}</div>}
    </div>
  );
}
