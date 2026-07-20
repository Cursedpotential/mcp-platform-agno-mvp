// Byline: Claude Code · Sonnet (agent) · 2026-07-20
"use client";

import { useEffect, useMemo, useState } from "react";
import { Search } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { ToolForm, type ToolInvokeResult } from "./tool-form";
import { ToolResultPane } from "./tool-result-pane";
import { listTools } from "@/lib/api-client";
import { cn } from "@/lib/utils";
import type { McpTool, ToolServerGroup } from "@/lib/shared/types";

export function ToolExplorer() {
  const [servers, setServers] = useState<ToolServerGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<{ serverKey: string; tool: McpTool } | null>(null);
  const [result, setResult] = useState<ToolInvokeResult | null>(null);

  useEffect(() => {
    listTools()
      .then(setServers)
      .catch(() => setServers([]))
      .finally(() => setLoading(false));
  }, []);

  const filteredServers = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return servers;
    return servers.map((s) => ({
      ...s,
      tools: (s.tools ?? []).filter(
        (t) => t.name.toLowerCase().includes(q) || (t.description ?? "").toLowerCase().includes(q),
      ),
    }));
  }, [servers, search]);

  const handleSelect = (serverKey: string, tool: McpTool) => {
    setSelected({ serverKey, tool });
    setResult(null);
  };

  return (
    <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
      <Card className="h-fit">
        <CardHeader>
          <CardTitle>Servers &amp; tools</CardTitle>
          <div className="relative mt-2">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              className="pl-8"
              placeholder="Search tools…"
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
          ) : filteredServers.length === 0 ? (
            <p className="text-sm text-muted-foreground">No MCP servers configured.</p>
          ) : (
            filteredServers.map((server) => (
              <div key={server.key} className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <p className="text-sm font-semibold">{server.label}</p>
                  {server.error ? (
                    <Badge variant="destructive" className="text-[10px]">
                      error
                    </Badge>
                  ) : (
                    <Badge variant="outline" className="text-[10px]">
                      {(server.tools ?? []).length}
                    </Badge>
                  )}
                </div>
                {server.error ? (
                  <p className="text-xs text-destructive">{server.error}</p>
                ) : (
                  <ul className="space-y-0.5">
                    {(server.tools ?? []).map((tool) => (
                      <li key={tool.name}>
                        <button
                          type="button"
                          onClick={() => handleSelect(server.key, tool)}
                          className={cn(
                            "w-full truncate rounded-md px-2 py-1 text-left text-xs hover:bg-accent",
                            selected?.serverKey === server.key &&
                              selected?.tool.name === tool.name &&
                              "bg-accent font-medium",
                          )}
                        >
                          {tool.name}
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ))
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{selected ? selected.tool.name : "Select a tool"}</CardTitle>
          {selected?.tool.description && (
            <p className="text-sm text-muted-foreground">{selected.tool.description}</p>
          )}
        </CardHeader>
        <CardContent className="space-y-6">
          {selected ? (
            <>
              <ToolForm serverKey={selected.serverKey} tool={selected.tool} onResult={setResult} />
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
