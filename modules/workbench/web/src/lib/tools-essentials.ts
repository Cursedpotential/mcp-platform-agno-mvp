// Byline: Claude Code · Sonnet (agent) · 2026-07-21
/**
 * Config-driven "Essentials" curation for the Tool Explorer (C2.7 —
 * requirements addendum 8 / owner directive #2). Matches by (server key,
 * tool name); everything that doesn't match stays in its normal per-server
 * group.
 *
 * ContextForge authors the `platform-tools` registry and Portkey publishes
 * that exact surface downstream. A regex keeps curation independent of any
 * federation prefix while AgentOS operations are intentionally absent.
 */

/** Confirmed-live today (2026-07-21): "sbv" (all 14 platform_tools CF
 * entries carry it) and "graphiti-search" (graphiti-search-memory-facts,
 * graphiti-search-nodes). "knowledge"/"custody"/"evidence" match nothing
 * yet — kept forward-looking, see module doc comment above. */
export const CONTEXTFORGE_ESSENTIALS_RE = /sbv|graphiti[-_]?search|knowledge|custody|evidence/i;

/** True if (serverKey, toolName) should render in the pinned "Essentials"
 * shelf. Servers other than the two curated keys never contribute
 * essentials — they only ever appear in their own per-server group. */
export function isEssential(serverKey: string, toolName: string): boolean {
  if (serverKey === "platform-tools") return CONTEXTFORGE_ESSENTIALS_RE.test(toolName);
  return false;
}
