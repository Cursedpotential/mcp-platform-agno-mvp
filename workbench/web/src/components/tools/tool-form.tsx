// Byline: Claude Code · Sonnet (agent) · 2026-07-21 (C2.7: Example / Save-as-example actions)
"use client";

/**
 * Hand-rolled JSON-Schema-driven form — deliberately NOT react-jsonschema-form
 * (per the build brief: "keep the form generator small and dependency-free").
 * Covers string/number/boolean/enum as native fields; anything else
 * (array/object/unrecognized) falls back to a raw-JSON textarea, parsed at
 * submit time. When the tool's `inputSchema` isn't a plain `{type:"object",
 * properties:{...}}` at all, the WHOLE form degrades to one JSON textarea.
 *
 * C2.7 adds two actions (owner directive #2): "Example" fills the form from
 * `buildExample()` (a saved example, or the schema's own examples/defaults,
 * or a minimal required-fields skeleton); "Save as example" persists the
 * form's current built arguments as that tool's example for next time.
 */
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { callTool } from "@/lib/api-client";
import { buildExample, saveExample } from "@/lib/tool-examples";
import type { JsonSchema, McpTool } from "@/lib/shared/types";

export interface ToolInvokeResult {
  ok: boolean;
  value?: unknown;
  error?: string;
}

interface ToolFormProps {
  serverKey: string;
  tool: McpTool;
  onResult: (result: ToolInvokeResult) => void;
}

type FieldValue = string | boolean | undefined;

function propertiesOf(schema?: JsonSchema): [string, JsonSchema][] {
  if (!schema || schema.type !== "object" || !schema.properties) return [];
  return Object.entries(schema.properties);
}

/** Types this form renders as a native field; everything else gets the JSON textarea fallback. */
function isSimple(schema: JsonSchema): boolean {
  return !!schema.enum || ["string", "number", "integer", "boolean"].includes(schema.type ?? "");
}

