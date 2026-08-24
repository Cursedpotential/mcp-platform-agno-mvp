// Byline: Claude Code · Sonnet (agent) · 2026-07-22 (C3: OpenFlagsCountProvider wired in)
/**
 * Static export — this app has no server component. FastAPI serves the
 * built `out/` directory same-origin and answers `/api/**` + `/health`.
 * No server actions, no route handlers, no `next/headers` anywhere in this
 * app.
 */
import type { NextConfig } from "next";
const { withModuleFederation } = require("@module-federation/nextjs-mf");

const nextConfig: NextConfig = {
  output: "export",
  turbopack: {
    // Keep dependency tracing inside this app even when an unrelated parent
    // workspace also has a lockfile.
    root: process.cwd(),
  },
  images: {
    unoptimized: true,
  },
};

module.exports = withModuleFederation(nextConfig, {
  name: "agno",
  filename: "static/chunks/remoteEntry.js",
  exposes: {
    "./Workbench": "./src/app/page.tsx", // Main page component (redirects to /runs)
  },
  shared: {
    react: { singleton: true, requiredVersion: false },
    "react-dom": { singleton: true, requiredVersion: false },
  },
});