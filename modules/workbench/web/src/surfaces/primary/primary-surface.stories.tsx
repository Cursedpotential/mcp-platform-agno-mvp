// Byline: Codex · GPT-5.6-Sol · 2026-08-30
import type { Meta, StoryObj } from "@storybook/react-vite";
import {
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
  RouterProvider,
} from "@tanstack/react-router";

import { AppShell } from "@/app-shell";
import { SurfaceManifest } from "@/platform-ui/surface-manifest";
import { WORKBENCH_SURFACES } from "@/platform-ui/surfaces";
import { EvidenceOperationsDesk } from "@/surfaces/primary/evidence-operations-desk";

const MATTER_ID = "11111111-1111-4111-8111-111111111111";
const COURT_CASE_ID = "22222222-2222-4222-8222-222222222222";

const matter = {
  id: MATTER_ID,
  title: "Salem family matter",
  description: "Canonical single-case operator scope",
  status: "active",
  partition_keys: ["primary"],
  created_at: "2026-08-30T08:00:00Z",
  updated_at: "2026-08-30T08:00:00Z",
  court_cases: [
    {
      id: COURT_CASE_ID,
      matter_id: MATTER_ID,
      caption: "Primary family-court proceeding",
      court_name: "Michigan Circuit Court",
      case_type: "custody",
      status: "active",
      is_primary: true,
      created_at: "2026-08-30T08:00:00Z",
      updated_at: "2026-08-30T08:00:00Z",
    },
  ],
};

const storyResponses: Record<string, unknown> = {
  "/health": { status: "ok" },
  "/api/files": [{ id: "staged-a" }, { id: "staged-b" }, { id: "staged-c" }],
  "/api/flags?status=open": [{ id: "flag-a" }, { id: "flag-b" }],
  "/api/runs?limit=6": [
    { run_id: "run-20260830-014", source_name: "messages-export.json", workflow: "message-import", status: "running" },
    { run_id: "run-20260830-013", source_name: "hearing-notes.docx", workflow: "document-intake", status: "completed" },
    { run_id: "run-20260830-012", source_name: "photos-index.json", workflow: "media-index", status: "paused" },
  ],
  "/api/matters?limit=50&offset=0": { data: [matter], total: 1, limit: 50, offset: 0 },
  [`/api/matters/${MATTER_ID}`]: matter,
};

function installStoryApi() {
  const previousFetch = globalThis.fetch;
  globalThis.fetch = async (input) => {
    const rawUrl = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
    const url = new URL(rawUrl, globalThis.location?.origin || "http://storybook.local");
    const key = `${url.pathname}${url.search}`;
    if (!(key in storyResponses)) {
      return new Response(JSON.stringify({ detail: `Unmocked Storybook request: ${key}` }), {
        status: 404,
        headers: { "content-type": "application/json" },
      });
    }
    return new Response(JSON.stringify(storyResponses[key]), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  };
  return () => {
    globalThis.fetch = previousFetch;
  };
}

const storyRootRoute = createRootRoute({ component: AppShell });
const storyDeskRoute = createRoute({
  getParentRoute: () => storyRootRoute,
  path: "/",
  component: EvidenceOperationsDesk,
});
const storyRouter = createRouter({
  routeTree: storyRootRoute.addChildren([storyDeskRoute]),
  history: createMemoryHistory({ initialEntries: ["/"] }),
});

const meta = {
  title: "Surfaces/Primary/Evidence Operations Desk",
  component: EvidenceOperationsDesk,
  beforeEach: installStoryApi,
  parameters: {
    docs: {
      description: {
        component: "The real browser-first daily desk, shown with bounded Storybook API fixtures.",
      },
    },
  },
} satisfies Meta<typeof EvidenceOperationsDesk>;

export default meta;
type Story = StoryObj<typeof meta>;

export const OperationalDesk: Story = {
  render: () => <RouterProvider router={storyRouter} />,
};

export const Boundary: Story = {
  render: () => <SurfaceManifest surface={WORKBENCH_SURFACES.primary} />,
};
