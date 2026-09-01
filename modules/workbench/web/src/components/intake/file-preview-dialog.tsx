// Byline: Claude Code · Sonnet (agent) · 2026-07-22 (C3: Dry-run parse button — "the real parser candidates")
"use client";

/**
 * Full-text preview + Analyze pane for a staged file (C2.7 owner scope
 * addition, 2026-07-21): "the owner can't see what staged files contain."
 *
 * Opened from a "Preview" row action on the Intake table AND from a button
 * inside FileDetailDialog (stacked on top of it) — both pass the same
 * `StagedFile`. Fetches the FULL untruncated text via GET
 * /api/files/{id}/text on open (StagedFile.text, when present, is capped by
 * the detail endpoint — see service/files.py's TEXT_PREVIEW_CHARS). The
 * "Analyze" button is a separate on-demand POST /api/files/{id}/analyze
 * call (not run automatically) since it re-parses the full text server-side
 * — the owner asked for "identify format before running", not an always-on
 * cost on every preview open.
 *
 * "Dry-run parse" (C3, requirements addendum 1) is a THIRD on-demand call —
 * distinct from Analyze's basic detect.py sniffing — that asks the spine
 * which real parser(s) would claim this file, without starting a run.
 * `file.id` is the staged file's sha256 (staging.py keys `staged_files` by
 * content hash), forwarded as-is to POST /api/runs/parse-dryrun.
 */
import { useEffect, useState } from "react";
import { Copy, Check, FlaskConical, Sparkles, WrapText, AlignLeft } from "lucide-react";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError, analyzeFile, getFileText, parseDryrunSha } from "@/lib/api-client";
import { humanizeBytes } from "@/lib/utils";
import type { FileAnalysis, ParseDryrunResponse, StagedFile } from "@/lib/shared/types";

