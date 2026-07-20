// Byline: Claude Code · Sonnet (agent) · 2026-07-20
"use client";

/**
 * The "New run" dialog — replaces the rejected upload-then-blind-promote
 * flow. Two sources: pick an already-staged file, or drop a fresh one
 * (which skips staging entirely and goes straight to the spine). Mounted
 * once near the app root (layout.tsx) and opened via useNewRunDialog() from
 * either the Runs page ("New run" button, no prefill) or the Intake page's
 * "Start run ->" row action (prefilled with that staged file).
 */
import { useEffect, useState } from "react";
import { toast } from "sonner";
import type { FileRejection } from "react-dropzone";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { Dropzone } from "@/components/upload/dropzone";
import { ApiError, createRunFromFile, createRunFromStaged, listFiles } from "@/lib/api-client";
import { useRefresh } from "@/lib/refresh-context";
import { useNewRunDialog } from "@/lib/new-run-dialog-context";
import { DOMAIN_OPTIONS, WORKFLOW_OPTIONS, type RunMode, type StagedFile, type Workflow } from "@/lib/shared/types";

type SourceMode = "staged" | "upload";

export function NewRunDialog() {
  const { open, prefill, closeNewRun } = useNewRunDialog();
  const { triggerRefresh } = useRefresh();

  const [sourceMode, setSourceMode] = useState<SourceMode>("staged");
  const [stagedFiles, setStagedFiles] = useState<StagedFile[]>([]);
  const [selectedStagedId, setSelectedStagedId] = useState("");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [workflow, setWorkflow] = useState<Workflow>("chat-transcript");
  const [domain, setDomain] = useState("");
  const [mode, setMode] = useState<RunMode>("auto");
  const [submitting, setSubmitting] = useState(false);

  // Reset on open, and seed from a row-action prefill if present.
  useEffect(() => {
    if (!open) return;
    setSourceMode("staged");
    setSelectedStagedId(prefill?.stagedId ?? "");
    setUploadFile(null);
    setWorkflow("chat-transcript");
    setDomain("");
    setMode("auto");
    listFiles({ status: "staged" })
      .then(setStagedFiles)
      .catch(() => setStagedFiles([]));
  }, [open, prefill]);

  const handleFilesRejected = (rejections: FileRejection[]) => {
    for (const r of rejections) {
      toast.error(`${r.file.name}: ${r.errors.map((e) => e.message).join(", ")}`);
    }
  };

  const handleSubmit = async () => {
    if (!domain) {
      toast.error("Pick a domain");
      return;
    }
    if (sourceMode === "staged" && !selectedStagedId) {
      toast.error("Pick a staged file");
      return;
    }
    if (sourceMode === "upload" && !uploadFile) {
      toast.error("Drop a file");
      return;
    }

    setSubmitting(true);
    try {
      const result =
        sourceMode === "staged"
          ? await createRunFromStaged({ stagedId: selectedStagedId, workflow, domain, mode })
          : await createRunFromFile({ file: uploadFile as File, workflow, domain, mode });
      toast.success(`Run ${result.run_id} started`);
      triggerRefresh();
      closeNewRun();
    } catch (err) {
      const detail = err instanceof ApiError ? err.message : "Failed to start run";
      toast.error(detail);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(next) => !next && closeNewRun()}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>New run</DialogTitle>
          <DialogDescription>
            Send a file through the evidence spine: custody -&gt; parse -&gt; store -&gt; knowledge.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="flex gap-2">
            <Button
              type="button"
              variant={sourceMode === "staged" ? "default" : "outline"}
              size="sm"
              onClick={() => setSourceMode("staged")}
            >
              Pick staged file
            </Button>
            <Button
              type="button"
              variant={sourceMode === "upload" ? "default" : "outline"}
              size="sm"
              onClick={() => setSourceMode("upload")}
            >
              Drop a new file
            </Button>
          </div>

          {sourceMode === "staged" ? (
            <div className="space-y-1.5">
              <Label htmlFor="staged-file-select">Staged file</Label>
              <select
                id="staged-file-select"
                className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-xs outline-none focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px]"
                value={selectedStagedId}
                onChange={(e) => setSelectedStagedId(e.target.value)}
              >
                <option value="">— choose a staged file —</option>
                {stagedFiles.map((f) => (
                  <option key={f.id} value={f.id}>
                    {f.name}
                  </option>
                ))}
              </select>
            </div>
          ) : (
            <Dropzone
              onFilesSelected={(files) => setUploadFile(files[0] ?? null)}
              onFilesRejected={handleFilesRejected}
              multiple={false}
            />
          )}
          {sourceMode === "upload" && uploadFile && (
            <p className="text-xs text-muted-foreground">Selected: {uploadFile.name}</p>
          )}

          <div className="space-y-1.5">
            <Label htmlFor="run-workflow-select">Workflow</Label>
            <select
              id="run-workflow-select"
              className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-xs outline-none focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px]"
              value={workflow}
              onChange={(e) => setWorkflow(e.target.value as Workflow)}
            >
              {WORKFLOW_OPTIONS.map((w) => (
                <option key={w} value={w}>
                  {w}
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="run-domain-select">Domain</Label>
            <select
              id="run-domain-select"
              className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-xs outline-none focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px]"
              value={domain}
              onChange={(e) => setDomain(e.target.value)}
            >
              <option value="">— choose a domain —</option>
              {DOMAIN_OPTIONS.map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-center justify-between rounded-md border p-3">
            <div className="space-y-0.5">
              <Label htmlFor="run-supervised-toggle">Supervised</Label>
              <p className="text-xs text-muted-foreground">
                Pause between stages for review instead of running straight through.
              </p>
            </div>
            <Tooltip>
              <TooltipTrigger asChild>
                <span>
                  <Switch
                    id="run-supervised-toggle"
                    checked={mode === "supervised"}
                    onCheckedChange={(checked) => setMode(checked ? "supervised" : "auto")}
                  />
                </span>
              </TooltipTrigger>
              <TooltipContent>Gates land in C2 — supervised runs still run straight through for now.</TooltipContent>
            </Tooltip>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={closeNewRun} disabled={submitting}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={submitting}>
            {submitting ? "Starting…" : "Start run"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
