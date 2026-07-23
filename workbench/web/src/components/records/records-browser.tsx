// Byline: Claude Code · Sonnet (agent) · 2026-07-22 (C3: parse-quality record browser — requirements addendum 1)
"use client";

/**
 * THE parse-quality review surface: filter by run (picker from GET
 * /api/runs) or an artifact sha256, paged table (idx/type/role/ts/text
 * preview), row -> detail drawer with split-boundary nav so segmentation is
 * eyeballable by hand (requirements addendum 1: "verify splitting +
 * semantics by eye").
 */
import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { RecordDetailDrawer } from "./record-detail-drawer";
import { ApiError, listRecords, listRuns } from "@/lib/api-client";
import { formatDate } from "@/lib/utils";
import type { RecordRow, RunSummary } from "@/lib/shared/types";

const PAGE_SIZE = 50;

export function RecordsBrowser() {
  // Deep-link support: the Evidence Queue's "View run's records" link opens
  // /records?run_id=... — read once on mount so the run picker below comes
  // up pre-scoped instead of the operator re-picking it by hand.
  const searchParams = useSearchParams();
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [runId, setRunId] = useState(() => searchParams.get("run_id") ?? "");
  const [artifactSha, setArtifactSha] = useState("");
  const [query, setQuery] = useState("");
  const [records, setRecords] = useState<RecordRow[]>([]);
  const [total, setTotal] = useState<number | undefined>(undefined);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);

  useEffect(() => {
    listRuns({ limit: 200 })
      .then(setRuns)
      .catch(() => setRuns([]));
  }, []);

  const selectedRun = runs.find((r) => r.run_id === runId);

  const fetchRecords = useCallback(() => {
    if (!runId && !artifactSha && !query) {
      setRecords([]);
      setTotal(undefined);
      return;
    }
    setLoading(true);
    listRecords({
      runId: runId || undefined,
      artifactId: artifactSha || undefined,
      q: query || undefined,
      limit: PAGE_SIZE,
      offset,
    })
      .then((res) => {
        setRecords(res.records);
        setTotal(res.total);
      })
      .catch((err) => {
        setRecords([]);
        toast.error(err instanceof ApiError ? err.message : "Failed to load records");
      })
      .finally(() => setLoading(false));
  }, [runId, artifactSha, query, offset]);

  useEffect(() => {
    fetchRecords();
  }, [fetchRecords]);

  // Reset to page 1 whenever the scope/search changes.
  useEffect(() => {
    setOffset(0);
  }, [runId, artifactSha, query]);

  const handleRecordUpdated = (updated: RecordRow) => {
    setRecords((prev) => prev.map((r) => (r.id === updated.id ? updated : r)));
  };

  const hasNext = total !== undefined ? offset + PAGE_SIZE < total : records.length === PAGE_SIZE;
  const hasPrev = offset > 0;

  return (
    <>
      <Card>
        <CardHeader className="flex flex-row flex-wrap items-end justify-between gap-4">
          <CardTitle>Records</CardTitle>
          <div className="flex flex-wrap items-end gap-2">
            <div className="space-y-1">
              <Label htmlFor="records-run-select" className="text-xs">
                Run
              </Label>
              <select
                id="records-run-select"
                className="h-9 rounded-md border border-input bg-transparent px-3 text-sm outline-none focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px]"
                value={runId}
                onChange={(e) => setRunId(e.target.value)}
              >
                <option value="">— any run —</option>
                {runs.map((r) => (
                  <option key={r.run_id} value={r.run_id}>
                    {r.source_name ?? r.run_id}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-1">
              <Label htmlFor="records-artifact-input" className="text-xs">
                Artifact sha256
              </Label>
              <Input
                id="records-artifact-input"
                value={artifactSha}
                onChange={(e) => setArtifactSha(e.target.value)}
                placeholder="sha256…"
                className="h-9 w-48 font-mono text-xs"
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="records-query-input" className="text-xs">
                Search text
              </Label>
              <Input
                id="records-query-input"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="q…"
                className="h-9 w-40"
              />
            </div>
            <Button variant="outline" size="sm" onClick={fetchRecords}>
              <RefreshCw className="h-4 w-4 mr-1" />
              Refresh
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {loading && records.length === 0 ? (
            <div className="space-y-2">
              {Array.from({ length: 8 }).map((_, i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : !runId && !artifactSha && !query ? (
            <p className="text-sm text-muted-foreground py-12 text-center">
              Pick a run, paste an artifact sha256, or search to browse records.
            </p>
          ) : records.length === 0 ? (
            <p className="text-sm text-muted-foreground py-12 text-center">No records found.</p>
          ) : (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-16">Idx</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>Role</TableHead>
                    <TableHead>Timestamp</TableHead>
                    <TableHead>Text preview</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {records.map((record) => (
                    <TableRow
                      key={record.id}
                      className="cursor-pointer"
                      onClick={() => {
                        setSelectedId(record.id);
                        setDetailOpen(true);
                      }}
                    >
                      <TableCell className="text-muted-foreground">{record.idx}</TableCell>
                      <TableCell>{record.record_type}</TableCell>
                      <TableCell>{record.role || "—"}</TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {record.ts ? formatDate(record.ts) : "—"}
                      </TableCell>
                      <TableCell className="max-w-md">
                        <div className="truncate text-sm">{record.text}</div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>

              <div className="flex items-center justify-between pt-3">
                <span className="text-xs text-muted-foreground">
                  {total !== undefined
                    ? `${offset + 1}–${Math.min(offset + PAGE_SIZE, total)} of ${total}`
                    : `${offset + 1}–${offset + records.length}`}
                </span>
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={!hasPrev}
                    onClick={() => setOffset((o) => Math.max(0, o - PAGE_SIZE))}
                  >
                    Prev page
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={!hasNext}
                    onClick={() => setOffset((o) => o + PAGE_SIZE)}
                  >
                    Next page
                  </Button>
                </div>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      <RecordDetailDrawer
        records={records}
        selectedId={selectedId}
        open={detailOpen}
        onOpenChange={setDetailOpen}
        onSelect={setSelectedId}
        sha256={selectedRun?.sha256}
        onRecordUpdated={handleRecordUpdated}
      />
    </>
  );
}
