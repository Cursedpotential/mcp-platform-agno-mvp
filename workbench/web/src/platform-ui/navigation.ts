// Byline: Codex · GPT-5.6-Sol · 2026-08-30
import type { LucideIcon } from "lucide-react";
import type { WorkbenchSurfaceId } from "./surfaces";
import { advancedNavigationItems } from "@/surfaces/advanced/navigation";
import { primaryNavigationItems } from "@/surfaces/primary/navigation";

export interface WorkbenchNavigationItem {
  title: string;
  pageTitle?: string;
  href: `/${string}`;
  icon: LucideIcon;
  surface: WorkbenchSurfaceId;
}

export const workbenchNavigation: readonly WorkbenchNavigationItem[] = [
  ...primaryNavigationItems,
  ...advancedNavigationItems,
];

export function navigationTitle(pathname: string): string | undefined {
  const item = workbenchNavigation.find(
    (item) => pathname === item.href || pathname.startsWith(`${item.href}/`),
  );
  return item?.pageTitle ?? item?.title;
}
