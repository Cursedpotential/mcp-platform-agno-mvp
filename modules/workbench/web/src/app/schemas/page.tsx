// Byline: Claude Code · Sonnet (agent) · 2026-07-22 (C3: Schemas page)
// Byline: Codex · GPT-5 · 2026-08-16 (Data Explorer surface)
import { SchemasView } from "@/components/schemas/schemas-view";

export default function SchemasPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Data Explorer</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Inspect canonical PostgreSQL tables and supplemental Weaviate vectors without changing either store.
        </p>
      </div>
      <SchemasView />
    </div>
  );
}
