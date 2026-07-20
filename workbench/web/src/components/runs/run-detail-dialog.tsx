// Byline: Claude Code · Sonnet (agent) · 2026-07-20
"use client";

/**
 * Run detail: the stage rail plus per-run metadata, opened as a Dialog from
 * a Runs-table row (mirrors the existing FileDetailDialog pattern rather
 * than a Next.js dynamic route — this app is a static export with
 * `output: 'export'`, so a `/runs/[id]` route would need
 * `generateStaticParams` enumerating every run id at BUILD time, which
 * can't work for runs created after deploy).
 *
 * Polls `GET /api/runs/{id}` every 2s while status === "running", stopping
 * on any terminal status (or when the dialog closes).
 */
import { useEffect, useRef, useState } from "react";
import { AlertTriangle } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { StageRail } from "./stage-rail";
import { StageDrawer } from "./stage-drawer";
import { getRun } from "@/lib/api-client";
import { formatDate } from "@/lib/utils";
import type { RunDetail, RunStageDetail } from "@/lib/shared/types";

const POLL_INTERVAL_MS = 2000;

interface RunDetailDialogProps {
  runId: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function statusBadgeVariant(status: string): "default" | "secondary" | "destructive" | "outline" {
  switch (status) {
    case "completed":
      return "default";
    case "running":
      return "secondary";
    case "failed":
      return "destructive";
    default:
      return "outline";
  }
}

export function RunDetailDialog({ runId, open, onOpenChange }: RunDetailDialogProps) {
  const [run, setRun] = useState<RunDetail | null>(null);
  const [selectedSeq, setSelectedSeq] = useState<number | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = () => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  };

  useEffect(() => {
    if (!open || !runId) {
      stopPolling();
      setRun(null);
      return;
    }

    let cancelled = false;
    const fetchRun = async () => {
      try {
        const data = await getRun(runId);
        if (!cancelled) {
          setRun(data);
          if (data.status !== "running") stopPolling();
        }
      } catch {
        // Transient poll failure — keep the last-known state, try again next tick.
      }
    };

    fetchRun();
    intervalRef.current = setInterval(fetchRun, POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      stopPolling();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, runId]);

  const handleSelectStage = (seq: number) => {
    setSelectedSeq(seq);
    setDrawerOpen(true);
  };

  const selectedStage: RunStageDetail | null =
    run?.stages.find((s) => s.seq === selectedSeq) ?? null;
  const failedStage = run?.stages.find((s) => s.status === "failed");

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 truncate">
              {run?.source_name ?? runId}
              {run && <Badge variant={statusBadgeVariant(run.status)}>{run.status}</Badge>}
            </DialogTitle>
            {run && (
              <DialogDescription>
                {run.workflow} · {run.domain || "no domain"} · {run.mode}
              </DialogDescription>
            )}
          </DialogHeader>

          {!run ? (
            <p className="py-8 text-center text-sm text-muted-foreground">Loading…</p>
          ) : (
            <div className="space-y-4">
              <StageRail stages={run.stages} variant="full" activeSeq={selectedSeq ?? undefined} onSelect={handleSelectStage} />

              {failedStage && (
                <div className="flex items-start gap-2 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm">
                  <AlertTriangle className="mt-0.5 size-4 shrink-0 text-destructive" />
                  <div>
                    <p className="font-medium text-destructive">
                      Stage &quot;{failedStage.name}&quot; failed
                    </p>
                    {failedStage.content && (
                      <p className="mt-0.5 whitespace-pre-wrap text-xs text-destructive/90">
                        {failedStage.content}
                      </p>
                    )}
                  </div>
                </div>
              )}

              {/* run.error is set only when an exception escaped the runner
                  itself (rare) — distinct from a per-stage failure above,
                  which is how most failures actually surface. */}
              {run.error && (
                <div className="flex items-start gap-2 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm">
                  <AlertTriangle className="mt-0.5 size-4 shrink-0 text-destructive" />
                  <div>
                    <p className="font-medium text-destructive">Run error</p>
                    <p className="mt-0.5 whitespace-pre-wrap text-xs text-destructive/90">{run.error}</p>
                  </div>
                </div>
              )}

              <Separator />
              <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Run ID</span>
                  <span className="truncate font-mono text-xs">{run.run_id}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">sha256</span>
                  <span className="truncate font-mono text-xs">{run.sha256}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Created</span>
                  <span>{formatDate(run.created_at)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Updated</span>
                  <span>{formatDate(run.updated_at)}</span>
                </div>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      <StageDrawer stage={selectedStage} open={drawerOpen} onOpenChange={setDrawerOpen} />
    </>
  );
}
