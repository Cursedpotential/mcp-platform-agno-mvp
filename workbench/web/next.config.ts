// Byline: Claude Code · Sonnet (agent) · 2026-07-19
/**
 * Static export — this app has no server component. FastAPI serves the
 * built `out/` directory same-origin and answers `/api/**` + `/health`.
 * No server actions, no route handlers, no `next/headers` anywhere in this
 * tree (verified — see workbench/web/README.md sanity-pass notes).
 */
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "export",
  images: {
    unoptimized: true,
  },
};

export default nextConfig;
