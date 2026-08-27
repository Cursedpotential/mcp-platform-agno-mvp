"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function HistoryPanel({ provider, model, probe }: { provider: string; model: string; probe?: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ["history", provider, model, probe],
    queryFn: () => api.history(provider, model, probe),
  });

  if (isLoading) return <div className="text-xs text-text-faint p-2">loading history…</div>;
  if (!data || data.length === 0) return <div className="text-xs text-text-faint p-2">no runs recorded yet.</div>;

  return (
    <div className="flex flex-col gap-2 max-h-80 overflow-y-auto">
      {data.map((r) => (
        <div key={`${r.run_id}-${r.probe}-${r.created_at}`} className="panel p-2.5 text-xs">
          <div className="flex items-center justify-between gap-2 mb-1">
            <span className={`font-mono font-semibold ${r.ok ? "text-good" : "text-bad"}`}>{r.ok ? "PASS" : "FAIL"}</span>
            <span className="text-text-faint">{r.probe}</span>
            <span className="text-text-faint">{new Date(r.created_at).toLocaleString()}</span>
          </div>
          <div className="flex flex-wrap gap-1.5 text-[10px] font-mono text-text-dim mb-1.5">
            {r.max_tokens_used !== null && <span className="chip !py-0.5">max_tokens={r.max_tokens_used}</span>}
            {r.reasoning_effort_used && <span className="chip !py-0.5">reasoning={r.reasoning_effort_used}</span>}
            {r.latency_s !== null && <span className="chip !py-0.5">{r.latency_s}s</span>}
            {typeof r.key_facts_hit === "number" && <span className="chip !py-0.5">{r.key_facts_hit}/8 facts</span>}
          </div>
          <div className="font-mono text-text-dim whitespace-pre-wrap line-clamp-3">{r.content || r.error || "(empty)"}</div>
        </div>
      ))}
    </div>
  );
}
