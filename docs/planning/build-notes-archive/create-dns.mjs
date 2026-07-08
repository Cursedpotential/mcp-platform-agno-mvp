#!/usr/bin/env node
// create-dns.mjs — idempotent Cloudflare DNS reconciler for mitechconsult.com
// > _Byline: Claude Code · Opus 4.8 · 2026-06-14_
//
// SAFETY: DRY-RUN by default. Prints intended changes and exits without touching
//         Cloudflare unless `--apply` is passed. Public-twin (orange-cloud) records
//         are SKIPPED unless `--include-public` is also passed.
//
// Usage:
//   node create-dns.mjs                          # dry-run, private .int records only
//   node create-dns.mjs --apply                  # apply private .int records
//   node create-dns.mjs --include-public         # dry-run incl. public twins
//   node create-dns.mjs --apply --include-public # apply everything
//   node create-dns.mjs --env C:\path\cloudflare.env   # override token file
//
// Token: read from C:\Users\matts\.secrets\cloudflare.env (CLOUDFLARE_API_TOKEN=...)
// Required token scope: Zone.DNS:Edit on the mitechconsult.com zone.
//
// Cloudflare API (v4) endpoints used:
//   GET    /zones/:zone/dns_records?type=A&per_page=100   (list, paginated)
//   POST   /zones/:zone/dns_records                       (create)
//   PUT    /zones/:zone/dns_records/:id                   (update/replace)
// Docs: https://developers.cloudflare.com/api/resources/dns/subresources/records/

import { readFileSync } from 'node:fs';

// ---------------------------------------------------------------------------
// Locked configuration
// ---------------------------------------------------------------------------
const ZONE_ID = 'd543c96e4bb7fad63e5f1925dce79640';
const ZONE_NAME = 'mitechconsult.com';
const API_BASE = 'https://api.cloudflare.com/client/v4';
const DEFAULT_ENV = 'C:\\Users\\matts\\.secrets\\cloudflare.env';

// Box inventory
const BOX = {
  'ovh-1': { tailnet: '100.72.169.40', public: '40.160.5.19' }, // exec
  'ovh-3': { tailnet: '100.119.96.29', public: '147.135.79.183' }, // data
};

// Old IP that milvus/attu currently point at (OVH-2). Used only to FLAG repoints.
const OVH2_PUBLIC = '51.81.83.191';

// Service map. host = the leaf label under the zone.
//   private hosts:  <svc>.int.mitechconsult.com  -> box tailnet IP, proxied:false
//   public twins:   <svc>.mitechconsult.com      -> box public IP,  proxied:true
const SERVICES = [
  { svc: 'api', desc: 'agentos-api', box: 'ovh-1', publicTwin: true },
  { svc: 'chat', desc: 'agent-ui', box: 'ovh-1', publicTwin: true },
  { svc: 'mcp', desc: 'ContextForge', box: 'ovh-1', publicTwin: true },
  { svc: 'tools', desc: 'SBV', box: 'ovh-1', publicTwin: false },
  { svc: 'desktop', desc: 'Kasm', box: 'ovh-1', publicTwin: false },
  { svc: 'gw', desc: 'LiteLLM gateway', box: 'ovh-1', publicTwin: false },
  { svc: 'neo4j', desc: 'neo4j browser', box: 'ovh-3', publicTwin: false },
  // milvus/attu live on a non-.int public hostname today (OVH-2). Their PRIVATE
  // twins are new; the legacy bare records are flagged as repoints below.
  { svc: 'milvus', desc: 'Milvus', box: 'ovh-3', publicTwin: false, legacyBare: true },
  { svc: 'attu', desc: 'Attu', box: 'ovh-3', publicTwin: false, legacyBare: true },
];

