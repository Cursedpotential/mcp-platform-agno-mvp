// Byline: Codex · GPT-5 · 2026-08-27
"use client";

import { useEffect, useState } from "react";
import {
  createRunEventSource,
  parseRunEvent,
  type RunEvent,
} from "@/lib/run-events-client";

export type RunEventConnectionState = "connecting" | "live" | "reconnecting" | "unavailable";

const MAX_EVENTS = 200;
const UNAVAILABLE_AFTER_FAILURES = 3;

interface EventBuffer {
  runId: string;
  events: RunEvent[];
}

interface Connection {
  runId: string;
  failures: number;
  state: RunEventConnectionState;
}

/** Follow one run while retaining only its newest ordered structured events. */
export function useRunEvents(runId: string) {
  const [buffer, setBuffer] = useState<EventBuffer>({ runId: "", events: [] });
  const [connection, setConnection] = useState<Connection>({
    runId: "",
    failures: 0,
    state: "connecting",
  });

  useEffect(() => {
    const source = createRunEventSource(runId);

    source.onopen = () => {
      setConnection({ runId, failures: 0, state: "live" });
    };

    const handleEvent = (incoming: Event) => {
      if (!(incoming instanceof MessageEvent)) return;
      const event = parseRunEvent(String(incoming.data));
      if (!event || event.run_id !== runId) return;
      setBuffer((current) => {
        const events = current.runId === runId ? current.events : [];
        if (events.some((item) => item.sequence === event.sequence)) return { runId, events };
        const ordered = [...events, event].sort((left, right) => left.sequence - right.sequence);
        return { runId, events: ordered.slice(-MAX_EVENTS) };
      });
    };

    source.addEventListener("run-event", handleEvent);
    source.onerror = () => {
      setConnection((current) => {
        const failures = current.runId === runId ? current.failures + 1 : 1;
        return {
          runId,
          failures,
          state: failures >= UNAVAILABLE_AFTER_FAILURES ? "unavailable" : "reconnecting",
        };
      });
    };

    return () => {
      source.removeEventListener("run-event", handleEvent);
      source.close();
    };
  }, [runId]);

  return {
    events: buffer.runId === runId ? buffer.events : [],
    state: connection.runId === runId ? connection.state : "connecting",
    maxEvents: MAX_EVENTS,
  };
}