interface FilePreviewDialogProps {
  file: StagedFile | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function FilePreviewDialog({ file, open, onOpenChange }: FilePreviewDialogProps) {
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [wrap, setWrap] = useState(true);
  const [copied, setCopied] = useState(false);
  const [analysis, setAnalysis] = useState<FileAnalysis | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [dryrun, setDryrun] = useState<ParseDryrunResponse | null>(null);
  const [dryrunning, setDryrunning] = useState(false);

  useEffect(() => {
    if (!open || !file) return;
    queueMicrotask(() => {
      setText("");
      setAnalysis(null);
      setDryrun(null);
      setLoading(true);
      getFileText(file.id)
        .then((res) => setText(res.text))
        .catch((err) => {
          const detail = err instanceof ApiError ? err.message : "Failed to load file text";
          toast.error(detail);
        })
        .finally(() => setLoading(false));
    });
  }, [open, file]);

  if (!file) return null;

  const hasText = text.trim().length > 0;

  const handleAnalyze = async () => {
    setAnalyzing(true);
    try {
      const result = await analyzeFile(file.id);
      setAnalysis(result);
    } catch (err) {
      const detail = err instanceof ApiError ? err.message : "Analyze failed";
      toast.error(detail);
    } finally {
      setAnalyzing(false);
    }
  };

  const handleDryrun = async () => {
    setDryrunning(true);
    try {
      const result = await parseDryrunSha(file.id);
      setDryrun(result);
    } catch (err) {
      const detail = err instanceof ApiError ? err.message : "Dry-run parse failed";
      toast.error(detail);
    } finally {
      setDryrunning(false);
    }
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(text).catch(() => {});
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="truncate">{file.name}</DialogTitle>
        </DialogHeader>

        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="outline" size="sm" onClick={handleAnalyze} disabled={analyzing}>
              <Sparkles className="h-3.5 w-3.5 mr-1" />
              {analyzing ? "Analyzing…" : "Analyze"}
            </Button>
            <Button variant="outline" size="sm" onClick={handleDryrun} disabled={dryrunning}>
              <FlaskConical className="h-3.5 w-3.5 mr-1" />
              {dryrunning ? "Dry-running…" : "Dry-run parse"}
            </Button>
            {hasText && (
              <>
                <Button variant="outline" size="sm" onClick={() => setWrap((w) => !w)}>
                  {wrap ? (
                    <AlignLeft className="h-3.5 w-3.5 mr-1" />
                  ) : (
                    <WrapText className="h-3.5 w-3.5 mr-1" />
                  )}
                  {wrap ? "No wrap" : "Wrap"}
                </Button>
                <Button variant="outline" size="sm" onClick={handleCopy}>
                  {copied ? (
                    <Check className="h-3.5 w-3.5 mr-1" />
                  ) : (
                    <Copy className="h-3.5 w-3.5 mr-1" />
                  )}
                  Copy
                </Button>
              </>
            )}
            <span className="ml-auto text-xs text-muted-foreground">
              {humanizeBytes(file.size)} · {file.mime}
            </span>
          </div>

          {analysis && (
            <div className="rounded-md border bg-muted/30 p-3 space-y-2 text-xs">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium">Detected type</span>
                <Badge variant="outline">{analysis.detected_type}</Badge>
                {analysis.current_detected_type &&
                  analysis.current_detected_type !== analysis.detected_type && (
                    <span className="text-amber-600 dark:text-amber-400">
                      (currently recorded as {analysis.current_detected_type})
                    </span>
                  )}
              </div>
              <p className="text-muted-foreground">{analysis.evidence}</p>
              <div className="flex flex-wrap gap-x-4 gap-y-1 text-muted-foreground pt-1">
                <span>size: {humanizeBytes(analysis.shape.size)}</span>
                <span>mime: {analysis.shape.mime}</span>
                <span>text length: {analysis.shape.text_length.toLocaleString()}</span>
                <span>lines: {analysis.shape.line_count.toLocaleString()}</span>
                <span>JSON-parseable: {analysis.shape.is_json_parseable ? "yes" : "no"}</span>
              </div>
            </div>
          )}

          {dryrun && (
            <div className="rounded-md border bg-muted/30 p-3 space-y-2 text-xs">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium">Parser candidates</span>
                {dryrun.parser_id ? (
                  <Badge variant="default">{dryrun.parser_id}</Badge>
                ) : (
                  <Badge variant="destructive">no parser claimed this file</Badge>
                )}
                <span className="text-muted-foreground">{dryrun.record_count} records</span>
              </div>
              {dryrun.attempts.length > 0 && (
                <div className="space-y-1">
                  {dryrun.attempts.map((attempt, i) => (
                    <div key={`${attempt.tool}-${i}`} className="flex items-center gap-2">
                      <Badge variant={attempt.ok ? "outline" : "secondary"} className="shrink-0">
                        {attempt.ok ? "ok" : "skip"}
                      </Badge>
                      <span className="font-mono">{attempt.tool}</span>
                      {attempt.confidence !== undefined && (
                        <span className="text-muted-foreground">conf {attempt.confidence.toFixed(2)}</span>
                      )}
                      {attempt.error && <span className="text-destructive truncate">{attempt.error}</span>}
                    </div>
                  ))}
                </div>
              )}
              {dryrun.sample_records.length > 0 && (
                <div>
                  <p className="mb-1 font-medium">Sample records</p>
                  <div className="max-h-40 space-y-1 overflow-y-auto">
                    {dryrun.sample_records.map((sample, i) => (
                      <pre key={i} className="overflow-x-auto rounded border bg-background p-1.5 whitespace-pre-wrap">
                        {sample}
                      </pre>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {loading ? (
            <div className="space-y-2">
              {Array.from({ length: 10 }).map((_, i) => (
                <Skeleton key={i} className="h-4 w-full" />
              ))}
            </div>
          ) : hasText ? (
            <pre
              className={`max-h-[55vh] overflow-auto rounded-md border bg-muted/30 p-3 text-xs font-mono ${
                wrap ? "whitespace-pre-wrap break-words" : "whitespace-pre"
              }`}
            >
              {text}
            </pre>
          ) : (
            <div className="rounded-md border bg-muted/30 p-4 text-sm text-muted-foreground">
              No text extracted at staging — parsed at run time. This is normal for binary
              formats (PDF/DOCX/images); run Analyze above for basic file-shape stats, or start a
              run to see it parsed.
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
