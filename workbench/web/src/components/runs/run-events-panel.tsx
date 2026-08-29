// Byline: Codex · GPT-5 · 2026-08-27
"use client";

import { Activity, CircleAlert } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { useRunEvents, type RunEventConnectionState } from "@/hooks/use-run-events";
import type { RunEventLevel, SafeRunEventScalar } from "@/lib/run-events-client";

const STATE_LABEL: Record<RunEventConnectionState, string> = {
  connecting: "Connecting",
  live: "Live",
  reconnecting: "Reconnecting",
  unavailable: "Unavailable",
};

function levelClass(level: RunEventLevel): string {
  if (level === "error") return "text-destructive";
  if (level === "warning") return "text-amber-700 dark:text-amber-400";
  if (level === "debug") return "text-muted-foreground";
  return "text-foreground";
}

function displayScalar(value: SafeRunEventScalar): string {
  if (value === null) return "null";
  return String(value);
}

function displayTime(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleTimeString();
}

export function RunEventsPanel({ runId }: { runId: string }) {
  const { events, state, maxEvents } = useRunEvents(runId);

  return (
    <section className="rounded-md border" aria-label="Live run progress">
      <header className="flex flex-wrap items-center justify-between gap-2 border-b px-3 py-2">
        <div className="flex items-center gap-2">
          <Activity className="size-4" aria-hidden="true" />
          <h3 className="text-sm font-semibold">Live progress</h3>
        </div>
        <Badge variant={state === "unavailable" ? "destructive" : "outline"}>
          {STATE_LABEL[state]}
        </Badge>
      </header>

      {events.length === 0 ? (
        <div className="flex items-center gap-2 px-3 py-4 text-xs text-muted-foreground" role="status">
          {state === "unavailable" && <CircleAlert className="size-4 text-destructive" />}
          {state === "live" && "Connected; waiting for the next structured event."}
          {state === "connecting" && "Connecting to the durable event stream…"}
          {state === "reconnecting" && "Connection interrupted; replay-safe reconnect in progress…"}
          {state === "unavailable" && "The event stream is temporarily unavailable; automatic retry continues."}
        </div>
      ) : (
        <ol className="max-h-72 divide-y overflow-y-auto" aria-live="polite">
          {events.map((event) => {
            const attributes = Object.entries(event.attributes).sort(([left], [right]) =>
              left.localeCompare(right),
            );
            return (
              <li key={event.sequence} className="space-y-1 px-3 py-2 text-xs">
                <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1 font-mono">
                  <span className="text-muted-foreground">#{event.sequence}</span>
                  <time dateTime={event.occurred_at}>{displayTime(event.occurred_at)}</time>
                  <span className={`font-semibold uppercase ${levelClass(event.level)}`}>
                    {event.level}
                  </span>
                  <span className="text-muted-foreground">{event.source}</span>
                </div>
                <p className={levelClass(event.level)}>{event.message}</p>
                {(event.trace_id || event.span_id) && (
                  <div className="flex flex-wrap gap-x-3 font-mono text-[11px] text-muted-foreground">
                    {event.trace_id && (
                      <span title={`Trace ${event.trace_id}`}>trace {event.trace_id.slice(0, 12)}…</span>
                    )}
                    {event.span_id && <span title={`Span ${event.span_id}`}>span {event.span_id}</span>}
                  </div>
                )}
                {attributes.length > 0 && (
                  <dl className="flex flex-wrap gap-x-3 gap-y-1 text-muted-foreground">
                    {attributes.map(([key, value]) => (
                      <div key={key} className="flex gap-1">
                        <dt>{key}:</dt>
                        <dd className="font-mono text-foreground">{displayScalar(value)}</dd>
                      </div>
                    ))}
                  </dl>
                )}
              </li>
            );
          })}
        </ol>
      )}

      <footer className="border-t px-3 py-1.5 text-[11px] text-muted-foreground">
        Ordered by durable sequence · showing at most the newest {maxEvents} safe events
      </footer>
    </section>
  );
}
