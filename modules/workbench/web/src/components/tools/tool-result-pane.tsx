// Byline: Claude Code · Sonnet (agent) · 2026-07-20
"use client";

import { useState } from "react";
import { Copy, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { ToolInvokeResult } from "./tool-form";

export function ToolResultPane({ result }: { result: ToolInvokeResult | null }) {
  const [pretty, setPretty] = useState(true);
  const [copied, setCopied] = useState(false);

  if (!result) {
    return <p className="text-sm text-muted-foreground">Invoke a tool to see its result here.</p>;
  }

  if (!result.ok) {
    return (
      <div className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
        {result.error}
      </div>
    );
  }

  const text = pretty ? JSON.stringify(result.value, null, 2) : JSON.stringify(result.value);

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <Button variant="outline" size="sm" onClick={() => setPretty((p) => !p)}>
          {pretty ? "Raw" : "Pretty"}
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            navigator.clipboard.writeText(text).catch(() => {});
            setCopied(true);
            setTimeout(() => setCopied(false), 1500);
          }}
        >
          {copied ? <Check className="h-3.5 w-3.5 mr-1" /> : <Copy className="h-3.5 w-3.5 mr-1" />}
          Copy
        </Button>
      </div>
      <pre className="max-h-96 overflow-auto rounded-md border bg-muted/30 p-3 text-xs">{text}</pre>
    </div>
  );
}
