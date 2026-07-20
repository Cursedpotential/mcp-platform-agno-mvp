// Byline: Claude Code · Sonnet (agent) · 2026-07-20
"use client";

/**
 * Lets any page open the New-run dialog with an optional prefill — mirrors
 * `refresh-context.tsx`'s pattern (a single provider mounted once in
 * layout.tsx, consumed via a hook) rather than prop-drilling between the
 * Runs page ("New run" button, no prefill) and the Intake page (a row's
 * "Start run ->" action, prefilled with that staged file).
 */
import { createContext, useCallback, useContext, useState } from "react";

/** What the Intake page's "Start run ->" row action hands the dialog. */
export interface NewRunPrefill {
  stagedId: string;
  name: string;
}

interface NewRunDialogContextValue {
  open: boolean;
  prefill: NewRunPrefill | null;
  openNewRun: (prefill?: NewRunPrefill) => void;
  closeNewRun: () => void;
}

const NewRunDialogContext = createContext<NewRunDialogContextValue>({
  open: false,
  prefill: null,
  openNewRun: () => {},
  closeNewRun: () => {},
});

export function NewRunDialogProvider({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const [prefill, setPrefill] = useState<NewRunPrefill | null>(null);

  const openNewRun = useCallback((next?: NewRunPrefill) => {
    setPrefill(next ?? null);
    setOpen(true);
  }, []);

  const closeNewRun = useCallback(() => {
    setOpen(false);
    setPrefill(null);
  }, []);

  return (
    <NewRunDialogContext.Provider value={{ open, prefill, openNewRun, closeNewRun }}>
      {children}
    </NewRunDialogContext.Provider>
  );
}

export function useNewRunDialog() {
  return useContext(NewRunDialogContext);
}
