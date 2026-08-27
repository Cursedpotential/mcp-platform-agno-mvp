"use client";

import { useEffect, useMemo, useState } from "react";
import { api, type BoardRow, type Summary } from "@/lib/api";

const PROVIDER_ORDER = ["nim", "ollama_cloud", "openrouter", "google", "openai", "mistral", "groq", "cerebras"];

function Pill({ ok, label = ["LIVE", "DEAD"] }: { ok?: boolean; label?: [string, string] }) {
  if (ok === undefined) return <span className="text-text-faint">—</span>;
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-mono font-semibold ${
        ok ? "bg-good-soft text-good" : "bg-bad-soft text-bad"
      }`}
    >
      <span className="w-1.5 h-1.5 rounded-full bg-current" />
      {ok ? label[0] : label[1]}
    </span>
  );
}

function StatCard({ label, n, d }: { label: string; n: number; d: number }) {
  const pct = d ? (100 * n) / d : 0;
  return (
    <div className="bg-surface border border-border rounded-lg px-4 py-3">
      <div className="text-[11px] uppercase tracking-wide text-text-faint">{label}</div>
      <div className="font-mono text-xl font-semibold flex items-baseline gap-1 tabular">
        {n}
        <span className="text-xs text-text-faint font-normal">/ {d}</span>
      </div>
      <div className="mt-2 h-1 rounded-full bg-surface-3 overflow-hidden">
        <div className="h-full bg-good" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

export default function BoardPage() {
  const [rows, setRows] = useState<BoardRow[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState<"all" | "live" | "dead" | "tier1" | "untested">("all");
  const [expanded, setExpanded] = useState<string | null>(null);

  function load() {
    setLoading(true);
    Promise.all([api.board(), api.summary()])
      .then(([b, s]) => {
        setRows(b);
        setSummary(s);
      })
      .finally(() => setLoading(false));
  }

  useEffect(load, []);

  const filtered = useMemo(() => {
    return rows.filter((r) => {
      if (status === "live" && !r.tier0_ok) return false;
      if (status === "dead" && r.tier0_ok) return false;
      if (status === "tier1" && r.tool_use_ok === undefined) return false;
      if (status === "untested" && (!r.tier0_ok || r.tool_use_ok !== undefined)) return false;
      if (q && !`${r.provider} ${r.model}`.toLowerCase().includes(q.toLowerCase())) return false;
      return true;
    });
  }, [rows, q, status]);

  const grouped = useMemo(() => {
    const g: Record<string, BoardRow[]> = {};
    for (const p of PROVIDER_ORDER) g[p] = [];
    for (const r of filtered) (g[r.provider] ??= []).push(r);
    return g;
  }, [filtered]);

  return (
    <div className="max-w-6xl mx-auto px-6 py-8 flex flex-col gap-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Board</h1>
          <p className="text-sm text-text-dim mt-1">Live from casebible.llm_eval — every provider, every probe.</p>
        </div>
        <button onClick={load} className="text-xs text-text-dim hover:text-accent underline underline-offset-2">
          refresh
        </button>
      </div>

      {summary && (
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
          <StatCard label="Live" n={summary.live} d={summary.total_models} />
          <StatCard label="Tool use" n={summary.tool_use_pass} d={summary.tier1_tested} />
          <StatCard label="Summarize" n={summary.summarization_pass} d={summary.tier1_tested} />
          <StatCard label="Instructions" n={summary.instruction_following_pass} d={summary.tier1_tested} />
          <StatCard label="All three" n={summary.pass_all_three} d={summary.tier1_tested} />
        </div>
      )}

      <div className="flex flex-wrap gap-2 items-center sticky top-14 bg-bg/95 backdrop-blur py-2 z-[5]">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Filter model or provider…"
          className="bg-surface border border-border rounded-lg px-3 py-1.5 text-sm min-w-[220px]"
        />
        {(["all", "live", "dead", "tier1", "untested"] as const).map((s) => (
          <button
            key={s}
            onClick={() => setStatus(s)}
            className={`text-xs font-mono rounded-full px-3 py-1 border ${
              status === s ? "bg-accent text-bg border-accent font-semibold" : "border-border text-text-dim"
            }`}
          >
            {s}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="text-text-faint text-sm">loading…</div>
      ) : (
        <div className="border border-border rounded-lg bg-surface overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[11px] uppercase tracking-wide text-text-faint bg-surface-2 text-left">
                <th className="px-3 py-2">Model</th>
                <th className="px-3 py-2">Live</th>
                <th className="px-3 py-2">Tool use</th>
                <th className="px-3 py-2">Summarize</th>
                <th className="px-3 py-2">Instructions</th>
                <th className="px-3 py-2">Note</th>
              </tr>
            </thead>
            <tbody>
              {PROVIDER_ORDER.map((p) => {
                const list = grouped[p];
                if (!list?.length) return null;
                const live = list.filter((r) => r.tier0_ok).length;
                return (
                  <>
                    <tr key={p} className="bg-surface-2 border-t border-b border-border">
                      <td colSpan={6} className="px-3 py-1.5 font-mono text-[11px] uppercase tracking-wide text-text-dim">
                        {p} <span className="text-text-faint normal-case tracking-normal ml-2">{live}/{list.length} live</span>
                      </td>
                    </tr>
                    {list.map((r) => {
                      const key = `${r.provider}::${r.model}`;
                      const isOpen = expanded === key;
                      return (
                        <>
                          <tr
                            key={key}
                            onClick={() => setExpanded(isOpen ? null : key)}
                            className={`border-b border-border cursor-pointer hover:bg-surface-2 ${isOpen ? "bg-accent-soft" : ""}`}
                          >
                            <td className="px-3 py-1.5 font-mono text-xs">{r.model}</td>
                            <td className="px-3 py-1.5"><Pill ok={r.tier0_ok} /></td>
                            <td className="px-3 py-1.5"><Pill ok={r.tool_use_ok} label={["PASS", "FAIL"]} /></td>
                            <td className="px-3 py-1.5"><Pill ok={r.summarization_ok} label={["PASS", "FAIL"]} /></td>
                            <td className="px-3 py-1.5"><Pill ok={r.instruction_following_ok} label={["PASS", "FAIL"]} /></td>
                            <td className="px-3 py-1.5 text-xs text-text-faint truncate max-w-[280px]">{r.tier0_note}</td>
                          </tr>
                          {isOpen && (
                            <tr key={key + "-detail"} className="border-b border-border">
                              <td colSpan={6} className="bg-surface-2 px-6 py-4">
                                <div className="grid sm:grid-cols-2 gap-3">
                                  <div className="bg-surface border border-border rounded-lg p-3">
                                    <div className="text-[11px] uppercase text-text-faint mb-1">Liveness</div>
                                    <div className="font-mono text-xs whitespace-pre-wrap">
                                      {r.tier0_full_content || r.tier0_full_error || "(no detail)"}
                                    </div>
                                  </div>
                                  {r.summarization_detail && (
                                    <div className="bg-surface border border-border rounded-lg p-3">
                                      <div className="text-[11px] uppercase text-text-faint mb-1">Summarization</div>
                                      <div className="font-mono text-xs whitespace-pre-wrap mb-2">
                                        {r.summarization_detail.content || "(empty)"}
                                      </div>
                                      <div className="flex flex-wrap gap-1">
                                        {(r.summarization_detail.hits || []).map((f) => (
                                          <span key={f} className="text-[10px] font-mono bg-good-soft text-good rounded-full px-2 py-0.5">{f}</span>
                                        ))}
                                        {(r.summarization_detail.missed || []).map((f) => (
                                          <span key={f} className="text-[10px] font-mono bg-bad-soft text-bad rounded-full px-2 py-0.5 line-through opacity-80">{f}</span>
                                        ))}
                                      </div>
                                    </div>
                                  )}
                                  {r.instruction_following_detail && (
                                    <div className="bg-surface border border-border rounded-lg p-3">
                                      <div className="text-[11px] uppercase text-text-faint mb-1">Instruction following</div>
                                      <div className="font-mono text-xs whitespace-pre-wrap">
                                        {r.instruction_following_detail.content || "(empty)"}
                                      </div>
                                    </div>
                                  )}
                                </div>
                              </td>
                            </tr>
                          )}
                        </>
                      );
                    })}
                  </>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
