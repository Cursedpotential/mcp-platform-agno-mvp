// Byline: Claude Code · Sonnet (agent) · 2026-07-22 (C3: Verify action in the custody section — requirements addendum 2)
// Byline: Codex · GPT-5 · 2026-08-13 (structured outcome reasons)
"use client";

import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { StageOutputView } from "./stage-output-view";
import { VerifyPanel } from "@/components/shared/verify-panel";
import { formatDate } from "@/lib/utils";
import type { RunStageDetail } from "@/lib/shared/types";

interface StageDrawerProps {
  stage: RunStageDetail | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** The run's sha256 (C3 Verify action) — only rendered on the custody
   * stage. Optional so existing callers keep working untouched. */
  sha256?: string | null;
}

function statusBadgeVariant(status: string): "default" | "secondary" | "destructive" | "outline" {
  switch (status) {
    case "success":
      return "default";
    case "running":
      return "secondary";
    case "failed":
      return "destructive";
    default:
      return "outline"; // pending | skipped
  }
}

export function StageDrawer({ stage, open, onOpenChange, sha256 }: StageDrawerProps) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full sm:max-w-lg overflow-y-auto">
        {stage && (
          <>
            <SheetHeader>
              <SheetTitle className="flex items-center gap-2 capitalize">
                {stage.name}
                <Badge variant={statusBadgeVariant(stage.status)}>{stage.status}</Badge>
              </SheetTitle>
              <SheetDescription>Stage {stage.seq}</SheetDescription>
            </SheetHeader>

            <div className="space-y-4 px-4 pb-4">
              <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Started</span>
                  <span>{stage.started_at ? formatDate(stage.started_at) : "—"}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Finished</span>
                  <span>{stage.finished_at ? formatDate(stage.finished_at) : "—"}</span>
                </div>
              </div>

              {(stage.outcome_reason_code || stage.outcome_reason_detail) && (
                <div className="rounded-md border bg-muted/20 p-3 text-xs">
                  <p className="font-medium">Outcome reason: {stage.outcome_reason_code ?? "unspecified"}</p>
                  {stage.outcome_reason_detail && <p className="mt-1 text-muted-foreground">{stage.outcome_reason_detail}</p>}
                </div>
              )}

              {stage.content !== null && stage.content !== undefined && stage.content !== "" && (
                <>
                  <Separator />
                  <div>
                    <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                      Content
                    </p>
                    <div
                      className={
                        "rounded-md border p-3 text-xs whitespace-pre-wrap max-h-40 overflow-y-auto " +
                        (stage.status === "failed"
                          ? "border-destructive/40 bg-destructive/10 text-destructive font-medium"
                          : "bg-muted/30 font-mono")
                      }
                    >
                      {stage.content}
                    </div>
                  </div>
                </>
              )}

              <Separator />
              <div>
                <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Output
                </p>
                <StageOutputView stageName={stage.name} output={stage.output} />
              </div>

              {/* C3 requirements addendum 2: active hash verification, only
                  on the custody stage (the sha256 belongs to the whole run's
                  source file, not to individual parse/store/knowledge
                  stages). */}
              {stage.name.toLowerCase() === "custody" && (
                <>
                  <Separator />
                  <div>
                    <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                      Custody — Verify
                    </p>
                    <VerifyPanel sha256={sha256} />
                  </div>
                </>
              )}
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}
