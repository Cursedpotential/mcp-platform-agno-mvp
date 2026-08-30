// Byline: Claude Code · Sonnet (agent) · 2026-07-20
// Byline: Codex · GPT-5.6-Sol · 2026-08-30 (monitored Atomic Tools surface)
import { AtomicTools } from "@/components/tools/atomic-tools";

export default function ToolsPage() {
  return (
    <div className="mx-auto w-full max-w-[1600px] space-y-5 px-5 py-6 lg:px-8 lg:py-8">
      <header className="border-b pb-5">
        <p className="platform-kicker">Monitored actions</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight">Atomic Tools</h1>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
          Run one bounded capability inside a durable, matter-scoped monitor. The browser never calls an operational tool directly.
        </p>
      </header>
      <AtomicTools />
    </div>
  );
}
