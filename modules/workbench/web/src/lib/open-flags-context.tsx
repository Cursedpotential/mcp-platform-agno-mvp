// Byline: Claude Code · Sonnet (agent) · 2026-07-22 (C3: corroboration flags — Evidence Queue badge count)
"use client";

/**
 * Polls `GET /api/flags?status=open` independently of the Evidence Queue
 * page's own poll (the sidebar renders on every route) — mirrors
 * lib/failed-runs-context.tsx's pattern exactly (C2.6's failed-run badge).
 */
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { listFlags } from "./api-client";

const POLL_MS = 20_000;

const OpenFlagsCountContext = createContext<number>(0);

export function OpenFlagsCountProvider({ children }: { children: ReactNode }) {
  const [openCount, setOpenCount] = useState(0);

  useEffect(() => {
    let cancelled = false;
    const poll = () => {
      listFlags({ status: "open" })
        .then((flags) => {
          if (!cancelled) setOpenCount(flags.length);
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

  return <OpenFlagsCountContext.Provider value={openCount}>{children}</OpenFlagsCountContext.Provider>;
}

export function useOpenFlagsCount() {
  return useContext(OpenFlagsCountContext);
}
