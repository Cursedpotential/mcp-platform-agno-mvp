// Byline: Codex · GPT-5.6-Sol · 2026-08-30
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider } from "@tanstack/react-router";

import "@/app/globals.css";
import { router } from "@/router";

const rootElement = document.getElementById("root");
if (!rootElement) throw new Error("Workbench root element is missing");

createRoot(rootElement).render(
  <StrictMode>
    <RouterProvider router={router} />
  </StrictMode>,
);
