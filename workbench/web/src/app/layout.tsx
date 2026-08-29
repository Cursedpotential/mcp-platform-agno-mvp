// Byline: Claude Code · Sonnet (agent) · 2026-07-22 (C3: OpenFlagsCountProvider wired in)
// Byline: Codex · GPT-5 · 2026-08-28 (unified operator shell and focused-release boundary)
import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { Geist_Mono } from "next/font/google";
import "./globals.css";

import { ThemeProvider } from "@/components/layout/theme-provider";
import { SidebarProvider } from "@/components/ui/sidebar";
import { TooltipProvider } from "@/components/ui/tooltip";
import { AppSidebar } from "@/components/layout/app-sidebar";
import { Header } from "@/components/layout/header";
import { Toaster } from "@/components/ui/sonner";
import { RefreshProvider } from "@/lib/refresh-context";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  display: "swap",
  axes: ["opsz"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "The Platform — Evidence & Legal Operations",
  description: "Matter-scoped evidence intake, review, timeline, and legal operations",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body
        className={`${inter.variable} ${geistMono.variable} antialiased`}
      >
        <ThemeProvider>
          <RefreshProvider>
            <SidebarProvider>
              <TooltipProvider>
                <AppSidebar />
                <div className="flex h-svh min-h-0 flex-1 flex-col bg-background">
                  <Header />
                  <main className="platform-workspace relative flex-1 overflow-auto">{children}</main>
                  <footer className="hidden h-9 shrink-0 items-center justify-between border-t border-[#3c4952] bg-[#172129] px-5 text-[10px] text-[#aeb7bc] md:flex">
                    <span>PostgreSQL remains canonical authority</span>
                    <span>Surface actions require governed receipts</span>
                  </footer>
                </div>
                <Toaster />
              </TooltipProvider>
            </SidebarProvider>
          </RefreshProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
