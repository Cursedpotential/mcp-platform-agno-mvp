// Byline: Claude Code · Sonnet (agent) · 2026-07-21 (C2.7: Essentials shelf, recently-used, retry, full descriptions)
"use client";

/**
 * Tools page curation (C2.7 — requirements addendum 8 / owner directive #2):
 *  - a "Recently used" row (last 8 invoked, localStorage) above Essentials
 *    when non-empty;
 *  - a pinned "Essentials" shelf, always first, config-driven via
 *    lib/tools-essentials.ts (isEssential) — flattened across servers, so
 *    it's not itself collapsible/grouped;
 *  - everything else grouped under its own server, collapsed by default,
 *    expandable, and force-expanded while a search is active;
 *  - search matches name OR description, across every section;
 *  - each server card that came back with an `error` gets a Retry button
 *    that re-runs the same GET /api/tools aggregate call;
 *  - descriptions render fully (not truncated) — a 1-line clamp in list
 *    rows (`line-clamp-1`, a native Tailwind v4 utility, no plugin), the
 *    complete text in the detail-pane header.
 */
import { useEffect, useMemo, useState } from "react";
import { ChevronDown, ChevronRight, RotateCw, Search } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ToolForm, type ToolInvokeResult } from "./tool-form";
import { ToolResultPane } from "./tool-result-pane";
import { listTools } from "@/lib/api-client";
import { cn } from "@/lib/utils";
import { isEssential } from "@/lib/tools-essentials";
import { getRecentTools, recordToolUsed, type RecentToolEntry } from "@/lib/recent-tools";
import type { McpTool, ToolServerGroup } from "@/lib/shared/types";

interface FlatTool {
  serverKey: string;
  serverLabel: string;
  tool: McpTool;
}

function matchesSearch(tool: McpTool, q: string): boolean {
  if (!q) return true;
  return (
    tool.name.toLowerCase().includes(q) || (tool.description ?? "").toLowerCase().includes(q)
  );
}

