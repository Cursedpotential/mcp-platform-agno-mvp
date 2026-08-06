// Byline: Claude Code · Sonnet (agent) · 2026-07-22 (C3: record browser detail — split-boundary view, curation, verify, flag)
"use client";

/**
 * Record detail drawer — the parse-quality eyeball surface (requirements
 * addendum 1). Opened from a row in records-browser.tsx; receives the FULL
 * currently-loaded records array (already sorted by idx) plus the selected
 * index so prev/next can walk split boundaries within the same artifact
 * without a re-fetch. That assumption holds whenever the browser is scoped
 * to one run/artifact (the primary use case); a broad, unscoped search
 * still opens fine, prev/next just walks across whatever's loaded.
 *
 * Curation (title/label chips) is read from `record.attrs.title` /
 * `record.attrs.labels` — the GET /v1/records contract doesn't list
 * top-level title/labels fields on a record row (only `attrs`), while PATCH
 * /v1/records/{id}/meta accepts `{title?, labels?, attrs_patch?}` as
 * separate params; the natural reconciliation (ASSUMPTION, since the spine
 * is a parallel build) is that the spine merges title/labels into `attrs`
 * server-side, so a subsequent GET surfaces them there.
 */
import { useEffect, useState } from "react";
import { AlignLeft, ChevronLeft, ChevronRight, Flag as FlagIcon, Type, WrapText } from "lucide-react";
import { toast } from "sonner";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { VerifyPanel } from "@/components/shared/verify-panel";
import { FlagDialog } from "@/components/flags/flag-dialog";
import { ApiError, patchRecordMeta } from "@/lib/api-client";
import { formatDate } from "@/lib/utils";
import type { RecordRow } from "@/lib/shared/types";

interface RecordDetailDrawerProps {
  records: RecordRow[];
  selectedId: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSelect: (id: string) => void;
  /** The run's sha256, if the browser is scoped to one run (Verify action). */
  sha256?: string | null;
  /** Called after a curation PATCH succeeds, so the parent can refresh its list. */
  onRecordUpdated?: (updated: RecordRow) => void;
}

function labelsOf(record: RecordRow): string[] {
  const raw = record.attrs?.labels;
  return Array.isArray(raw) ? raw.filter((l): l is string => typeof l === "string") : [];
}

function titleOf(record: RecordRow): string {
  const raw = record.attrs?.title;
  return typeof raw === "string" ? raw : "";
}

