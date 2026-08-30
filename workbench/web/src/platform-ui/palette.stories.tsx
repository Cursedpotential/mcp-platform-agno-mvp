// Byline: Codex · GPT-5.6-Sol · 2026-08-30
import type { Meta, StoryObj } from "@storybook/react-vite";

const paletteGroups = [
  {
    label: "Workspace",
    colors: [
      ["Paper", "#f5f3ee"],
      ["Surface", "#fffefb"],
      ["Ink", "#1d2228"],
      ["Muted", "#687078"],
      ["Soft fill", "#ebe8e0"],
      ["Border", "#d5d1c9"],
    ],
  },
  {
    label: "Graphite shell",
    colors: [
      ["Navigation", "#151e25"],
      ["Sidebar", "#202b33"],
      ["Active", "#314050"],
      ["Shell border", "#3d4952"],
      ["Shell text", "#d9dfe2"],
      ["Bright text", "#f7f8f7"],
    ],
  },
  {
    label: "Interaction and status",
    colors: [
      ["Indigo", "#4051b9"],
      ["Indigo dark", "#2f3d9c"],
      ["Indigo soft", "#e9ecfb"],
      ["Success", "#2f9d67"],
      ["Warning", "#c58214"],
      ["Destructive", "#b5433b"],
    ],
  },
] as const;

function PlatformPalette() {
  return (
    <main className="platform-workspace min-h-screen p-8 sm:p-12">
      <div className="mx-auto max-w-5xl">
        <p className="platform-kicker mb-2">Shared visual contract</p>
        <h1 className="text-2xl font-semibold tracking-tight">Platform palette</h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
          Graphite shell, warm-paper workspace, and one restrained indigo interaction accent.
          Status colors carry meaning and are not decorative accents.
        </p>

        <div className="mt-8 grid gap-6 lg:grid-cols-3">
          {paletteGroups.map((group) => (
            <section key={group.label} className="platform-panel p-5" aria-labelledby={`${group.label.replaceAll(" ", "-")}-palette`}>
              <h2 id={`${group.label.replaceAll(" ", "-")}-palette`} className="platform-rule-title mb-4">
                {group.label}
              </h2>
              <ul className="space-y-3">
                {group.colors.map(([name, value]) => (
                  <li key={name} className="grid grid-cols-[2.5rem_1fr_auto] items-center gap-3 text-xs">
                    <span className="h-8 w-10 border border-border" style={{ backgroundColor: value }} aria-hidden="true" />
                    <span className="font-medium">{name}</span>
                    <code className="text-muted-foreground">{value.toUpperCase()}</code>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      </div>
    </main>
  );
}

const meta = {
  title: "Platform UI/Palette",
  component: PlatformPalette,
  parameters: {
    docs: {
      description: {
        component: "The approved color contract shared by primary and advanced surfaces.",
      },
    },
  },
} satisfies Meta<typeof PlatformPalette>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Approved: Story = {};
