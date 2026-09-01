// Byline: Claude Code · Sonnet (agent) · 2026-07-22 (C3: Evidence Queue page)
import { FlagsQueue } from "@/components/flags/flags-queue";

export default function EvidenceQueuePage() {
  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold tracking-tight">Evidence Queue</h1>
      <FlagsQueue />
    </div>
  );
}
