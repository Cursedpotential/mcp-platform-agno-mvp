// Byline: Claude Code · Sonnet (agent) · 2026-07-20
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { PlayCircle, Wrench, Inbox, Brain } from "lucide-react";
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarFooter,
} from "@/components/ui/sidebar";

// C1 Operator Console nav: Runs (default landing) -> Tools -> Intake.
// "Files"/"Upload" retired — see _stale/upload-page-pre-c1/ for the old route.
const navItems = [
  { title: "Runs", href: "/runs", icon: PlayCircle },
  { title: "Tools", href: "/tools", icon: Wrench },
  { title: "Intake", href: "/intake", icon: Inbox },
];

export function AppSidebar() {
  const pathname = usePathname();

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
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
      <SidebarFooter className="border-t px-4 py-3">
        <span className="text-xs text-muted-foreground">
          C1 Operator Console — drive the pipeline
        </span>
      </SidebarFooter>
    </Sidebar>
  );
}
