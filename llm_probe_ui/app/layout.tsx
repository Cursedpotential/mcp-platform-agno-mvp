import type { Metadata } from "next";
import { IBM_Plex_Sans, IBM_Plex_Mono } from "next/font/google";
import Link from "next/link";
import "./globals.css";

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

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${plexSans.variable} ${plexMono.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col bg-bg text-text">
        <header className="border-b border-border sticky top-0 z-10 bg-bg/95 backdrop-blur">
          <nav className="max-w-6xl mx-auto px-6 h-14 flex items-center gap-6">
            <span className="font-semibold tracking-tight">llm-probe</span>
            <Link href="/playground" className="text-sm text-text-dim hover:text-accent transition-colors">
              Playground
            </Link>
            <Link href="/board" className="text-sm text-text-dim hover:text-accent transition-colors">
              Board
            </Link>
          </nav>
        </header>
        <main className="flex-1">{children}</main>
      </body>
    </html>
  );
}
