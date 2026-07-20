// Byline: Claude Code · Sonnet (agent) · 2026-07-20
import { ToolExplorer } from "@/components/tools/tool-explorer";

export default function ToolsPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold tracking-tight">Tools</h1>
      <ToolExplorer />
    </div>
  );
}
