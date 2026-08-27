"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type Provider } from "@/lib/api";

export default function SettingsPage() {
  const { data: providers = [] } = useQuery<Provider[]>({ queryKey: ["providers"], queryFn: api.providers });
  const [expanded, setExpanded] = useState<string | null>(null);
  const [showAddForm, setShowAddForm] = useState(false);

  return (
    <div className="max-w-4xl mx-auto px-6 py-8 flex flex-col gap-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
          <p className="text-sm text-text-dim mt-1">Providers, live catalogs, and which models actually get tracked on the board.</p>
        </div>
        <button onClick={() => setShowAddForm((s) => !s)} className="bg-accent text-bg rounded-lg px-4 py-2 text-sm font-medium shadow-card">
          {showAddForm ? "Cancel" : "+ Add provider"}
        </button>
      </div>

      {showAddForm && <AddProviderForm onDone={() => setShowAddForm(false)} />}

      <div className="flex flex-col gap-3">
        {providers.map((p) => (
          <ProviderCard key={p.name} provider={p} expanded={expanded === p.name} onToggle={() => setExpanded(expanded === p.name ? null : p.name)} />
        ))}
      </div>
    </div>
  );
}

function AddProviderForm({ onDone }: { onDone: () => void }) {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [modelsUrl, setModelsUrl] = useState("");
  const [penaltySupport, setPenaltySupport] = useState<"unknown" | "yes" | "no">("unknown");

  const mutation = useMutation({
    mutationFn: () =>
      api.addProvider({
        name: name.trim(),
        base_url: baseUrl.trim(),
        api_key: apiKey,
        models_url: modelsUrl.trim() || undefined,
        supports_penalty_params: penaltySupport === "unknown" ? null : penaltySupport === "yes",
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["providers"] });
      onDone();
    },
  });

  return (
    <div className="panel p-4 flex flex-col gap-3">
      <div className="text-sm text-text-dim">
        The key is encrypted at rest (pgcrypto) and only ever decrypted server-side at call time — it's never stored in plaintext or returned by any
        API response after this.
      </div>
      <div className="grid sm:grid-cols-2 gap-3">
        <Field label="name" value={name} onChange={setName} placeholder="e.g. together-ai" />
        <Field label="base_url" value={baseUrl} onChange={setBaseUrl} placeholder="https://api.example.com/v1" />
        <Field label="api_key" value={apiKey} onChange={setApiKey} placeholder="sk-…" type="password" />
        <Field label="models_url (optional)" value={modelsUrl} onChange={setModelsUrl} placeholder="defaults to base_url + /models" />
      </div>
      <label className="flex flex-col gap-1 text-xs text-text-faint max-w-xs">
        presence/frequency_penalty support
        <select value={penaltySupport} onChange={(e) => setPenaltySupport(e.target.value as typeof penaltySupport)} className="field px-2 py-1.5 text-sm">
          <option value="unknown">unconfirmed (hide the controls)</option>
          <option value="yes">confirmed supported</option>
          <option value="no">confirmed rejected</option>
        </select>
      </label>
      <div className="flex items-center gap-3">
        <button
          onClick={() => mutation.mutate()}
          disabled={!name || !baseUrl || !apiKey || mutation.isPending}
          className="bg-accent text-bg rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-40"
        >
          {mutation.isPending ? "Adding…" : "Add provider"}
        </button>
        {mutation.isError && <span className="text-bad text-xs">{(mutation.error as Error).message}</span>}
      </div>
    </div>
  );
}

function Field({ label, value, onChange, placeholder, type = "text" }: { label: string; value: string; onChange: (v: string) => void; placeholder?: string; type?: string }) {
  return (
    <label className="flex flex-col gap-1 text-xs text-text-faint">
      {label}
      <input type={type} value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} className="field px-3 py-1.5 text-sm font-mono" />
    </label>
  );
}

function ProviderCard({ provider, expanded, onToggle }: { provider: Provider; expanded: boolean; onToggle: () => void }) {
  const qc = useQueryClient();
  const { data: catalog, refetch: pullModels, isFetching: pulling } = useQuery({
    queryKey: ["catalog", provider.name],
    queryFn: () => api.models(provider.name),
    enabled: false,
  });
  const { data: tracked = [] } = useQuery({
    queryKey: ["tracked", provider.name],
    queryFn: () => api.trackedModels(provider.name),
    enabled: expanded,
  });
  const trackedIds = new Set(tracked.map((t) => t.model));

  const trackMutation = useMutation({
    mutationFn: ({ model, track }: { model: string; track: boolean }) =>
      track ? api.trackModel(provider.name, model) : api.untrackModel(provider.name, model),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tracked", provider.name] }),
  });

  const deleteMutation = useMutation({
    mutationFn: () => api.deleteProvider(provider.name),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["providers"] }),
  });

  return (
    <div className="panel p-4">
      <div className="flex items-center justify-between cursor-pointer" onClick={onToggle}>
        <div className="flex items-center gap-2">
          <span className="font-mono text-sm font-semibold">{provider.name}</span>
          {provider.is_custom && <span className="text-[10px] uppercase bg-accent-soft text-accent rounded-full px-2 py-0.5">custom</span>}
          <span className={`text-[10px] uppercase rounded-full px-2 py-0.5 ${provider.configured ? "bg-good-soft text-good" : "bg-bad-soft text-bad"}`}>
            {provider.configured ? "configured" : "no key"}
          </span>
        </div>
        <span className="text-text-faint text-xs font-mono">{provider.base_url}</span>
      </div>

      {expanded && (
        <div className="mt-4 flex flex-col gap-3">
          <div className="flex items-center gap-2">
            <button onClick={() => pullModels()} disabled={pulling} className="chip">
              {pulling ? "pulling…" : "pull model list"}
            </button>
            {provider.is_custom && (
              <button
                onClick={() => confirm(`Delete provider ${provider.name}?`) && deleteMutation.mutate()}
                className="chip text-bad border-bad/40"
              >
                delete provider
              </button>
            )}
            {tracked.length > 0 && <span className="text-xs text-text-faint">{tracked.length} tracked</span>}
          </div>

          {tracked.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {tracked.map((t) => (
                <button key={t.model} onClick={() => trackMutation.mutate({ model: t.model, track: false })} data-active="true" className="chip">
                  {t.model} ✕
                </button>
              ))}
            </div>
          )}

          {catalog && (
            <div className="max-h-64 overflow-y-auto flex flex-col gap-1 border-t border-border pt-3">
              {catalog.map((m) => (
                <div key={m.id} className="flex items-center justify-between text-xs font-mono py-1 px-2 rounded hover:bg-surface-2">
                  <span>{m.id}</span>
                  <button
                    onClick={() => trackMutation.mutate({ model: m.id, track: !trackedIds.has(m.id) })}
                    className={`chip ${trackedIds.has(m.id) ? "" : ""}`}
                    data-active={trackedIds.has(m.id)}
                  >
                    {trackedIds.has(m.id) ? "tracked" : "track"}
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
