// Byline: Codex · GPT-5.6-Sol · 2026-08-30
import type { Preview } from "@storybook/react-vite";
import type { Decorator } from "@storybook/react";
import "../src/app/globals.css";

const withPlatformCanvas: Decorator = (Story, context) => {
  const dark = context.globals.theme === "dark";

  return (
    <div
      className={dark ? "dark min-h-screen bg-background text-foreground" : "min-h-screen bg-background text-foreground"}
      style={
        {
          "--font-inter": "Inter, ui-sans-serif, system-ui, sans-serif",
          "--font-geist-mono": "Geist Mono, ui-monospace, monospace",
        } as React.CSSProperties
      }
    >
      <Story />
    </div>
  );
};

const preview: Preview = {
  decorators: [withPlatformCanvas],
  globalTypes: {
    theme: {
      description: "Platform color mode",
      defaultValue: "light",
      toolbar: {
        icon: "paintbrush",
        items: [
          { value: "light", title: "Warm paper" },
          { value: "dark", title: "Graphite dark" },
        ],
      },
    },
  },
  parameters: {
    a11y: {
      test: "error",
    },
    backgrounds: {
      disable: true,
    },
    controls: {
      matchers: {
        color: /(background|color)$/i,
        date: /Date$/i,
      },
    },
    layout: "fullscreen",
  },
};

export default preview;
