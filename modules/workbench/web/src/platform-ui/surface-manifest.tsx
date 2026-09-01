// Byline: Codex · GPT-5.6-Sol · 2026-08-30
import type { WorkbenchSurfaceDefinition } from "./surfaces";

export interface SurfaceManifestProps {
  surface: WorkbenchSurfaceDefinition;
}

export function SurfaceManifest({ surface }: SurfaceManifestProps) {
  return (
    <main className="platform-workspace min-h-screen p-8 sm:p-12">
      <section className="platform-panel mx-auto max-w-3xl p-6 sm:p-8" aria-labelledby={`${surface.id}-surface-title`}>
        <div className="flex flex-wrap items-start justify-between gap-4 border-b border-border pb-5">
          <div className="max-w-2xl">
            <p className="platform-kicker mb-2">{surface.kicker}</p>
            <h1 id={`${surface.id}-surface-title`} className="text-2xl font-semibold tracking-tight">
              {surface.label}
            </h1>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">{surface.description}</p>
          </div>
          <span
            className={
              surface.state === "active"
                ? "border border-[#2f9d67] bg-[#e2f3e9] px-2.5 py-1 text-xs font-semibold text-[#17794b] dark:bg-[#203d31] dark:text-[#72d9a1]"
                : "border border-[#c58214] bg-[#fff4dd] px-2.5 py-1 text-xs font-semibold text-[#684b18] dark:bg-[#43351f] dark:text-[#ffe0a6]"
            }
          >
            {surface.state === "active" ? "Active surface" : "Proof gated"}
          </span>
        </div>

        <div className="grid gap-8 pt-6 md:grid-cols-[1fr_0.9fr]">
          <div>
            <h2 className="platform-rule-title mb-3">Owned capabilities</h2>
            <ul className="divide-y divide-border border-y border-border">
              {surface.capabilities.map((capability) => (
                <li key={capability} className="py-3 text-sm">
                  {capability}
                </li>
              ))}
            </ul>
          </div>
          <aside className="border-l-2 border-primary bg-accent/45 p-4">
            <h2 className="platform-rule-title mb-2 text-accent-foreground">Authority boundary</h2>
            <p className="text-sm leading-6 text-muted-foreground">{surface.boundary}</p>
          </aside>
        </div>
      </section>
    </main>
  );
}
