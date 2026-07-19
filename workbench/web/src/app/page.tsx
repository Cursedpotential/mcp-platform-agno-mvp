// Byline: Claude Code · Sonnet (agent) · 2026-07-19
"use client";

/**
 * Home route. The workbench has exactly two surfaces (Upload, Files) and no
 * dashboard — this is a thin client-side redirect to Files rather than a
 * duplicated landing page. Client-side redirect (not a Next.js `redirect()`
 * server helper) because this app is a static export with no server runtime.
 */
import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function HomePage() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/files");
  }, [router]);

  return null;
}
