// Byline: Claude Code · Sonnet (agent) · 2026-07-22 (C3: Records/Evidence Queue/Schemas nav entries + open-flags badge)
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { PlayCircle, Wrench, Inbox, Brain, FileSearch, ListChecks, Database } from "lucide-react";
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuBadge,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarFooter,
} from "@/components/ui/sidebar";
import { useFailedRunsCount } from "@/lib/failed-runs-context";
import { useOpenFlagsCount } from "@/lib/open-flags-context";

// C1/C3 Operator Console nav: Runs (default landing) -> Records -> Tools ->
// Intake -> Evidence Queue -> Schemas. "Files"/"Upload" retired — see
// _stale/upload-page-pre-c1/ for the old route.
const navItems = [
  { title: "Runs", href: "/runs", icon: PlayCircle },
  { title: "Records", href: "/records", icon: FileSearch },
  { title: "Tools", href: "/tools", icon: Wrench },
  { title: "Intake", href: "/intake", icon: Inbox },
  { title: "Evidence Queue", href: "/evidence-queue", icon: ListChecks },
  { title: "Schemas", href: "/schemas", icon: Database },
];

export function AppSidebar() {
  const pathname = usePathname();
  // C2.6 requirement 3: red count badge of failed runs on the "Runs" nav
  // item, driven by the list poll in lib/failed-runs-context.tsx.
  const failedRunsCount = useFailedRunsCount();
  // C3: same pattern for open corroboration flags on "Evidence Queue".
  const openFlagsCount = useOpenFlagsCount();

  return (
    <Sidebar>
      <SidebarHeader className="border-b px-4 py-3">
        <Link href="/runs" className="flex items-center gap-2 font-semibold">
          <Brain className="h-5 w-5" />
          <span>Operator Console</span>
        </Link>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Navigation</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {navItems.map((item) => (
                <SidebarMenuItem key={item.href}>
                  <SidebarMenuButton asChild isActive={pathname === item.href}>
                    <Link href={item.href}>
                      <item.icon className="h-4 w-4" />
                      <span>{item.title}</span>
                    </Link>
                  </SidebarMenuButton>
                  {item.href === "/runs" && failedRunsCount > 0 && (
                    <SidebarMenuBadge className="bg-destructive text-destructive-foreground">
                      {failedRunsCount > 99 ? "99+" : failedRunsCount}
                    </SidebarMenuBadge>
                  )}
                  {item.href === "/evidence-queue" && openFlagsCount > 0 && (
                    <SidebarMenuBadge className="bg-amber-500 text-white">
                      {openFlagsCount > 99 ? "99+" : openFlagsCount}
                    </SidebarMenuBadge>
                  )}
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
      <SidebarFooter className="border-t px-4 py-3">
        <span className="text-xs text-muted-foreground">
          Operator Console — drive the pipeline
        </span>
      </SidebarFooter>
    </Sidebar>
  );
}