// ---------------------------------------------------------------------------
// Build the desired record set
// ---------------------------------------------------------------------------
// Each desired record: { name (FQDN), type, content (IP), proxied, ttl, kind, note }
function buildDesired() {
  const recs = [];
  for (const s of SERVICES) {
    const box = BOX[s.box];
    // PRIVATE: <svc>.int.mitechconsult.com -> tailnet, DNS-only
    recs.push({
      name: `${s.svc}.int.${ZONE_NAME}`,
      type: 'A',
      content: box.tailnet,
      proxied: false,
      ttl: 1, // 1 = "automatic"
      kind: 'private',
      note: `${s.desc} on ${s.box} (tailnet)`,
    });
  }
  // PUBLIC TWINS: only api/chat/mcp -> public IP, orange-cloud (default-blocked)
  for (const s of SERVICES.filter((x) => x.publicTwin)) {
    const box = BOX[s.box];
    recs.push({
      name: `${s.svc}.${ZONE_NAME}`,
      type: 'A',
      content: box.public,
      proxied: true,
      ttl: 1,
      kind: 'public-twin',
      note: `${s.desc} on ${s.box} (PUBLIC, proxied; treat as default-blocked via CF)`,
    });
  }
  return recs;
}

// Legacy bare records that must be REPOINTED OVH-2 -> OVH-3 (NOT auto-applied;
// surfaced as explicit, separately-confirmed updates).
const REPOINTS = [
  { name: `milvus.${ZONE_NAME}`, from: OVH2_PUBLIC, to: BOX['ovh-3'].public, proxied: false },
  { name: `attu.${ZONE_NAME}`, from: OVH2_PUBLIC, to: BOX['ovh-3'].public, proxied: false },
];

// ---------------------------------------------------------------------------
// CLI args + token
// ---------------------------------------------------------------------------
const args = process.argv.slice(2);
const APPLY = args.includes('--apply');
const INCLUDE_PUBLIC = args.includes('--include-public');
const APPLY_REPOINTS = args.includes('--apply-repoints');
const envIdx = args.indexOf('--env');
const ENV_PATH = envIdx >= 0 && args[envIdx + 1] ? args[envIdx + 1] : DEFAULT_ENV;

function loadToken(path) {
  let raw;
  try {
    raw = readFileSync(path, 'utf8');
  } catch (e) {
    die(`Cannot read token file: ${path}\n${e.message}`);
  }
  const m = raw.match(/^\s*CLOUDFLARE_API_TOKEN\s*=\s*(.+?)\s*$/m);
  if (!m) die(`CLOUDFLARE_API_TOKEN not found in ${path}`);
  return m[1].trim();
}

function die(msg) {
  console.error(`\nERROR: ${msg}`);
  process.exit(1);
}

const TOKEN = loadToken(ENV_PATH);

