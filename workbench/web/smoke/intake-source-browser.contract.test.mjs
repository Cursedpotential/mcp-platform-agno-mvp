// Byline: Codex · GPT-5 · 2026-08-29.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const intake = readFileSync(new URL("../src/components/intake/unified-intake.tsx", import.meta.url), "utf8");
const client = readFileSync(new URL("../src/lib/api-client.ts", import.meta.url), "utf8");
const types = readFileSync(new URL("../src/lib/shared/types.ts", import.meta.url), "utf8");

test("Case Bible Sorted is the default browser and local upload is secondary", () => {
  assert.match(intake, /Default ingestion point/);
  assert.match(intake, /Case Bible Sorted/);
  assert.match(intake, /Or add a source from this device/);
  assert.ok(intake.indexOf("Case Bible Sorted") < intake.indexOf("Choose local file"));
});

test("browser API never accepts provider or bucket input", () => {
  assert.match(client, /\/api\/uiw\/sources/);
  assert.doesNotMatch(client, /listUIWSources[\s\S]{0,500}(provider|bucket)\??:/);
  assert.match(types, /source: "casebible-sorted"/);
});

test("remote listings stay factual while inspection computes a separate preview checksum", () => {
  const remoteType = types.slice(types.indexOf("interface UIWSourceObject"), types.indexOf("interface UIWSourcePrefix"));
  assert.doesNotMatch(remoteType, /sha256/i);
  assert.match(client, /inspectUIWSource/);
  assert.match(client, /\/api\/uiw\/source-inspection/);
  assert.match(types, /digest_status: "preview_only"/);
  assert.match(intake, /Acquisition recomputes and receipts the custody checksum before promotion/);
});
