// Byline: Codex · GPT-5 · 2026-08-15 (static-export Matter workspace entry)
import { Suspense } from "react";

import { MatterWorkspace } from "@/components/matters/matter-workspace";

export default function MatterPage() {
  return (
    <Suspense fallback={<p className="py-10 text-center text-sm text-muted-foreground">Loading Matter workspace…</p>}>
      <MatterWorkspace />
    </Suspense>
  );
}
