// Byline: Codex · GPT-5.6-Sol · 2026-08-30
import type { StorybookConfig } from "@storybook/react-vite";
import { fileURLToPath } from "node:url";

const config: StorybookConfig = {
  stories: [
    "../src/platform-ui/**/*.stories.@(ts|tsx)",
    "../src/surfaces/**/*.stories.@(ts|tsx)",
  ],
  addons: ["@storybook/addon-docs", "@storybook/addon-a11y"],
  framework: {
    name: "@storybook/react-vite",
    options: {},
  },
  viteFinal: async (viteConfig) => ({
    ...viteConfig,
    resolve: {
      ...viteConfig.resolve,
      alias: {
        ...viteConfig.resolve?.alias,
        "@": fileURLToPath(new URL("../src", import.meta.url)),
      },
    },
  }),
};

export default config;
