// Byline: Claude Code · Sonnet (agent) · 2026-07-21
"use client";

import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

export interface CopilotMessage {
  role: "user" | "assistant";
  text: string;
}

/** Monospace-friendly message rendering — no markdown lib (keep deps zero,
 * per the build brief); a plain `<pre>` handles the model's own formatting
 * (code fences, lists) well enough for an ops tool. */
export function CopilotMessageList({
  messages,
  loading,
}: {
  messages: CopilotMessage[];
  loading: boolean;
}) {
  if (messages.length === 0 && !loading) {
    return (
      <p className="flex-1 text-sm text-muted-foreground">
        Ask about a run, a staged file, or anything else — pick a preset below or just type.
      </p>
    );
  }

  return (
    <div className="flex-1 space-y-3 overflow-auto">
      {messages.map((m, i) => (
        <div
          key={i}
          className={cn(
            "rounded-md border px-3 py-2",
            m.role === "user" ? "bg-accent/40" : "bg-transparent",
          )}
        >
          <p className="mb-1 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
            {m.role === "user" ? "You" : "Copilot"}
          </p>
          <pre className="whitespace-pre-wrap break-words font-mono text-xs">{m.text}</pre>
        </div>
      ))}
      {loading && (
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
          Waiting for the model…
        </div>
      )}
    </div>
  );
}
