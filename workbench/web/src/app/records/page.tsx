// Byline: Claude Code · Sonnet (agent) · 2026-07-22 (C3: Records page — Suspense wraps useSearchParams for static export)
import { Suspense } from "react";
import { RecordsBrowser } from "@/components/records/records-browser";

export default function RecordsPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold tracking-tight">Records</h1>
      {/* RecordsBrowser reads useSearchParams() (run_id deep-link from the
          Evidence Queue) — Next's static export requires that call be
          wrapped in Suspense or the build fails. */}
      <Suspense fallback={<div className="h-9" />}>
        <RecordsBrowser />
      </Suspense>
    </div>
  );
}
