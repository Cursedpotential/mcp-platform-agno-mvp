"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type Provider, type ProbesCatalog, type RetryParams } from "@/lib/api";

const REASONING_OPTIONS = ["(unset)", "none", "low", "medium", "high"];

export function RetryPanel({
  provider,
  model,
  probe,
  providerMeta,
  onDone,
}: {
  provider: string;
  model: string;
  probe: string;
  providerMeta?: Provider;
  onDone?: () => void;
}) {
  const qc = useQueryClient();
  const { data: catalog } = useQuery<ProbesCatalog>({ queryKey: ["probes"], queryFn: api.probes });
  const variants = catalog?.probes[probe]?.variants ?? [];

  const [variantKey, setVariantKey] = useState("default");
  const [reasoning, setReasoning] = useState("(unset)");
  const [maxTokens, setMaxTokens] = useState(1000);
  const [temperature, setTemperature] = useState(0);
  const [topP, setTopP] = useState(1);
  const [presencePenalty, setPresencePenalty] = useState(0);
  const [frequencyPenalty, setFrequencyPenalty] = useState(0);
  const [lastResult, setLastResult] = useState<Record<string, unknown> | null>(null);

  const supportsPenalty = providerMeta?.supports_penalty_params === true;

  const mutation = useMutation({
    mutationFn: () => {
      const params: RetryParams = {
        max_tokens: maxTokens,
        temperature,
        top_p: topP !== 1 ? topP : undefined,
        reasoning_effort: reasoning === "(unset)" ? undefined : reasoning,
      };
      if (supportsPenalty) {
        if (presencePenalty !== 0) params.presence_penalty = presencePenalty;
        if (frequencyPenalty !== 0) params.frequency_penalty = frequencyPenalty;
      }
      const variant = variants.find((v) => v.key === variantKey);
      if (variant && variant.key !== "default") params.prompt_override = variant.prompt;
      return api.retryProbe(provider, model, probe, params, `retry via board (variant=${variantKey})`);
    },
    onSuccess: (result) => {
      setLastResult(result);
      qc.invalidateQueries({ queryKey: ["board"] });
      qc.invalidateQueries({ queryKey: ["summary"] });
      qc.invalidateQueries({ queryKey: ["history", provider, model] });
    },
  });

  function applyPreset(key: string) {
    if (key === "no_reasoning") setReasoning("none");
    else if (key === "bigger_budget") setMaxTokens((m) => Math.min(4000, m * 3));
    else if (key === "no_reasoning_bigger_budget") {
      setReasoning("none");
      setMaxTokens((m) => Math.min(4000, m * 3));
    } else if (key === "same") {
      setReasoning("(unset)");
      setMaxTokens(1000);
    }
  }

  const resultOk = lastResult?.ok as boolean | undefined;

  return (
    <div className="panel p-3 flex flex-col gap-3 mt-2">
      <div className="flex items-center justify-between">
        <span className="text-[11px] uppercase tracking-wide text-text-faint font-semibold">Retry this probe</span>
        {onDone && (
          <button onClick={onDone} className="text-text-faint hover:text-text text-xs">
            close
          </button>
        )}
      </div>

      {variants.length > 1 && (
        <div className="flex flex-wrap gap-1.5">
          {variants.map((v) => (
            <button
              key={v.key}
              onClick={() => setVariantKey(v.key)}
              data-active={variantKey === v.key}
              className="chip"
              title={v.prompt}
            >
              {v.label}
            </button>
          ))}
        </div>
      )}

      {catalog && (
        <div className="flex flex-wrap gap-1.5">
          {catalog.retry_presets.map((p) => (
            <button key={p.key} onClick={() => applyPreset(p.key)} className="chip">
              {p.label}
            </button>
          ))}
        </div>
      )}

      <div className="grid sm:grid-cols-2 gap-3">
        <SliderField label="max_tokens" value={maxTokens} min={50} max={4000} step={50} onChange={setMaxTokens} />
        <SliderField label="temperature" value={temperature} min={0} max={2} step={0.1} onChange={setTemperature} />
        <SliderField label="top_p" value={topP} min={0.05} max={1} step={0.05} onChange={setTopP} />
        <label className="flex flex-col gap-1 text-xs text-text-faint">
          reasoning_effort
          <select value={reasoning} onChange={(e) => setReasoning(e.target.value)} className="field px-2 py-1.5 text-sm">
            {REASONING_OPTIONS.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
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
        <div className="text-[11px] text-text-faint">
          {providerMeta.supports_penalty_params === false
            ? "presence/frequency_penalty hidden — this provider rejects them."
            : "presence/frequency_penalty hidden — support unconfirmed for this provider."}
        </div>
      )}

      <div className="flex items-center gap-3">
        <button
          onClick={() => mutation.mutate()}
          disabled={mutation.isPending}
          className="bg-accent text-bg rounded-lg px-4 py-1.5 text-sm font-medium disabled:opacity-50"
        >
          {mutation.isPending ? "Running…" : "Retry now"}
        </button>
        {mutation.isError && <span className="text-bad text-xs">{(mutation.error as Error).message}</span>}
        {lastResult && !mutation.isPending && (
          <span className={`text-xs font-mono ${resultOk ? "text-good" : "text-bad"}`}>
            {resultOk ? "PASS" : "FAIL"} · {String(lastResult.latency_s)}s
          </span>
        )}
      </div>

      {lastResult && (
        <div className="bg-surface-2 border border-border rounded-lg p-2.5 font-mono text-xs whitespace-pre-wrap max-h-40 overflow-y-auto">
          {(lastResult.content as string) || (lastResult.error as string) || "(empty)"}
        </div>
      )}
    </div>
  );
}

function SliderField({
  label,
  value,
  min,
  max,
  step,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (v: number) => void;
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
