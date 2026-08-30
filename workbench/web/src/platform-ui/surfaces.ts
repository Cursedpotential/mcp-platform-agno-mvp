// Byline: Codex · GPT-5.6-Sol · 2026-08-30

export type WorkbenchSurfaceId = "primary" | "advanced";
export type WorkbenchSurfaceState = "active" | "gated";

export interface WorkbenchSurfaceDefinition {
  id: WorkbenchSurfaceId;
  label: string;
  kicker: string;
  description: string;
  state: WorkbenchSurfaceState;
  capabilities: readonly string[];
  boundary: string;
}

export const WORKBENCH_SURFACES = {
  primary: {
    id: "primary",
    label: "Evidence Operations Desk",
    kicker: "Daily work",
    description: "The focused surface for intake, sorting, review, and ordinary case chronology.",
    state: "active",
    capabilities: [
      "Glide-backed document and evidence review",
      "Intake, queues, receipts, and provenance",
      "Lightweight purpose-built timeline views",
      "Matter-scoped search and review",
    ],
    boundary: "Every action remains matter-scoped and requires a governed backend receipt.",
  },
  advanced: {
    id: "advanced",
    label: "Modular Service Cockpit",
    kicker: "Advanced work",
    description: "The power-user surface for deep forensic analysis and governed service tools.",
    state: "gated",
    capabilities: [
      "Timesketch forensic chronology",
      "Temporal and n8n workflow inspection",
      "Graph, map, schema, and projection tools",
      "Deep diagnostics and governed curation",
    ],
    boundary: "Advanced destinations remain hidden until deployment, authority, and round-trip proof pass.",
  },
} as const satisfies Record<WorkbenchSurfaceId, WorkbenchSurfaceDefinition>;
