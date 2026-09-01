// Byline: Codex · GPT-5 · 2026-08-29 (single canonical case shell context)
"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";

import { ApiError, getMatter, listMatters } from "@/lib/api-client";
import type { CourtCase, MatterDetail } from "@/lib/shared/types";

type FixedCaseContextValue = {
  matter: MatterDetail | null;
  primaryCourtCase: CourtCase | null;
  loading: boolean;
  error: string | null;
};

const FixedCaseContext = createContext<FixedCaseContextValue | null>(null);

function errorText(error: unknown) {
  return error instanceof ApiError
    ? error.message
    : error instanceof Error
      ? error.message
      : "The fixed case could not be loaded";
}

export function FixedCaseProvider({ children }: { children: React.ReactNode }) {
  const [matter, setMatter] = useState<MatterDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    listMatters()
      .then((response) => {
        if (response.total === 0) {
          throw new Error(
            "The Platform has no case. Restore the single canonical case before intake continues.",
          );
        }
        if (response.total !== 1 || response.data.length !== 1) {
          throw new Error(
            `The Platform returned ${response.total} Matters. This is split or duplicated case data, not a choice for the operator.`,
          );
        }
        return getMatter(response.data[0].id);
      })
      .then((fixedMatter) => {
        if (!cancelled) {
          setMatter(fixedMatter);
          setError(null);
        }
      })
      .catch((requestError) => {
        if (!cancelled) setError(errorText(requestError));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const value = useMemo<FixedCaseContextValue>(
    () => ({
      matter,
      primaryCourtCase: matter?.court_cases.find((courtCase) => courtCase.is_primary) ?? null,
      loading,
      error,
    }),
    [matter, loading, error],
  );

  return <FixedCaseContext.Provider value={value}>{children}</FixedCaseContext.Provider>;
}

export function useFixedCase() {
  const context = useContext(FixedCaseContext);
  if (!context) throw new Error("useFixedCase must be used within FixedCaseProvider");
  return context;
}
