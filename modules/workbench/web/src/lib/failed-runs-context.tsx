// Byline: Claude Code · Sonnet (agent) · 2026-07-21 (C2.6: sidebar failed-run count badge)
"use client";

/**
 * Polls `GET /api/runs?status=failed` independently of any single page's
 * own run poll (the sidebar renders on every route — Runs/Tools/Intake —
 * so this can't piggyback on RunsTable's poll, which only mounts on
 * /runs). Exposes just the count; app-sidebar.tsx renders it as a red
 * SidebarMenuBadge next to the "Runs" nav item when > 0 (C2.6 requirement 3).
 */
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { listRuns } from "./api-client";

const POLL_MS = 15_000;

const FailedRunsCountContext = createContext<number>(0);

export function FailedRunsCountProvider({ children }: { children: ReactNode }) {
  const [failedCount, setFailedCount] = useState(0);

  useEffect(() => {
    let cancelled = false;
    const poll = () => {
      listRuns({ status: "failed", limit: 500 })
        .then((runs) => {
          if (!cancelled) setFailedCount(runs.length);
        })
        .catch(() => {
          // Transient poll failure — keep the last-known count, try again next tick.
        });
    };
    poll();
    const id = setInterval(poll, POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  return <FailedRunsCountContext.Provider value={failedCount}>{children}</FailedRunsCountContext.Provider>;
}

export function useFailedRunsCount() {
  return useContext(FailedRunsCountContext);
}