export function ToolExplorer() {
  const [servers, setServers] = useState<ToolServerGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [retrying, setRetrying] = useState(false);
  const [search, setSearch] = useState("");
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [selected, setSelected] = useState<{ serverKey: string; tool: McpTool } | null>(null);
  const [result, setResult] = useState<ToolInvokeResult | null>(null);
  const [recent, setRecent] = useState<RecentToolEntry[]>([]);

  const fetchServers = () => {
    return listTools()
      .then(setServers)
      .catch(() => setServers([]));
  };

  useEffect(() => {
    fetchServers().finally(() => setLoading(false));
    queueMicrotask(() => setRecent(getRecentTools()));
  }, []);

  const handleRetry = () => {
    setRetrying(true);
    fetchServers().finally(() => setRetrying(false));
  };

  const q = search.trim().toLowerCase();

  const allTools: FlatTool[] = useMemo(
    () =>
      servers.flatMap((s) =>
        (s.tools ?? []).map((tool) => ({ serverKey: s.key, serverLabel: s.label, tool })),
      ),
    [servers],
  );

  const findFlat = (serverKey: string, toolName: string) =>
    allTools.find((f) => f.serverKey === serverKey && f.tool.name === toolName);

  const recentFlat = useMemo(
    () =>
      recent
        .map((r) => findFlat(r.serverKey, r.toolName))
        .filter((f): f is FlatTool => !!f && matchesSearch(f.tool, q)),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [recent, allTools, q],
  );

  const essentialFlat = useMemo(
    () => allTools.filter((f) => isEssential(f.serverKey, f.tool.name) && matchesSearch(f.tool, q)),
    [allTools, q],
  );

  const essentialKeySet = useMemo(
    () => new Set(essentialFlat.map((f) => `${f.serverKey}::${f.tool.name}`)),
    [essentialFlat],
  );

  const groupedServers = useMemo(
    () =>
      servers.map((s) => ({
        ...s,
        tools: (s.tools ?? []).filter(
          (t) => !essentialKeySet.has(`${s.key}::${t.name}`) && matchesSearch(t, q),
        ),
      })),
    [servers, essentialKeySet, q],
  );

  const handleSelect = (serverKey: string, tool: McpTool) => {
    setSelected({ serverKey, tool });
    setResult(null);
  };

  const handleResult = (r: ToolInvokeResult) => {
    setResult(r);
    if (r.ok && selected) {
      recordToolUsed(selected.serverKey, selected.tool.name);
      setRecent(getRecentTools());
    }
  };

  const toggleExpanded = (key: string) =>
    setExpanded((prev) => ({ ...prev, [key]: !prev[key] }));

  const isExpanded = (key: string) => (q ? true : !!expanded[key]);

  const renderToolButton = (f: FlatTool, showServerBadge: boolean) => (
    <li key={`${f.serverKey}::${f.tool.name}`}>
      <button
        type="button"
        onClick={() => handleSelect(f.serverKey, f.tool)}
        className={cn(
          "w-full rounded-md px-2 py-1.5 text-left text-xs hover:bg-accent",
          selected?.serverKey === f.serverKey &&
            selected?.tool.name === f.tool.name &&
            "bg-accent font-medium",
        )}
      >
        <div className="flex items-center gap-1.5">
          <span className="truncate font-medium">{f.tool.name}</span>
          {showServerBadge && (
            <Badge variant="outline" className="text-[9px] shrink-0">
              {f.serverLabel}
            </Badge>
          )}
        </div>
        {f.tool.description && (
          <p className="line-clamp-1 text-[11px] text-muted-foreground">{f.tool.description}</p>
        )}
      </button>
    </li>
  );

  return (
    <div className="grid gap-4 lg:grid-cols-[340px_1fr]">
      <Card className="h-fit">
        <CardHeader>
          <CardTitle>Servers &amp; tools</CardTitle>
          <div className="relative mt-2">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              className="pl-8"
              placeholder="Search tools (name or description)…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {loading ? (
            <div className="space-y-2">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-8 w-full" />
              ))}
            </div>
          ) : (
            <>
              {recentFlat.length > 0 && (
                <div className="space-y-1.5">
                  <p className="text-sm font-semibold">Recently used</p>
                  <ul className="space-y-0.5">{recentFlat.map((f) => renderToolButton(f, true))}</ul>
                </div>
              )}

              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <p className="text-sm font-semibold">Essentials</p>
                  <Badge variant="outline" className="text-[10px]">
                    {essentialFlat.length}
                  </Badge>
                </div>
                {essentialFlat.length === 0 ? (
                  <p className="text-xs text-muted-foreground">
                    {q ? "No essentials match your search." : "No essentials configured yet."}
                  </p>
                ) : (
                  <ul className="space-y-0.5">{essentialFlat.map((f) => renderToolButton(f, true))}</ul>
                )}
              </div>

              {groupedServers.length === 0 ? (
                <p className="text-sm text-muted-foreground">No MCP servers configured.</p>
              ) : (
                groupedServers.map((server) => (
                  <div key={server.key} className="space-y-1.5 border-t pt-3 first:border-t-0 first:pt-0">
                    <div className="flex items-center justify-between">
                      <button
                        type="button"
                        onClick={() => toggleExpanded(server.key)}
                        className="flex items-center gap-1 text-sm font-semibold hover:underline"
                      >
                        {isExpanded(server.key) ? (
                          <ChevronDown className="h-3.5 w-3.5" />
                        ) : (
                          <ChevronRight className="h-3.5 w-3.5" />
                        )}
                        {server.label}
                      </button>
                      {server.error ? (
                        <Badge variant="destructive" className="text-[10px]">
                          error
                        </Badge>
                      ) : (
                        <Badge variant="outline" className="text-[10px]">
                          {server.tools?.length ?? 0}
                        </Badge>
                      )}
                    </div>
                    {server.error ? (
                      <div className="space-y-1.5 rounded-md border border-destructive/40 bg-destructive/10 p-2">
                        <p className="text-xs text-destructive">{server.error}</p>
                        <Button variant="outline" size="sm" onClick={handleRetry} disabled={retrying}>
                          <RotateCw className={cn("h-3.5 w-3.5 mr-1", retrying && "animate-spin")} />
                          {retrying ? "Retrying…" : "Retry"}
                        </Button>
                      </div>
                    ) : isExpanded(server.key) ? (
                      server.tools.length === 0 ? (
                        <p className="text-xs text-muted-foreground">
                          {q ? "No matches in this server." : "No non-essential tools."}
                        </p>
                      ) : (
                        <ul className="space-y-0.5">
                          {server.tools.map((tool) =>
                            renderToolButton({ serverKey: server.key, serverLabel: server.label, tool }, false),
                          )}
                        </ul>
                      )
                    ) : null}
                  </div>
                ))
              )}
            </>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{selected ? selected.tool.name : "Select a tool"}</CardTitle>
          {selected?.tool.description && (
            <p className="text-sm text-muted-foreground whitespace-pre-wrap">
              {selected.tool.description}
            </p>
          )}
        </CardHeader>
        <CardContent className="space-y-6">
          {selected ? (
            <>
              <ToolForm serverKey={selected.serverKey} tool={selected.tool} onResult={handleResult} />
              <div>
                <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Result
                </p>
                <ToolResultPane result={result} />
              </div>
            </>
          ) : (
            <p className="text-sm text-muted-foreground">
              Pick a tool from the left to see its parameters.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
