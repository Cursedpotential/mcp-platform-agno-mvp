// Byline: Claude Code · Sonnet (agent) · 2026-07-20
"use client";

/**
 * Home route. Runs is the default landing surface for the C1 Operator
 * Console (Runs / Tools / Intake) — this is a thin client-side redirect
 * rather than a duplicated landing page. Client-side redirect (not a
 * Next.js `redirect()` server helper) because this app is a static export
 * with no server runtime.
 */
import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function HomePage() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/runs");
  }, [router]);

  return null;
}