export function RecordDetailDrawer({
  records,
  selectedId,
  open,
  onOpenChange,
  onSelect,
  sha256,
  onRecordUpdated,
}: RecordDetailDrawerProps) {
  const [wrap, setWrap] = useState(true);
  const [mono, setMono] = useState(true);
  const [titleDraft, setTitleDraft] = useState("");
  const [labelDraft, setLabelDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const [flagOpen, setFlagOpen] = useState(false);

  const index = records.findIndex((r) => r.id === selectedId);
  const record = index >= 0 ? records[index] : null;
  const prev = index > 0 ? records[index - 1] : null;
  const next = index >= 0 && index < records.length - 1 ? records[index + 1] : null;

  useEffect(() => {
    queueMicrotask(() => setTitleDraft(record ? titleOf(record) : ""));
  }, [record]);

  if (!record) return null;

  const labels = labelsOf(record);

  const handleSaveTitle = async () => {
    setSaving(true);
    try {
      const updated = await patchRecordMeta(record.id, { title: titleDraft });
      toast.success("Title saved");
      onRecordUpdated?.(updated);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Failed to save title");
    } finally {
      setSaving(false);
    }
  };

  const handleAddLabel = async () => {
    const next = labelDraft.trim();
    if (!next || labels.includes(next)) {
      setLabelDraft("");
      return;
    }
    setSaving(true);
    try {
      const updated = await patchRecordMeta(record.id, { labels: [...labels, next] });
      setLabelDraft("");
      onRecordUpdated?.(updated);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Failed to add label");
    } finally {
      setSaving(false);
    }
  };

  const handleRemoveLabel = async (label: string) => {
    setSaving(true);
    try {
      const updated = await patchRecordMeta(record.id, { labels: labels.filter((l) => l !== label) });
      onRecordUpdated?.(updated);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Failed to remove label");
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <Sheet open={open} onOpenChange={onOpenChange}>
        <SheetContent className="w-full sm:max-w-2xl overflow-y-auto">
          <SheetHeader>
            <SheetTitle className="flex items-center gap-2">
              Record #{record.idx}
              <Badge variant="outline">{record.record_type}</Badge>
              {record.role && <Badge variant="secondary">{record.role}</Badge>}
            </SheetTitle>
            <SheetDescription>
              {record.ts ? formatDate(record.ts) : "no timestamp"} · {record.full_len.toLocaleString()} chars
            </SheetDescription>
          </SheetHeader>

          <div className="space-y-4 px-4 pb-4">
            {/* Split-boundary nav: walk idx order within the loaded set */}
            <div className="flex items-center justify-between rounded-md border p-2">
              <Button
                size="sm"
                variant="outline"
                disabled={!prev}
                onClick={() => prev && onSelect(prev.id)}
              >
                <ChevronLeft className="size-4" />
                Prev
              </Button>
              <span className="text-xs text-muted-foreground">
                {index + 1} of {records.length}
              </span>
              <Button
                size="sm"
                variant="outline"
                disabled={!next}
                onClick={() => next && onSelect(next.id)}
              >
                Next
                <ChevronRight className="size-4" />
              </Button>
            </div>

            <Button size="sm" variant="outline" onClick={() => setFlagOpen(true)}>
              <FlagIcon className="size-4" />
              Flag for evidence
            </Button>

            <Separator />

            {/* Curation: title + label chips (analysis-lane metadata only) */}
            <div className="space-y-2">
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Curation</p>
              <div className="flex gap-2">
                <Input
                  value={titleDraft}
                  onChange={(e) => setTitleDraft(e.target.value)}
                  placeholder="Title this record…"
                  disabled={saving}
                />
                <Button size="sm" onClick={handleSaveTitle} disabled={saving || titleDraft === titleOf(record)}>
                  Save
                </Button>
              </div>
              <div className="flex flex-wrap items-center gap-1.5">
                {labels.map((label) => (
                  <Badge key={label} variant="secondary" className="gap-1">
                    {label}
                    <button
                      type="button"
                      onClick={() => handleRemoveLabel(label)}
                      disabled={saving}
                      className="ml-0.5 opacity-70 hover:opacity-100"
                      aria-label={`Remove label ${label}`}
                    >
                      ×
                    </button>
                  </Badge>
                ))}
                <Input
                  value={labelDraft}
                  onChange={(e) => setLabelDraft(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      handleAddLabel();
                    }
                  }}
                  placeholder="add label…"
                  disabled={saving}
                  className="h-7 w-28 text-xs"
                />
              </div>
            </div>

            <Separator />

            {/* Full text */}
            <div>
              <div className="mb-1.5 flex items-center justify-between">
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Text</p>
                <div className="flex gap-1">
                  <Button size="icon-xs" variant="ghost" onClick={() => setWrap((w) => !w)} title="Toggle wrap">
                    {wrap ? <AlignLeft className="size-3" /> : <WrapText className="size-3" />}
                  </Button>
                  <Button size="icon-xs" variant="ghost" onClick={() => setMono((m) => !m)} title="Toggle monospace">
                    <Type className="size-3" />
                  </Button>
                </div>
              </div>
              <pre
                className={`max-h-96 overflow-auto rounded-md border bg-muted/30 p-3 text-xs ${
                  mono ? "font-mono" : "font-sans"
                } ${wrap ? "whitespace-pre-wrap break-words" : "whitespace-pre"}`}
              >
                {record.text}
              </pre>
            </div>

            <Separator />

            {/* Attrs */}
            <div>
              <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Attrs
              </p>
              <pre className="max-h-64 overflow-auto rounded-md border bg-muted/30 p-3 text-xs">
                {JSON.stringify(record.attrs, null, 2)}
              </pre>
            </div>

            <Separator />

            {/* Verify (C3 addendum 2) — only meaningful when scoped to a run */}
            <div>
              <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Custody — Verify
              </p>
              <VerifyPanel sha256={sha256} />
            </div>
          </div>
        </SheetContent>
      </Sheet>

      <FlagDialog
        open={flagOpen}
        onOpenChange={setFlagOpen}
        targetKind="record"
        targetId={record.id}
        claimPrefill={record.text.slice(0, 300)}
      />
    </>
  );
}
