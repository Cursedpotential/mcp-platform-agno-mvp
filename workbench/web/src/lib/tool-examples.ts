// Byline: Claude Code · Sonnet (agent) · 2026-07-21
"use client";

/**
 * Example-payload generation + per-tool saved-example persistence for the
 * Tool Explorer's detail-pane "Example" and "Save current args as example"
 * actions (C2.7 — owner directive #2).
 */
import type { JsonSchema, McpTool } from "./shared/types";

function exampleKey(serverKey: string, toolName: string): string {
  return `workbench:tools:example:${serverKey}:${toolName}`;
}

/** A previously-saved example for this exact (server, tool), if any. */
export function getSavedExample(
  serverKey: string,
  toolName: string,
): Record<string, unknown> | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(exampleKey(serverKey, toolName));
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return typeof parsed === "object" && parsed !== null && !Array.isArray(parsed)
      ? (parsed as Record<string, unknown>)
      : null;
  } catch {
    return null;
  }
}

/** Persist the current form's built arguments as this tool's example,
 * restored automatically the next time its "Example" button is used
 * (including in a future browser session). Best-effort only. */
export function saveExample(
  serverKey: string,
  toolName: string,
  args: Record<string, unknown>,
): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(exampleKey(serverKey, toolName), JSON.stringify(args));
  } catch {
    // best effort only
  }
}

/** Type-appropriate placeholder for a JSON-Schema property with no
 * default/example of its own. */
function placeholderFor(schema: JsonSchema): unknown {
  if (schema.enum && schema.enum.length > 0) return schema.enum[0];
  switch (schema.type) {
    case "string":
      return schema.description ? `<${schema.description}>` : "<string>";
    case "number":
    case "integer":
      return 0;
    case "boolean":
      return false;
    case "array":
      return [];
    case "object":
      return {};
    default:
      return null;
  }
}

/**
 * Build an example arguments object for a tool, in priority order:
 *  1. a previously saved example for this exact (server, tool)
 *  2. the schema's own top-level `examples[0]` / `example`, if either is a
 *     plain object
 *  3. a minimal skeleton: every REQUIRED property, using its own `default`
 *     when present, else a type-appropriate placeholder — deliberately
 *     omits optional properties to keep the generated example minimal.
 */
export function buildExample(serverKey: string, tool: McpTool): Record<string, unknown> {
  const saved = getSavedExample(serverKey, tool.name);
  if (saved) return saved;

  const schema = tool.inputSchema as (JsonSchema & { examples?: unknown[]; example?: unknown }) | undefined;

  if (Array.isArray(schema?.examples) && schema.examples.length > 0) {
    const first = schema.examples[0];
    if (typeof first === "object" && first !== null && !Array.isArray(first)) {
      return first as Record<string, unknown>;
    }
  }
  if (typeof schema?.example === "object" && schema.example !== null && !Array.isArray(schema.example)) {
    return schema.example as Record<string, unknown>;
  }

  if (!schema || schema.type !== "object" || !schema.properties) return {};
  const required = new Set(schema.required ?? []);
  const skeleton: Record<string, unknown> = {};
  for (const [key, propSchema] of Object.entries(schema.properties)) {
    if (!required.has(key)) continue;
    skeleton[key] = propSchema.default !== undefined ? propSchema.default : placeholderFor(propSchema);
  }
  return skeleton;
}