export function ToolForm({ serverKey, tool, onResult }: ToolFormProps) {
  const props = propertiesOf(tool.inputSchema);
  const required = new Set(tool.inputSchema?.required ?? []);
  const useRawFallback = props.length === 0;

  const [values, setValues] = useState<Record<string, FieldValue>>({});
  const [jsonFields, setJsonFields] = useState<Record<string, string>>({});
  const [rawJson, setRawJson] = useState("{}");
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Reset whenever a different tool is selected.
  useEffect(() => {
    setValues({});
    setJsonFields({});
    setRawJson("{}");
    setFieldError(null);
  }, [tool.name, serverKey]);

  const setValue = (key: string, value: FieldValue) =>
    setValues((prev) => ({ ...prev, [key]: value }));

  function buildArguments(): Record<string, unknown> | null {
    if (useRawFallback) {
      try {
        const parsed = JSON.parse(rawJson || "{}");
        if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
          setFieldError("Arguments must be a JSON object");
          return null;
        }
        return parsed as Record<string, unknown>;
      } catch {
        setFieldError("Invalid JSON");
        return null;
      }
    }

    const args: Record<string, unknown> = {};
    for (const [key, propSchema] of props) {
      if (!isSimple(propSchema)) {
        const raw = jsonFields[key];
        if (raw && raw.trim()) {
          try {
            args[key] = JSON.parse(raw);
          } catch {
            setFieldError(`"${key}" is not valid JSON`);
            return null;
          }
        } else if (required.has(key)) {
          setFieldError(`"${key}" is required`);
          return null;
        }
        continue;
      }

      const value = values[key];
      if (value === undefined || value === "") {
        if (required.has(key)) {
          setFieldError(`"${key}" is required`);
          return null;
        }
        continue;
      }
      if (propSchema.type === "number" || propSchema.type === "integer") {
        const n = Number(value);
        if (Number.isNaN(n)) {
          setFieldError(`"${key}" must be a number`);
          return null;
        }
        args[key] = n;
      } else {
        args[key] = value;
      }
    }
    return args;
  }

  /** Fills the form (native fields or the raw-JSON fallback, whichever is
   * active) from buildExample()'s result. Doesn't touch fields the example
   * doesn't mention. */
  const handleFillExample = () => {
    setFieldError(null);
    const example = buildExample(serverKey, tool);

    if (useRawFallback) {
      setRawJson(JSON.stringify(example, null, 2));
      return;
    }

    const nextValues: Record<string, FieldValue> = {};
    const nextJsonFields: Record<string, string> = {};
    for (const [key, propSchema] of props) {
      if (!(key in example)) continue;
      const value = example[key];
      if (isSimple(propSchema)) {
        nextValues[key] = typeof value === "boolean" ? value : String(value);
      } else {
        nextJsonFields[key] = JSON.stringify(value, null, 2);
      }
    }
    setValues(nextValues);
    setJsonFields(nextJsonFields);
  };

  /** Persists the form's CURRENT built arguments (same validation path as
   * Invoke) as this tool's saved example, restored next time this tool is
   * opened and "Example" is clicked. */
  const handleSaveExample = () => {
    setFieldError(null);
    const args = buildArguments();
    if (args === null) return;
    saveExample(serverKey, tool.name, args);
    toast.success("Saved current args as this tool's example");
  };

  const handleInvoke = async () => {
    setFieldError(null);
    const args = buildArguments();
    if (args === null) return;
    setBusy(true);
    try {
      const value = await callTool(serverKey, tool.name, args);
      onResult({ ok: true, value });
    } catch (err) {
      onResult({ ok: false, error: err instanceof Error ? err.message : "Tool call failed" });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-3">
      {useRawFallback ? (
        <div className="space-y-1.5">
          <Label htmlFor="tool-raw-json">Arguments (JSON)</Label>
          <Textarea
            id="tool-raw-json"
            className="min-h-32 font-mono text-xs"
            value={rawJson}
            onChange={(e) => setRawJson(e.target.value)}
          />
        </div>
      ) : (
        props.map(([key, propSchema]) => (
          <div key={key} className="space-y-1.5">
            <Label htmlFor={`tool-field-${key}`}>
              {key}
              {required.has(key) && <span className="text-destructive"> *</span>}
            </Label>
            {propSchema.description && (
              <p className="text-xs text-muted-foreground">{propSchema.description}</p>
            )}
            {propSchema.enum ? (
              <select
                id={`tool-field-${key}`}
                className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-xs outline-none focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px]"
                value={(values[key] as string) ?? ""}
                onChange={(e) => setValue(key, e.target.value)}
              >
                <option value="">— select —</option>
                {propSchema.enum.map((opt) => (
                  <option key={String(opt)} value={String(opt)}>
                    {String(opt)}
                  </option>
                ))}
              </select>
            ) : propSchema.type === "boolean" ? (
              <Switch
                id={`tool-field-${key}`}
                checked={Boolean(values[key])}
                onCheckedChange={(checked) => setValue(key, checked)}
              />
            ) : isSimple(propSchema) ? (
              <Input
                id={`tool-field-${key}`}
                type={propSchema.type === "number" || propSchema.type === "integer" ? "number" : "text"}
                value={(values[key] as string) ?? ""}
                onChange={(e) => setValue(key, e.target.value)}
              />
            ) : (
              <Textarea
                id={`tool-field-${key}`}
                className="font-mono text-xs"
                placeholder="JSON"
                value={jsonFields[key] ?? ""}
                onChange={(e) => setJsonFields((prev) => ({ ...prev, [key]: e.target.value }))}
              />
            )}
          </div>
        ))
      )}

      {fieldError && <p className="text-xs text-destructive">{fieldError}</p>}

      <div className="flex flex-wrap gap-2">
        <Button onClick={handleInvoke} disabled={busy}>
          {busy ? "Invoking…" : "Invoke"}
        </Button>
        <Button type="button" variant="outline" onClick={handleFillExample} disabled={busy}>
          Example
        </Button>
        <Button type="button" variant="outline" onClick={handleSaveExample} disabled={busy}>
          Save current args as example
        </Button>
      </div>
    </div>
  );
}
