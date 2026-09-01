// Byline: Codex · GPT-5.6-Sol · 2026-08-30
import { FileSearch, Inbox, LayoutDashboard } from "lucide-react";
import type { WorkbenchNavigationItem } from "@/platform-ui/navigation";

export const primaryNavigationItems = [
  {
    title: "Desk",
    pageTitle: "Evidence Operations Desk",
    href: "/",
    icon: LayoutDashboard,
    surface: "primary",
  },
  {
    title: "Intake",
    pageTitle: "Intake new evidence",
    href: "/intake",
    icon: Inbox,
    surface: "primary",
  },
  {
    title: "Preview",
    pageTitle: "Inspect pipeline preview",
    href: "/evidence/preview",
    icon: FileSearch,
    surface: "primary",
  },
] as const satisfies readonly WorkbenchNavigationItem[];
