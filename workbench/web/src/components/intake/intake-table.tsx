// Byline: Claude Code · Sonnet (agent) · 2026-07-21 (C2.7: routing-hint relabel + Preview action)
"use client";

/**
 * The Intake table — renamed/rewritten from file-browser.tsx. The Promote
 * button is gone (owner rejected the upload->promote blind-box UX); each
 * row's action is now "Start run ->", which opens the New-run dialog
 * prefilled with that staged file (see lib/new-run-dialog-context.tsx).
 * Metadata editing + the detail view (FileDetailDialog) stay.
 *
 * C2.7 additions: the "Domain" column is a routing hint, not a
 * classification (requirements addenda 7-8) — header relabeled
 * accordingly. A "Preview" row action opens FilePreviewDialog with the
 * staged file's full extracted text + an on-demand Analyze pass (owner
 * scope addition, 2026-07-21).
 */
import { useCallback, useEffect, useState } from "react";
import { RefreshCw, Eye, ArrowRight, FileSearch } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { FileDetailDialog } from "./file-detail-dialog";
import { FilePreviewDialog } from "./file-preview-dialog";
import { listFiles } from "@/lib/api-client";
import { humanizeBytes, formatDate } from "@/lib/utils";
import { useRefresh } from "@/lib/refresh-context";
import { useNewRunDialog } from "@/lib/new-run-dialog-context";
import type { StagedFile, StagedStatus, DetectedType } from "@/lib/shared/types";

const STATUS_OPTIONS: Array<{ value: StagedStatus | "all"; label: string }> = [
  { value: "all", label: "All statuses" },
  { value: "staged", label: "Staged" },
  { value: "promoting", label: "Promoting" },
  { value: "promoted", label: "Promoted" },
  { value: "failed", label: "Failed" },
];

const TYPE_OPTIONS: Array<{ value: DetectedType | "all"; label: string }> = [
  { value: "all", label: "All types" },
  { value: "doc", label: "Document" },
  { value: "chat_export", label: "Chat export" },
];

function statusVariant(
  status: StagedStatus,
): "default" | "secondary" | "destructive" | "outline" {
  switch (status) {
    case "promoted":
      return "default";
    case "promoting":
      return "secondary";
    case "failed":
      return "destructive";
    default:
      return "outline";
  }
}

export function IntakeTable() {
  const [files, setFiles] = useState<StagedFile[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<StagedStatus | "all">("all");
  const [typeFilter, setTypeFilter] = useState<DetectedType | "all">("all");
  const [detailFile, setDetailFile] = useState<StagedFile | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [previewFile, setPreviewFile] = useState<StagedFile | null>(null);
  const [previewOpen, setPreviewOpen] = useState(false);
  const { refreshKey } = useRefresh();
  const { openNewRun } = useNewRunDialog();

  const fetchFiles = useCallback(() => {
    setLoading(true);
    listFiles({
      status: statusFilter === "all" ? undefined : statusFilter,
      detected_type: typeFilter === "all" ? undefined : typeFilter,
    })
      .then(setFiles)
      .catch(() => {
        setFiles([]);
        toast.error("Failed to load staged files");
      })
      .finally(() => setLoading(false));
  }, [statusFilter, typeFilter]);

  useEffect(() => {
    fetchFiles();
  }, [fetchFiles, refreshKey]);

  const handleOpenDetail = (file: StagedFile) => {
    setDetailFile(file);
    setDetailOpen(true);
  };

  const handleOpenPreview = (file: StagedFile) => {
    setPreviewFile(file);
    setPreviewOpen(true);
  };

  const handleDetailUpdated = (updated: StagedFile) => {
    setFiles((prev) => prev.map((f) => (f.id === updated.id ? updated : f)));
    setDetailFile(updated);
  };

  return (
    <>
      <Card>
        <CardHeader className="flex flex-row items-center justify-between gap-4 flex-wrap">
          <CardTitle>Staged Files</CardTitle>
          <div className="flex items-center gap-2 flex-wrap">
            <select
              className="h-9 rounded-md border border-input bg-transparent px-3 text-sm outline-none focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px]"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as StagedStatus | "all")}
              aria-label="Filter by status"
            >
              {STATUS_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
            <select
              className="h-9 rounded-md border border-input bg-transparent px-3 text-sm outline-none focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px]"
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value as DetectedType | "all")}
              aria-label="Filter by detected type"
            >
              {TYPE_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
            <Button variant="outline" size="sm" onClick={fetchFiles}>
              <RefreshCw className="h-4 w-4 mr-1" />
              Refresh
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="space-y-2">
              {Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : files.length === 0 ? (
            <p className="text-sm text-muted-foreground py-12 text-center">
              No staged files found. Upload some files to get started.
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Size</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Routing hint</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Updated</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {files.map((file) => (
                  <TableRow key={file.id}>
                    <TableCell className="font-medium truncate max-w-[240px]">
                      {file.name}
                    </TableCell>
                    <TableCell>{humanizeBytes(file.size)}</TableCell>
                    <TableCell>
                      <Badge variant="outline">{file.detected_type}</Badge>
                    </TableCell>
                    <TableCell>{file.meta?.domain ?? "—"}</TableCell>
                    <TableCell>
                      <Badge variant={statusVariant(file.status)}>{file.status}</Badge>
                    </TableCell>
                    <TableCell>{formatDate(file.updated_at)}</TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleOpenPreview(file)}
                        >
                          <FileSearch className="h-3.5 w-3.5 mr-1" />
                          Preview
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8"
                          onClick={() => handleOpenDetail(file)}
                        >
                          <Eye className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => openNewRun({ stagedId: file.id, name: file.name })}
                        >
                          Start run
                          <ArrowRight className="h-3.5 w-3.5 ml-1" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <FileDetailDialog
        file={detailFile}
        open={detailOpen}
        onOpenChange={setDetailOpen}
        onUpdated={handleDetailUpdated}
      />

      <FilePreviewDialog file={previewFile} open={previewOpen} onOpenChange={setPreviewOpen} />
    </>
  );
}
