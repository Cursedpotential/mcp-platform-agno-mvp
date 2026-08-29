// Byline: Codex · GPT-5 · 2026-08-27

export type RunEventLevel = "debug" | "info" | "warning" | "error";
export type SafeRunEventScalar = string | number | boolean | null;

export interface RunEvent {
  run_id: string;
  sequence: number;
  event_type: string;
  source: string;
  level: RunEventLevel;
  message: string;
  attributes: Record<string, SafeRunEventScalar>;
  trace_id: string | null;
  span_id: string | null;
  occurred_at: string;
  recorded_at: string;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";
const UNSAFE_ATTRIBUTE_SEGMENT =
  /(^|[_.-])(authorization|cookie|secret|password|passphrase|token|api[_-]?key|prompt|completion|response|request[_-]?body|raw|content|evidence|transcript|document|message|detail|stack|exception)([_.-]|$)/i;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isSafeScalar(value: unknown): value is SafeRunEventScalar {
  return value === null || ["string", "number", "boolean"].includes(typeof value);
}

function isOptionalHexId(value: unknown, length: number): value is string | null {
  return value === null || (typeof value === "string" && new RegExp(`^[A-Fa-f0-9]{${length}}$`).test(value));
}

function safeAttributes(value: unknown): Record<string, SafeRunEventScalar> | null {
  if (!isRecord(value)) return null;
  const entries = Object.entries(value);
  if (
    entries.some(
      ([key, item]) =>
        UNSAFE_ATTRIBUTE_SEGMENT.test(key) ||
        !isSafeScalar(item) ||
        (typeof item === "string" && item.length > 1024),
    )
  ) {
    return null;
  }
  return Object.fromEntries(entries) as Record<string, SafeRunEventScalar>;
}

/** Parse only the bounded, content-free structured event contract. */
export function parseRunEvent(serialized: string): RunEvent | null {
  let value: unknown;
  try {
    value = JSON.parse(serialized);
  } catch {
    return null;
  }
  if (!isRecord(value)) return null;
  const attributes = safeAttributes(value.attributes);
  const level = value.level;
  if (
    typeof value.run_id !== "string" ||
    !Number.isSafeInteger(value.sequence) ||
    Number(value.sequence) < 1 ||
    typeof value.event_type !== "string" ||
    typeof value.source !== "string" ||
    !["debug", "info", "warning", "error"].includes(String(level)) ||
    typeof value.message !== "string" ||
    !isOptionalHexId(value.trace_id, 32) ||
    !isOptionalHexId(value.span_id, 16) ||
    typeof value.occurred_at !== "string" ||
    typeof value.recorded_at !== "string" ||
    attributes === null
  ) {
    return null;
  }
  return {
    run_id: value.run_id,
    sequence: Number(value.sequence),
    event_type: value.event_type,
    source: value.source,
    level: level as RunEventLevel,
    message: value.message,
    attributes,
    trace_id: value.trace_id,
    span_id: value.span_id,
    occurred_at: value.occurred_at,
    recorded_at: value.recorded_at,
  };
}

/**
 * Open the same-origin Workbench stream. Native EventSource retains every
 * upstream ``id`` and sends it back as ``Last-Event-ID`` on reconnect; the
 * Workbench BFF forwards that cursor while keeping platform auth server-side.
 */
export function createRunEventSource(runId: string): EventSource {
  const query = new URLSearchParams({ after: "0", follow: "true", limit: "250" });
  const url = `${API_BASE}/api/runs/${encodeURIComponent(runId)}/events?${query.toString()}`;
  return new EventSource(url, { withCredentials: true });
}
