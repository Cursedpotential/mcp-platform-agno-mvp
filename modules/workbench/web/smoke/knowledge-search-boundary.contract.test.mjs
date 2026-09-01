// Byline: Codex · GPT-5.6-Sol · 2026-08-29.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const browser = readFileSync(
  new URL("../src/components/knowledge/knowledge-browser.tsx", import.meta.url),
  "utf8",
);

test("semantic search is fixed to the native evidence lane", () => {
  assert.match(browser, /const EVIDENCE_SEARCH_LANE = "evidence" as const/);
  assert.match(browser, /requestedScope = \{ partitionKey: activePartition\.trim\(\), lane: EVIDENCE_SEARCH_LANE \}/);
  assert.match(browser, /lane: requestedScope\.lane/);
  assert.match(browser, /<option value=\{EVIDENCE_SEARCH_LANE\}>evidence \(native\)<\/option>/);
  assert.doesNotMatch(browser, /All allowed lanes/);
});

test("canonical catalog browsing retains all supported lanes independently", () => {
  assert.match(browser, /const \[catalogLane, setCatalogLane\] = useState\(""\)/);
  assert.match(browser, /lane: catalogLane/);
  assert.match(browser, /id="sources-lane"[\s\S]{0,800}\{LANES\.map/);
});
