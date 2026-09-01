// Byline: Codex · GPT-5.6-Sol · 2026-08-30
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const intake = readFileSync(new URL("../src/components/intake/unified-intake.tsx", import.meta.url), "utf8");
const atomic = readFileSync(new URL("../src/components/tools/atomic-tools.tsx", import.meta.url), "utf8");
const client = readFileSync(new URL("../src/lib/api-client.ts", import.meta.url), "utf8");

test("Atomic Tools is a tab inside the unified intake window", () => {
  assert.match(intake, /type OperatorTab = "intake" \| "atomic_tools"/);
  assert.match(intake, />Atomic Tools<\/button>/);
  assert.match(intake, /<AtomicTools embedded/);
});

test("atomic execution has no browser direct-call fallback", () => {
  assert.doesNotMatch(client, /\/api\/tools\/call/);
  assert.match(client, /\/api\/monitored-actions\/capabilities/);
  assert.match(client, /startAtomicToolAction/);
  assert.match(atomic, /Execution unavailable/);
  assert.match(atomic, /No placeholder run is created in the browser/);
});

test("the atomic surface carries intent and governed execution scope", () => {
  for (const phrase of [
    "Operator intent",
    "Knowledge horizon",
    "Authority scope",
    "Fixed case scope",
    "Start monitored run",
    "Workflow ID",
    "Run ID",
    "Retries",
    "Current waits",
    "Receipts",
    "Output",
    "Technical details",
  ]) assert.match(`${atomic}\n${readFileSync(new URL("../src/components/tools/tool-form.tsx", import.meta.url), "utf8")}`, new RegExp(phrase));
  assert.doesNotMatch(atomic, /Model selector|model_id|provider selector/i);
});
