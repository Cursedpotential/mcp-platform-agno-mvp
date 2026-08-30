// Byline: Codex · GPT-5.6-Sol · 2026-08-30
import { Inbox } from "lucide-react";
import type { WorkbenchNavigationItem } from "@/platform-ui/navigation";

export const primaryNavigationItems = [
  {
    title: "Intake",
    pageTitle: "Intake new evidence",
    href: "/intake",
    icon: Inbox,
    surface: "primary",
  },
] as const satisfies readonly WorkbenchNavigationItem[];
