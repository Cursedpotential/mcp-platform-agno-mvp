"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, type BoardRow, type Provider, type Summary } from "@/lib/api";
import { RetryPanel } from "@/components/RetryPanel";
import { HistoryPanel } from "@/components/HistoryPanel";

const PROVIDER_ORDER = ["nim", "ollama_cloud", "openrouter", "google", "openai", "mistral", "groq", "cerebras"];
const PROBES = ["tool_use", "summarization", "instruction_following"] as const;

function gradedPill(ok: boolean | undefined, fraction?: number, label: [string, string] = ["PASS", "FAIL"]) {
  if (ok === undefined) return <span className="text-text-faint">—</span>;
  let cls = "bg-bad-soft text-bad";
  let text = label[1];
  if (ok) {
    if (fraction === undefined || fraction >= 1) {
      cls = "bg-good-soft text-good";
      text = fraction !== undefined ? "FULL" : label[0];
    } else {
      cls = "bg-warn-soft text-warn";
      text = "PARTIAL";
    }
  }
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-mono font-semibold ${cls}`}>
      <span className="w-1.5 h-1.5 rounded-full bg-current" />
      {text}
    </span>
  );
}

function StatCard({ label, n, d }: { label: string; n: number; d: number }) {
  const pct = d ? (100 * n) / d : 0;
  return (
    <div className="panel px-4 py-3">
      <div className="text-[11px] uppercase tracking-wide text-text-faint">{label}</div>
      <div className="font-mono text-xl font-semibold flex items-baseline gap-1 tabular mt-0.5">
        {n}
        <span className="text-xs text-text-faint font-normal">/ {d}</span>
      </div>
      <div className="mt-2 h-1 rounded-full bg-surface-3 overflow-hidden">
        <div className="h-full bg-good transition-all" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

export default function BoardPage() {
  const { data: rows = [], isLoading, refetch, isFetching } = useQuery<BoardRow[]>({ queryKey: ["board"], queryFn: api.board });
  const { data: summary } = useQuery<Summary>({ queryKey: ["summary"], queryFn: api.summary });
  const { data: providers = [] } = useQuery<Provider[]>({ queryKey: ["providers"], queryFn: api.providers });

  const [q, setQ] = useState("");
  const [status, setStatus] = useState<"all" | "live" | "dead" | "tier1" | "untested">("all");
  const [hiddenCodes, setHiddenCodes] = useState<Set<number>>(new Set());
  const [expandedRow, setExpandedRow] = useState<string | null>(null);
  const [openTool, setOpenTool] = useState<{ key: string; probe: string; mode: "retry" | "history" } | null>(null);

  const providerByName = useMemo(() => Object.fromEntries(providers.map((p) => [p.name, p])), [providers]);

  const statusCodeCounts = useMemo(() => {
    const m = new Map<number, number>();
    for (const r of rows) {
      if (!r.tier0_ok && r.tier0_status) m.set(r.tier0_status, (m.get(r.tier0_status) || 0) + 1);
    }
    return [...m.entries()].sort((a, b) => b[1] - a[1]);
  }, [rows]);

  const filtered = useMemo(() => {
    return rows.filter((r) => {
      if (status === "live" && !r.tier0_ok) return false;
      if (status === "dead" && r.tier0_ok) return false;
      if (status === "tier1" && r.tool_use_ok === undefined) return false;
      if (status === "untested" && (!r.tier0_ok || r.tool_use_ok !== undefined)) return false;
      if (!r.tier0_ok && r.tier0_status && hiddenCodes.has(r.tier0_status)) return false;
      if (q && !`${r.provider} ${r.model}`.toLowerCase().includes(q.toLowerCase())) return false;
      return true;
    });
  }, [rows, q, status, hiddenCodes]);

  const grouped = useMemo(() => {
    const g: Record<string, BoardRow[]> = {};
    for (const p of PROVIDER_ORDER) g[p] = [];
    for (const r of filtered) (g[r.provider] ??= []).push(r);
    return g;
  }, [filtered]);

  function toggleCode(code: number) {
    setHiddenCodes((prev) => {
      const next = new Set(prev);
      next.has(code) ? next.delete(code) : next.add(code);
      return next;
    });
  }

  return (
    <div className="max-w-6xl mx-auto px-6 py-8 flex flex-col gap-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Board</h1>
          <p className="text-sm text-text-dim mt-1">Live from casebible.llm_eval — every provider, every probe.</p>
        </div>
        <button
          onClick={() => refetch()}
          className="text-xs text-text-dim hover:text-accent underline underline-offset-2 disabled:opacity-50"
          disabled={isFetching}
        >
          {isFetching ? "refreshing…" : "refresh"}
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

      <div className="flex flex-col gap-2 sticky top-14 bg-bg/95 backdrop-blur-sm py-2 z-[5] -mx-6 px-6 border-b border-border">
        <div className="flex flex-wrap gap-2 items-center">
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filter model or provider…" className="field px-3 py-1.5 text-sm min-w-[220px]" />
          {(["all", "live", "dead", "tier1", "untested"] as const).map((s) => (
            <button key={s} onClick={() => setStatus(s)} data-active={status === s} className="chip">
              {s}
            </button>
          ))}
        </div>
        {statusCodeCounts.length > 0 && (
          <div className="flex flex-wrap gap-1.5 items-center">
            <span className="text-[11px] text-text-faint uppercase tracking-wide">hide status:</span>
            {statusCodeCounts.map(([code, n]) => (
              <button key={code} onClick={() => toggleCode(code)} data-active={hiddenCodes.has(code)} className="chip">
                {code} <span className="opacity-60">({n})</span>
              </button>
            ))}
          </div>
        )}
      </div>

      {isLoading ? (
        <div className="text-text-faint text-sm">loading…</div>
      ) : (
        <div className="panel overflow-x-auto">
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
                      const isOpen = expandedRow === key;
                      const untested = r.tier0_ok && r.tool_use_ok === undefined;
                      const summFrac = r.summarization_detail?.key_facts_hit !== undefined ? r.summarization_detail.key_facts_hit / 8 : undefined;
                      return (
                        <>
                          <tr
                            key={key}
                            onClick={() => setExpandedRow(isOpen ? null : key)}
                            className={`border-b border-border cursor-pointer hover:bg-surface-2 transition-colors ${isOpen ? "bg-accent-soft" : ""}`}
                          >
                            <td className="px-3 py-1.5 font-mono text-xs">
                              {r.model}
                              {untested && <span className="ml-2 text-[9px] uppercase bg-bad-soft text-bad rounded-full px-1.5 py-0.5">no tier-1</span>}
                            </td>
                            <td className="px-3 py-1.5">{gradedPill(r.tier0_ok)}</td>
                            <td className="px-3 py-1.5">{gradedPill(r.tool_use_ok)}</td>
                            <td className="px-3 py-1.5">{gradedPill(r.summarization_ok, summFrac)}</td>
                            <td className="px-3 py-1.5">{gradedPill(r.instruction_following_ok)}</td>
                            <td className="px-3 py-1.5 text-xs text-text-faint truncate max-w-[280px]">{r.tier0_note}</td>
                          </tr>
                          {isOpen && (
                            <tr key={key + "-detail"} className="border-b border-border">
                              <td colSpan={6} className="bg-surface-2 px-6 py-4">
                                <div className="grid sm:grid-cols-2 gap-3 mb-3">
                                  <DetailCard title="Liveness" ok={r.tier0_ok} body={r.tier0_full_content || r.tier0_full_error} />
                                  {r.summarization_detail && (
                                    <DetailCard title="Summarization" ok={r.summarization_ok} body={r.summarization_detail.content}>
                                      <div className="flex flex-wrap gap-1 mt-2">
                                        {(r.summarization_detail.hits || []).map((f) => (
                                          <span key={f} className="text-[10px] font-mono bg-good-soft text-good rounded-full px-2 py-0.5">{f}</span>
                                        ))}
                                        {(r.summarization_detail.missed || []).map((f) => (
                                          <span key={f} className="text-[10px] font-mono bg-bad-soft text-bad rounded-full px-2 py-0.5 line-through opacity-80">{f}</span>
                                        ))}
                                      </div>
                                    </DetailCard>
                                  )}
                                  {r.instruction_following_detail && (
                                    <DetailCard title="Instruction following" ok={r.instruction_following_ok} body={r.instruction_following_detail.content} />
                                  )}
                                </div>

                                <div className="flex flex-wrap gap-1.5 mb-2">
                                  {(["liveness", ...PROBES] as const).map((probe) => (
                                    <div key={probe} className="flex gap-1">
                                      <button
                                        className="chip"
                                        data-active={openTool?.key === key && openTool.probe === probe && openTool.mode === "retry"}
                                        onClick={() => setOpenTool((cur) => (cur?.key === key && cur.probe === probe && cur.mode === "retry" ? null : { key, probe, mode: "retry" }))}
                                      >
                                        ↻ retry {probe}
                                      </button>
                                      <button
                                        className="chip"
                                        data-active={openTool?.key === key && openTool.probe === probe && openTool.mode === "history"}
                                        onClick={() => setOpenTool((cur) => (cur?.key === key && cur.probe === probe && cur.mode === "history" ? null : { key, probe, mode: "history" }))}
                                      >
                                        history
                                      </button>
                                    </div>
                                  ))}
                                </div>

                                {openTool?.key === key && openTool.mode === "retry" && (
                                  <RetryPanel provider={r.provider} model={r.model} probe={openTool.probe} providerMeta={providerByName[r.provider]} onDone={() => setOpenTool(null)} />
                                )}
                                {openTool?.key === key && openTool.mode === "history" && (
                                  <div className="mt-2">
                                    <HistoryPanel provider={r.provider} model={r.model} probe={openTool.probe} />
                                  </div>
                                )}
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

function DetailCard({ title, ok, body, children }: { title: string; ok?: boolean; body?: string | null; children?: React.ReactNode }) {
  return (
    <div className="panel p-3">
      <div className="flex items-center justify-between mb-1">
        <span className="text-[11px] uppercase text-text-faint">{title}</span>
        {gradedPill(ok)}
      </div>
      <div className="font-mono text-xs whitespace-pre-wrap">{body || "(no detail)"}</div>
      {children}
    </div>
  );
}
