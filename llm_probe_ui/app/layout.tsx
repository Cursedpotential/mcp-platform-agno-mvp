import type { Metadata } from "next";
import { IBM_Plex_Sans, IBM_Plex_Mono } from "next/font/google";
import Link from "next/link";
import "./globals.css";
import { AppProviders } from "./providers";

const plexSans = IBM_Plex_Sans({
  variable: "--font-plex-sans",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

const plexMono = IBM_Plex_Mono({
  variable: "--font-plex-mono",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
});

export const metadata: Metadata = {
  title: "llm-probe",
  description: "Live testbed for every LLM provider on the platform.",
};

const NAV = [
  { href: "/playground", label: "Playground" },
  { href: "/board", label: "Board" },
  { href: "/settings", label: "Settings" },
];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${plexSans.variable} ${plexMono.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col bg-bg text-text">
        <AppProviders>
          <header className="border-b border-border sticky top-0 z-20 bg-bg/90 backdrop-blur-sm">
            <nav className="max-w-6xl mx-auto px-6 h-14 flex items-center gap-1">
              <span className="font-semibold tracking-tight mr-5 text-[15px]">llm-probe</span>
              {NAV.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className="text-sm text-text-dim hover:text-text px-3 py-1.5 rounded-lg hover:bg-surface-2 transition-colors"
                >
                  {item.label}
                </Link>
              ))}
            </nav>
          </header>
          <main className="flex-1">{children}</main>
        </AppProviders>
      </body>
    </html>
  );
}