async function cf(method, path, body) {
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: {
      Authorization: `Bearer ${TOKEN}`,
      'Content-Type': 'application/json',
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  const json = await res.json().catch(() => ({}));
  if (!res.ok || json.success === false) {
    const errs = (json.errors || []).map((e) => `${e.code}: ${e.message}`).join('; ');
    throw new Error(`CF ${method} ${path} -> ${res.status} ${errs || res.statusText}`);
  }
  return json;
}

// List ALL A records (paginated) into a map keyed by FQDN name.
async function listExisting() {
  const byName = new Map();
  let page = 1;
  for (;;) {
    const j = await cf('GET', `/zones/${ZONE_ID}/dns_records?type=A&per_page=100&page=${page}`);
    for (const r of j.result) byName.set(r.name.toLowerCase(), r);
    const ti = j.result_info?.total_pages ?? 1;
    if (page >= ti) break;
    page++;
  }
  return byName;
}

function needsUpdate(existing, desired) {
  return (
    existing.content !== desired.content ||
    Boolean(existing.proxied) !== Boolean(desired.proxied) ||
    existing.type !== desired.type
  );
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------
async function main() {
  const mode = APPLY ? 'APPLY' : 'DRY-RUN';
  console.log(`\n=== Cloudflare DNS reconcile — ${ZONE_NAME} ===`);
  console.log(`Mode: ${mode}${INCLUDE_PUBLIC ? ' +public-twins' : ' (private only)'}`);
  console.log(`Zone: ${ZONE_ID}`);
  console.log(`Token file: ${ENV_PATH} (value not printed)\n`);

  const existing = await listExisting();
  console.log(`Found ${existing.size} existing A record(s) in zone.\n`);

  let desired = buildDesired();
  if (!INCLUDE_PUBLIC) desired = desired.filter((r) => r.kind !== 'public-twin');

  const plan = { create: [], update: [], noop: [] };
  for (const d of desired) {
    const ex = existing.get(d.name.toLowerCase());
    if (!ex) plan.create.push({ d });
    else if (needsUpdate(ex, d)) plan.update.push({ d, ex });
    else plan.noop.push({ d, ex });
  }

  // Report
  const tag = (d) => `${d.name.padEnd(34)} A -> ${d.content.padEnd(16)} proxied:${d.proxied}  [${d.kind}]`;
  console.log('--- CREATE (' + plan.create.length + ') ---');
  for (const { d } of plan.create) console.log('  + ' + tag(d) + `  # ${d.note}`);
  console.log('\n--- UPDATE (' + plan.update.length + ') ---');
  for (const { d, ex } of plan.update)
    console.log(`  ~ ${tag(d)}\n      was: ${ex.content} proxied:${ex.proxied}`);
  console.log('\n--- NO-OP (' + plan.noop.length + ') already correct ---');
  for (const { d } of plan.noop) console.log('  = ' + d.name);

  // Repoint flags (milvus/attu OVH-2 -> OVH-3) — always surfaced, never auto-applied
  console.log('\n--- REPOINT FLAGS (milvus/attu: OVH-2 -> OVH-3) ---');
  console.log('  These touch EXISTING bare hostnames. Confirm before changing.');
  for (const rp of REPOINTS) {
    const ex = existing.get(rp.name.toLowerCase());
    if (!ex) {
      console.log(`  ! ${rp.name}: no existing record found (expected ${rp.from}) — verify manually.`);
    } else if (ex.content === rp.to) {
      console.log(`  = ${rp.name}: already -> ${rp.to} (OVH-3). No repoint needed.`);
    } else {
      console.log(
        `  ~ ${rp.name}: ${ex.content} -> ${rp.to}  (proxied:${ex.proxied}->${rp.proxied})` +
          `${APPLY_REPOINTS ? '' : '  [pass --apply-repoints to apply]'}`,
      );
    }
  }

  if (!APPLY) {
    console.log('\nDRY-RUN complete. No changes made. Re-run with --apply to execute.\n');
    return;
  }

  // Apply private (+public if requested)
  console.log('\n=== APPLYING ===');
  for (const { d } of plan.create) {
    await cf('POST', `/zones/${ZONE_ID}/dns_records`, {
      type: d.type, name: d.name, content: d.content, proxied: d.proxied, ttl: d.ttl,
    });
    console.log('  created ' + d.name);
  }
  for (const { d, ex } of plan.update) {
    await cf('PUT', `/zones/${ZONE_ID}/dns_records/${ex.id}`, {
      type: d.type, name: d.name, content: d.content, proxied: d.proxied, ttl: d.ttl,
    });
    console.log('  updated ' + d.name);
  }

  // Apply repoints only with explicit extra flag
  if (APPLY_REPOINTS) {
    console.log('\n=== APPLYING REPOINTS ===');
    for (const rp of REPOINTS) {
      const ex = existing.get(rp.name.toLowerCase());
      if (!ex || ex.content === rp.to) continue;
      await cf('PUT', `/zones/${ZONE_ID}/dns_records/${ex.id}`, {
        type: 'A', name: rp.name, content: rp.to, proxied: rp.proxied, ttl: 1,
      });
      console.log(`  repointed ${rp.name} -> ${rp.to}`);
    }
  } else {
    console.log('\n(Repoints NOT applied — pass --apply-repoints to include them.)');
  }

  console.log('\nDone.\n');
}

main().catch((e) => die(e.message));
