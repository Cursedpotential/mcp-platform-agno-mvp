// Byline: Claude Code · Sonnet (agent) · 2026-07-22 (C3: Evidence Queue — requirements addendum 6)
"use client";

/**
 * The evidence-gathering worklist: open flags grouped by evidence_wanted
 * type (a flag with multiple wanted types appears in each of its groups;
 * flags with none land in an "unspecified" bucket), claim + date range +
 * target link, and status transitions (open -> partial ->
 * corroborated/unobtainable) with notes.
 *
 * Target navigation: a `run` target links to the Records page pre-scoped to
 * that run (`/records?run_id=...`, read by RecordsBrowser's
 * useSearchParams). A `record` target has no run_id on the flag itself to
 * deep-link with (GET /v1/flags per the C3 contract carries target_kind/
 * target_id only) — this is a real, documented gap; the record's ID is
 * shown with a copy button instead of a broken/guessed link.
 */
import { useEffect, useState } from "react";
import Link from "next/link";
import { Copy, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { ApiError, listFlags, updateFlag } from "@/lib/api-client";
import { EVIDENCE_WANTED_OPTIONS, type Flag, type FlagStatus } from "@/lib/shared/types";

const STATUS_OPTIONS: Array<{ value: FlagStatus | "all"; label: string }> = [
  { value: "open", label: "Open" },
  { value: "partial", label: "Partial" },
  { value: "corroborated", label: "Corroborated" },
  { value: "unobtainable", label: "Unobtainable" },
  { value: "all", label: "All statuses" },
];

const NEXT_STATUS: Record<FlagStatus, FlagStatus[]> = {
  open: ["partial", "corroborated", "unobtainable"],
  partial: ["corroborated", "unobtainable", "open"],
  corroborated: ["open"],
  unobtainable: ["open"],
};

function dateRange(flag: Flag): string | null {
  if (!flag.claim_date_start && !flag.claim_date_end) return null;
  const start = flag.claim_date_start ?? "?";
  const end = flag.claim_date_end ?? "?";
  return start === end ? start : `${start} — ${end}`;
}

function FlagCard({ flag, onChanged }: { flag: Flag; onChanged: () => void }) {
  const [notesDraft, setNotesDraft] = useState(flag.notes ?? "");
  const [saving, setSaving] = useState(false);
  const range = dateRange(flag);

  const handleStatus = async (status: FlagStatus) => {
    setSaving(true);
    try {
      await updateFlag(flag.id, { status });
      toast.success(`Flag marked ${status}`);
      onChanged();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Failed to update flag");
    } finally {
      setSaving(false);
    }
  };

  const handleSaveNotes = async () => {
    setSaving(true);
    try {
      await updateFlag(flag.id, { notes: notesDraft });
      toast.success("Notes saved");
      onChanged();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Failed to save notes");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-2 rounded-md border p-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <p className="text-sm font-medium">{flag.claim}</p>
        <Badge variant="outline" className="capitalize shrink-0">
          {flag.status}
        </Badge>
      </div>

      <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        {range && <span>{range}</span>}
        {flag.evidence_wanted?.map((t) => (
          <Badge key={t} variant="secondary" className="capitalize">
            {t}
          </Badge>
        ))}
        {flag.target_kind === "run" ? (
          <Link href={`/records?run_id=${encodeURIComponent(flag.target_id)}`} className="underline underline-offset-2">
            View run&apos;s records
          </Link>
        ) : (
          <button
            type="button"
            className="inline-flex items-center gap-1 underline underline-offset-2"
            onClick={() => {
              navigator.clipboard.writeText(flag.target_id).catch(() => {});
              toast.success("Record ID copied");
            }}
          >
            <Copy className="size-3" />
            {flag.target_kind}: {flag.target_id.slice(0, 12)}…
          </button>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-1.5 pt-1">
        {(NEXT_STATUS[flag.status] ?? []).map((next) => (
          <Button key={next} size="sm" variant="outline" disabled={saving} onClick={() => handleStatus(next)}>
            Mark {next}
          </Button>
        ))}
      </div>

      <div className="flex gap-2 pt-1">
        <Textarea
          value={notesDraft}
          onChange={(e) => setNotesDraft(e.target.value)}
          placeholder="Notes…"
          rows={1}
          className="text-xs"
        />
        <Button size="sm" variant="outline" disabled={saving || notesDraft === (flag.notes ?? "")} onClick={handleSaveNotes}>
          Save
        </Button>
      </div>

      {flag.link_artifact && (
        <p className="text-xs text-muted-foreground">
          Corroborated by artifact <span className="font-mono">{flag.link_artifact.sha256.slice(0, 16)}…</span>
        </p>
      )}
    </div>
  );
}

export function FlagsQueue() {
  const [statusFilter, setStatusFilter] = useState<FlagStatus | "all">("open");
  const [flags, setFlags] = useState<Flag[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchFlags = () => {
    setLoading(true);
    listFlags({ status: statusFilter === "all" ? undefined : statusFilter })
      .then(setFlags)
      .catch((err) => {
        setFlags([]);
        toast.error(err instanceof ApiError ? err.message : "Failed to load flags");
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    queueMicrotask(fetchFlags);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter]);

  // Group by evidence_wanted type; flags with none land in "unspecified".
  const groups = new Map<string, Flag[]>();
  for (const flag of flags) {
    const types = flag.evidence_wanted?.length ? flag.evidence_wanted : ["unspecified"];
    for (const t of types) {
      if (!groups.has(t)) groups.set(t, []);
      groups.get(t)!.push(flag);
    }
  }
  const orderedGroupKeys = [...EVIDENCE_WANTED_OPTIONS, "unspecified"].filter((k) => groups.has(k));

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-4 flex-wrap">
        <CardTitle>Evidence Queue</CardTitle>
        <div className="flex items-center gap-2">
          <Label htmlFor="flags-status-filter" className="sr-only">
            Status
          </Label>
          <select
            id="flags-status-filter"
            className="h-9 rounded-md border border-input bg-transparent px-3 text-sm outline-none focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px]"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as FlagStatus | "all")}
          >
            {STATUS_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
          <Button variant="outline" size="sm" onClick={fetchFlags}>
            <RefreshCw className="h-4 w-4 mr-1" />
            Refresh
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        {loading && flags.length === 0 ? (
          <div className="space-y-2">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-20 w-full" />
            ))}
          </div>
        ) : flags.length === 0 ? (
          <p className="text-sm text-muted-foreground py-12 text-center">
            No {statusFilter === "all" ? "" : statusFilter} flags — nothing waiting on corroborating evidence.
          </p>
        ) : (
          orderedGroupKeys.map((key) => (
            <div key={key} className="space-y-2">
              <h3 className="text-sm font-semibold capitalize">
                {key} <span className="text-muted-foreground font-normal">({groups.get(key)!.length})</span>
              </h3>
              <div className="space-y-2">
                {groups.get(key)!.map((flag) => (
                  <FlagCard key={`${key}-${flag.id}`} flag={flag} onChanged={fetchFlags} />
                ))}
              </div>
            </div>
          ))
        )}
      </CardContent>
    </Card>
  );
}
