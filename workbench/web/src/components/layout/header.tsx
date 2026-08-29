// Byline: Claude Code · Sonnet (agent) · 2026-07-22 (C3: Records/Evidence Queue/Schemas page titles)
// Byline: Codex · GPT-5 · 2026-08-16 (Knowledge + Surreal projection page titles)
// Byline: Codex · GPT-5 · 2026-08-28 (unified product header)
"use client";

import { usePathname } from "next/navigation";
import { useTheme } from "next-themes";
import { Moon, Sun } from "lucide-react";
import { Button } from "@/components/ui/button";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { Separator } from "@/components/ui/separator";
import { HealthChips } from "@/components/layout/health-chips";

const pageTitles: Record<string, string> = {
  "/intake": "Intake new evidence",
};

export function Header() {
  const pathname = usePathname();
  const { theme, setTheme } = useTheme();
  const pageTitle = pageTitles[pathname] || "Evidence & legal operations";

  return (
    <header className="flex h-[74px] shrink-0 items-stretch bg-nav text-nav-foreground">
      <div className="flex w-[232px] items-center gap-3 border-r border-white/15 px-4">
        <SidebarTrigger className="text-nav-foreground/70 hover:bg-white/10 hover:text-nav-foreground" />
        <div className="grid h-9 w-9 place-items-center border border-[#6d7982] bg-[#1f2a33] font-mono text-lg font-semibold">P</div>
        <div className="min-w-0">
          <strong className="block truncate text-sm">The Platform</strong>
          <span className="block truncate text-[10px] text-[#aeb6bc]">Evidence & legal operations</span>
        </div>
      </div>
      <div className="flex min-w-0 flex-1 flex-col justify-center px-5">
        <strong className="truncate text-sm">{pageTitle}</strong>
        <span className="truncate text-[11px] text-[#b9c0c5]">Matter scope is selected and verified inside the intake workspace</span>
      </div>
      <div className="ml-auto flex items-center gap-3">
        <HealthChips />
        <Separator orientation="vertical" className="h-5 bg-nav-foreground/20" />
        <Button
          variant="ghost"
          size="icon"
          className="mr-5 h-9 w-9 rounded-full border border-white/20 text-nav-foreground/70 hover:bg-white/10 hover:text-nav-foreground"
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
        >
          <Sun className="h-4 w-4 rotate-0 scale-100 transition-all dark:-rotate-90 dark:scale-0" />
          <Moon className="absolute h-4 w-4 rotate-90 scale-0 transition-all dark:rotate-0 dark:scale-100" />
        </Button>
      </div>
    </header>
  );
}
