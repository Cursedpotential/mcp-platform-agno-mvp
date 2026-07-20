// Byline: Claude Code · Sonnet (agent) · 2026-07-19
"use client";

import { CheckCircle2, AlertTriangle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import type { UploadResponse } from "@/lib/shared/types";

interface UploadResultProps {
  result: UploadResponse;
}

const TYPE_LABEL: Record<UploadResponse["detected_type"], string> = {
  doc: "Document",
  chat_export: "Chat export",
};

/** Per-file outcome shown under the dropzone once a file finishes uploading. */
export function UploadResult({ result }: UploadResultProps) {
  if (result.duplicate) {
    return (
      <div className="flex items-start gap-2 rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs">
        <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-amber-600 mt-0.5" />
        <div>
          <p className="font-medium text-amber-700 dark:text-amber-400">
            {result.name} — already staged
          </p>
          <p className="text-muted-foreground mt-0.5">
            This file matches an existing staged file (id {result.id}); no new copy was created.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2 text-xs text-muted-foreground">
      <CheckCircle2 className="h-3.5 w-3.5 text-green-600 shrink-0" />
      <span className="truncate">{result.name} staged</span>
      <Badge variant="outline" className="text-[10px]">
        {TYPE_LABEL[result.detected_type] ?? result.detected_type}
      </Badge>
      {result.meta?.domain && (
        <Badge variant="secondary" className="text-[10px]">
          {result.meta.domain}
        </Badge>
      )}
    </div>
  );
}
