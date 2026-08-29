// Byline: Codex · GPT-5 · 2026-08-29 (production intake anatomy contract)
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const intake = readFileSync(
  new URL("../src/components/intake/unified-intake.tsx", import.meta.url),
  "utf8",
);

function between(source, startMarker, endMarker) {
  const start = source.indexOf(startMarker);
  const end = source.indexOf(endMarker, start + startMarker.length);
  assert.notEqual(start, -1, `missing start marker: ${startMarker}`);
  assert.notEqual(end, -1, `missing end marker: ${endMarker}`);
  assert.ok(end > start, `expected ${endMarker} after ${startMarker}`);
  return source.slice(start, end);
}

test("source inspection exposes the Source preview, Metadata, and Parser tabs", () => {
  assert.match(intake, /type PreviewTab = "source" \| "metadata" \| "parser";/);
  assert.match(intake, /\(\["source", "metadata", "parser"\] as const\)\.map/);
  assert.match(intake, /tab === "source" \? "Source preview" : tab/);
  assert.match(intake, /aria-label="Source preview"/);
  assert.match(intake, /aria-label="Source metadata"/);
  assert.match(intake, /aria-label="Parser selection"/);
});

test("local intake selects the five supported document extensions and declares them truthfully", () => {
  assert.match(intake, /const LOCAL_FILE_ACCEPT = "\.md,\.json,\.docx,\.html,\.htm";/);
  assert.match(intake, /<input accept=\{LOCAL_FILE_ACCEPT\} className="sr-only" type="file"/);
  assert.match(intake, /md: "markdown"/);
  assert.match(intake, /json: "message_export_json"/);
  assert.match(intake, /docx: "docx"/);
  assert.match(intake, /html: "html"/);
  assert.match(intake, /htm: "html"/);
  assert.match(intake, /\/\\\.\(md\|json\|html\?\|txt\|csv\|xml\)\$\/i/);
});

test("remote sources make no content or SHA-256 claim before acquisition seals them", () => {
  assert.match(
    intake,
    /Remote content is fetched and sealed by the acquisition worker after intake starts\. No content or SHA-256 is claimed before that seal completes\./,
  );
  assert.match(
    intake,
    /remote \? "Pending acquisition and seal" : upload\?\.sha256 \|\| digest \|\| "Computing browser preview"/,
  );
  assert.match(
    intake,
    /remote \? "Computed after acquisition seals the object" : upload\?\.sha256 \|\| digest \|\| "Choose a source"/,
  );
  assert.doesNotMatch(intake, /remote\.(sha256|content|digest)/);
});

test("parser details are rendered only from backend workflow preview state", () => {
  const parserPanel = between(
    intake,
    '{previewTab === "parser"',
    '<div className="flex flex-col gap-3 border-t',
  );

  assert.match(parserPanel, /\{preview \? \(/);
  assert.match(parserPanel, /preview\.phase/);
  assert.match(parserPanel, /preview\.select_ref/);
  assert.match(parserPanel, /preview\.reason/);
  assert.match(parserPanel, /Temporal read-back/);
  assert.match(
    parserPanel,
    /this screen will show only the selection returned by that workflow/,
  );
  assert.doesNotMatch(parserPanel, /<select\b|<option\b|setParser|parserOptions/);
});

test("execution receipt uses server-returned workflow identity and preserves the context boundary", () => {
  const receipt = between(
    intake,
    'aria-label="Intake execution receipt"',
    "</main>",
  );

  assert.match(receipt, /Server-returned workflow identity and latest Temporal phase\./);
  assert.match(receipt, /\{run\.workflow_id\}/);
  assert.match(receipt, /\{run\.run_id\}/);
  assert.match(receipt, /Authority boundary/);
  assert.match(receipt, /Context only; not evidence/);
});

test("intake exposes no model or provider selector and no Timeline or Legal destination", () => {
  assert.doesNotMatch(intake, /<select\b|role="combobox"/);
  assert.doesNotMatch(intake, /model(_id|Id|Selector)?\b|setModel|Model selector/i);
  assert.doesNotMatch(
    intake,
    /provider(_id|Id|Selector)\b|setProvider|Provider selector|<label[^>]*>[^<]*Provider/i,
  );
  assert.doesNotMatch(intake, /\bTimeline\b|\bLegal\b/);
});
