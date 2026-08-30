// Byline: Codex · GPT-5.6-Sol · 2026-08-30
import type { Meta, StoryObj } from "@storybook/react-vite";
import { SurfaceManifest } from "@/platform-ui/surface-manifest";
import { WORKBENCH_SURFACES } from "@/platform-ui/surfaces";

const meta = {
  title: "Surfaces/Primary/Evidence Operations Desk",
  component: SurfaceManifest,
  parameters: {
    docs: {
      description: {
        component: "The daily, matter-scoped surface. Glide sorting work belongs here when integrated.",
      },
    },
  },
  args: {
    surface: WORKBENCH_SURFACES.primary,
  },
} satisfies Meta<typeof SurfaceManifest>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Boundary: Story = {};
