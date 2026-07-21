// Byline: Claude Code · Sonnet (agent) · 2026-07-20
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
import { NewRunDialogProvider } from "@/lib/new-run-dialog-context";
import { FailedRunsCountProvider } from "@/lib/failed-runs-context";
import { NewRunDialog } from "@/components/runs/new-run-dialog";

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
  title: "Operator Console",
  description: "Drive the evidence spine: custody, parse, store, knowledge — and the tools behind it",
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
            <NewRunDialogProvider>
              <FailedRunsCountProvider>
                <SidebarProvider>
                  <TooltipProvider>
                    <AppSidebar />
                    <div className="flex flex-1 flex-col h-svh min-h-0">
                      <Header />
                      <main className="relative flex-1 overflow-auto p-6">{children}</main>
                    </div>
                    <Toaster />
                    <NewRunDialog />
                  </TooltipProvider>
                </SidebarProvider>
              </FailedRunsCountProvider>
            </NewRunDialogProvider>
          </RefreshProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
