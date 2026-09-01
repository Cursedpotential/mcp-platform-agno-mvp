// Byline: Claude Code · Sonnet (agent) · 2026-07-21
"use client";

/**
 * Client-only localStorage persistence for the Tool Explorer's "Recently
 * used" row (C2.7 — owner directive #2). Last 8 successfully-invoked
 * tools, most-recent-first, rendered above Essentials when non-empty.
 */

const STORAGE_KEY = "workbench:tools:recent";
const MAX_RECENT = 8;

export interface RecentToolEntry {
  serverKey: string;
  toolName: string;
  ts: number;
}

function safeParse(): RecentToolEntry[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as RecentToolEntry[]) : [];
  } catch {
    return [];
  }
}

export function getRecentTools(): RecentToolEntry[] {
  return safeParse();
}

/** Record a successful invocation, moving it to the front if already
 * present. Best-effort — a full/unavailable localStorage (private
 * browsing) silently no-ops rather than breaking the invoke flow. */
export function recordToolUsed(serverKey: string, toolName: string): void {
  if (typeof window === "undefined") return;
  const existing = safeParse().filter(
    (e) => !(e.serverKey === serverKey && e.toolName === toolName),
  );
  const next = [{ serverKey, toolName, ts: Date.now() }, ...existing].slice(0, MAX_RECENT);
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  } catch {
    // best effort only
  }
}
