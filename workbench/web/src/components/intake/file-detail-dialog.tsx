// Byline: Claude Code · Sonnet (agent) · 2026-07-19
"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { ApiError, promoteFile, updateFileMeta } from "@/lib/api-client";
import { humanizeBytes, formatDate } from "@/lib/utils";
import { DOMAIN_OPTIONS, type StagedFile } from "@/lib/shared/types";

interface FileDetailDialogProps {
  file: StagedFile | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Called after a successful metadata save, with the server's updated record. */
  onUpdated: (file: StagedFile) => void;
  /** Called after a promote attempt (success or failure), with the merged record. */
  onPromoted: (file: StagedFile) => void;
}

/** Detail view for a staged file: text preview + metadata editor + promote. */
export function FileDetailDialog({
  file,
  open,
  onOpenChange,
  onUpdated,
  onPromoted,
}: FileDetailDialogProps) {
  const [domain, setDomain] = useState("");
  const [category, setCategory] = useState("");
  const [sourcePlatform, setSourcePlatform] = useState("");
  const [saving, setSaving] = useState(false);
  const [promoting, setPromoting] = useState(false);

  useEffect(() => {
    if (file) {
      setDomain(file.meta?.domain ?? "");
      setCategory(file.meta?.category ?? "");
      setSourcePlatform(file.meta?.source_platform ?? "");
    }
  }, [file]);

  if (!file) return null;

  const handleSave = async () => {
    setSaving(true);
    try {
      const updated = await updateFileMeta(file.id, {
        domain: domain || null,
        category: category || null,
        source_platform: sourcePlatform || null,
      });
      onUpdated(updated);
      toast.success("Metadata saved");
    } catch (err) {
      const detail = err instanceof ApiError ? err.message : "Failed to save metadata";
      toast.error(detail);
    } finally {
      setSaving(false);
    }
  };

  const handlePromote = async () => {
    setPromoting(true);
    try {
      const result = await promoteFile(file.id);
      onPromoted({
        ...file,
        status: result.status,
        promote_result: result.promote_result ?? file.promote_result,
      });
      if (result.status === "failed") {
        toast.error(`Promote failed${result.error ? `: ${result.error}` : ""}`);
      } else {
        toast.success("File promoted");
      }
    } catch (err) {
      const detail = err instanceof ApiError ? err.message : "Failed to promote file";
      toast.error(detail);
    } finally {
      setPromoting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="truncate">{file.name}</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Size</span>
              <span>{humanizeBytes(file.size)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">MIME</span>
              <span className="truncate max-w-[60%]">{file.mime}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Type</span>
              <Badge variant="outline">{file.detected_type}</Badge>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Status</span>
              <Badge>{file.status}</Badge>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Updated</span>
              <span>{formatDate(file.updated_at)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">R2 key</span>
              <span className="font-mono text-xs truncate max-w-[60%]">{file.r2_key}</span>
            </div>
          </div>

          <Separator />

          <div>
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1.5">
              Text preview
            </p>
            <div className="rounded-md border bg-muted/30 p-3 max-h-48 overflow-y-auto text-xs font-mono whitespace-pre-wrap">
              {file.text?.trim() ? file.text : "No text preview available for this file."}
            </div>
          </div>

          <Separator />

          <div className="space-y-3">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
              Metadata
            </p>
            <div className="space-y-1.5">
              <Label htmlFor="domain-select">Domain</Label>
              <select
                id="domain-select"
                className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-xs outline-none focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px]"
                value={domain}
                onChange={(e) => setDomain(e.target.value)}
              >
                <option value="">— none —</option>
                {DOMAIN_OPTIONS.map((d) => (
                  <option key={d} value={d}>
                    {d}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="category-input">Category</Label>
              <Input
                id="category-input"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                placeholder="optional"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="source-platform-input">Source platform</Label>
              <Input
                id="source-platform-input"
                value={sourcePlatform}
                onChange={(e) => setSourcePlatform(e.target.value)}
                placeholder="optional"
              />
            </div>
          </div>

          {file.promote_result != null && (
            <>
              <Separator />
              <div>
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1.5">
                  Promote result
                </p>
                <pre className="rounded-md border bg-muted/30 p-3 max-h-32 overflow-y-auto text-xs">
                  {JSON.stringify(file.promote_result, null, 2)}
                </pre>
              </div>
            </>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={handleSave} disabled={saving}>
            {saving ? "Saving…" : "Save metadata"}
          </Button>
          <Button
            onClick={handlePromote}
            disabled={promoting || file.status === "promoted" || file.status === "promoting"}
          >
            {promoting ? "Promoting…" : "Promote"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
