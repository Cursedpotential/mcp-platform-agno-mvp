// Byline: Claude Code · Sonnet (agent) · 2026-07-21 (C2.6: dependency health strip)
"use client";

/**
 * Console header dependency-health strip (C2.6 requirement 4): a small dot
 * + name chip per dependency (pg, milvus, lancedb, object_store), polled
 * every 60s via GET /api/health/deps. A red dot's tooltip shows the error
 * text; a green dot's tooltip just confirms "ok".
 */
import { useEffect, useState } from "react";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { getHealthDeps } from "@/lib/api-client";
import type { DepStatus, HealthDepsResponse } from "@/lib/shared/types";

const POLL_MS = 60_000;

const DEP_LABELS: Record<keyof Omit<HealthDepsResponse, "checked_at">, string> = {
  pg: "Postgres",
  milvus: "Milvus",
  lancedb: "LanceDB",
  object_store: "Object store",
};

const DEP_KEYS = Object.keys(DEP_LABELS) as Array<keyof typeof DEP_LABELS>;

function Dot({ status }: { status: DepStatus["status"] }) {
  return (
    <span
      className={cn(
        "inline-block size-2 shrink-0 rounded-full",
        status === "ok" ? "bg-green-500" : "bg-red-500",
      )}
    />
  );
}

export function HealthChips() {
  const [deps, setDeps] = useState<HealthDepsResponse | null>(null);

  useEffect(() => {
    let cancelled = false;
    const poll = () => {
      getHealthDeps()
        .then((data) => {
          if (!cancelled) setDeps(data);
        })
        .catch(() => {
          // Transient poll failure — keep the last-known chips, try again next tick.
        });
    };
    poll();
    const id = setInterval(poll, POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  if (!deps) return null;

  return (
    <div className="flex items-center gap-2.5">
      {DEP_KEYS.map((key) => {
        const dep = deps[key];
        if (!dep) return null;
        return (
          <Tooltip key={key}>
            <TooltipTrigger asChild>
              <span className="flex items-center gap-1.5 text-xs text-nav-foreground/70">
                <Dot status={dep.status} />
                <span className="hidden sm:inline">{DEP_LABELS[key]}</span>
              </span>
            </TooltipTrigger>
            <TooltipContent>
              {DEP_LABELS[key]}: {dep.status}
              {dep.error ? ` — ${dep.error}` : ""}
            </TooltipContent>
          </Tooltip>
        );
      })}
    </div>
  );
}
