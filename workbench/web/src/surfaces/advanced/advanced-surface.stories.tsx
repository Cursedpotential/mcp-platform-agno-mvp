// Byline: Codex · GPT-5.6-Sol · 2026-08-30
import type { Meta, StoryObj } from "@storybook/react-vite";
import { SurfaceManifest } from "@/platform-ui/surface-manifest";
import { WORKBENCH_SURFACES } from "@/platform-ui/surfaces";

const meta = {
  title: "Surfaces/Advanced/Modular Service Cockpit",
  component: SurfaceManifest,
  parameters: {
    docs: {
      description: {
        component: "The separately gated power-user surface. Timesketch remains native and standalone here.",
      },
    },
  },
  args: {
    surface: WORKBENCH_SURFACES.advanced,
  },
} satisfies Meta<typeof SurfaceManifest>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Boundary: Story = {};
