// Byline: Codex · GPT-5 · 2026-08-15 (case-scoped Knowledge MVP)
import { KnowledgeBrowser } from "@/components/knowledge/knowledge-browser";

export default function KnowledgePage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Knowledge</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Browse canonical case knowledge and inspect the separate Graphiti memory projection.
        </p>
      </div>
      <KnowledgeBrowser />
    </div>
  );
}
