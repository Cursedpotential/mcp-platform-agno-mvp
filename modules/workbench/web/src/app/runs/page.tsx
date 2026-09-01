// Byline: Claude Code · Sonnet (agent) · 2026-07-20
import { RunsTable } from "@/components/runs/runs-table";

export default function RunsPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold tracking-tight">Runs</h1>
      <RunsTable />
    </div>
  );
}
