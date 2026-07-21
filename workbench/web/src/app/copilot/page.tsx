// Byline: Claude Code · Sonnet (agent) · 2026-07-21
/**
 * Ops Copilot (C2.5) — a chat pane over the platform's existing headless
 * OpenCode server. No nav entry: app-sidebar.tsx is out of this build's
 * scope (parallel sprint collision rules — see build notes), so this page
 * is reachable by URL only (/copilot) until a future pass wires the nav.
 */
import { CopilotChat } from "@/components/copilot/copilot-chat";

export default function CopilotPage() {
  return (
    <div className="flex h-full flex-col space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Ops Copilot</h1>
        <p className="text-sm text-muted-foreground">
          Ask about a run, a staged file, or anything else — backed by the platform&apos;s OpenCode server.
        </p>
      </div>
      <CopilotChat />
    </div>
  );
}
