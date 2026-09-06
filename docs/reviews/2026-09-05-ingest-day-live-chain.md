# Ingest day — the live chain from outbox to the HITL gate

> _Byline: Claude Code · Fable 5.1 · 2026-09-05._
> Consolidates one day's live-verified work across four prior reviews
> (`2026-09-04-outbox-part1-build.md`, `2026-09-05-tool-gateway-live-deploy.md`,
> `2026-09-05-live-deploy-run.md`, `2026-09-05-h04-bridge-and-weaviate-feed-rewire.md`)
> and twelve commits (`dd0e60d..HEAD`). All facts below are live-verified today unless
> marked otherwise.
> _Naming: written before the 2026-09-05 rename (D-137..D-141); see docs/NAMING.md for the old->new glossary._

## Outcome

End-to-end reachability through the tool gateway to the human-in-the-loop repair
decision gate is **PROVEN**: a real UIW rehearsal (`r2e-…`, then `r2f-…`) registered a
source, retained the original over `r2://`, ran `assess_source_repair` through
`svc:tool-gateway` to a real detector result (99 chunks, 0 repairs), and parked cleanly
at `awaiting_repair_decision`. Parse-to-raw is **NOT** yet proven: the first run past
that gate (`r2f-…`) reached `execute_parser` and failed on a NUL byte (`0x00`) inside the
synthetic fixture, which PostgreSQL TEXT columns cannot store — a byte-exactness
question the platform has not yet ruled on. Nothing described here is a new capability
in the product sense; it is the wiring between capabilities that shipped over the last
five commits, found broken by literally running the chain end to end rather than by
re-reading it.

## What's live now

| Component | State | Evidence |
|---|---|---|
| `sql/0071` outbox spine + `sql/0072` bridge | Applied live, one transaction, `09:54:35Z→09:54:40Z` | ledger 0→2 rows; `cdc_lag()` returns 36 rows (6 sinks × 6 outboxes) |
| `working.enqueue_evidence_vector_projection` | Rewired off dropped `normalized_record_chunk` onto `content_chunk_message` | `pg_get_functiondef` no longer names the dropped table |
| `platform-tools` | Redeployed with materialize mount (`:ro`) | deployment `l9y8ft7oaeu3zh4449uhg48t`; `/tools` → 200, 41 tools |
| `tool-gateway` (Coolify `ws67wgw1qxdgxo956p2k1jvi`, ovh-app) | Container running, tsnet node joined, VIP service `svc:tool-gateway` live | node renamed `tool-gateway-node` (service/node name collision); VIP `100.110.251.133` / `fd7a:115c:a1e0::1b29:fb86`; auto-approved by `autogroup:tagged` |
| `universal-import-worker` | Token mounted, repointed to `https://tool-gateway.tilapia-skilift.ts.net`, `r2://` resolver registered | first real gateway call succeeded (`repair.detect` → 200) |
| Weaviate `EvidenceChunkV1` | Class created at 2048-d | 0 objects; write probe blocked on zero chunk rows (Go chunker unbuilt) |

## Commit chain (`dd0e60d..HEAD`)

| Hash | What | Live proof |
|---|---|---|
| `ad5f820` | ADR-0052 Part 1 outbox spine (`sql/0071`) + gateway deploy review + ingest redesign plan | Rollback-validated on platform PG: idempotent double-apply, in-txn INSERT/UPDATE/DELETE capture, claim/ack/cursor, dead-letter skip |
| `8ed3191` | Go 1.26 Dockerfile pins, tsnet embed, gateway contract, platform-tools build context | Clears the 5 defects blocking build/redeploy in `2026-09-05-tool-gateway-live-deploy.md` |
| `fa51dde` | Mount tool-gateway service token into universal-import-worker | Worker fails closed at startup without `/run/secrets/tool-gateway-service-token`; token copied ovh-app→ovh-files |
| `cc182a9` | H-04: `working.content_chunk_message` bridge (`sql/0072`); rewire Weaviate feed off dropped chunk table | `to_regclass('working.normalized_record_chunk')` confirmed `NULL` live before the fix |
| `5eda234` | Docs: H-04 nine-site inventory, column mapping, unproven items | 14 pre-existing failures on `tests/test_ingest_port.py` disclosed, not hidden |
| `3952814` | Admit IPv6 tailnet peers in `authorizedTailnetPeer`; log rejections | Rehearsal `rehearsal-20260905-1788604587` got 401 with zero log line until this fix |
| `26a36da` | Trust `X-Forwarded-For` from loopback on tsnet service-mode listeners | Second live finding: gateway saw `remote_addr=127.0.0.1` for every worker call post-IPv6-fix |
| `d06e169` | Dev-only fixture prefix `r2://nexus/uiw/test-fixtures/…` under `PLATFORM_DEV_AUTH_BYPASS` | `/reference-import/start` had rejected the exact ref that `repair.detect` already proved reachable |
| `c3d5475` | Register the `r2://` acquisition resolver in the UIW worker | `retain_original_activity` had died: `no acquisition resolver registered for scheme "r2"` |
| `77e6033` | Pass the acquisition locator (not the retained-object UUID) to repair stages | `assess_source_repair` 422'd 3× on a bare UUID with no URI scheme |
| `72a121e` | Send the detector's structural format (`fmt`) to `repair.preview`, not the declared platform tag | `format=sms_xml` → 422; `format=xml` or omitted → 200, 99 clean chunks |
| `7feea1f` | Mount `source-objects` into parser runtime; persist `{}` for use-original decisions | `execute_parser_activity` couldn't open the retained object; nil `tool_payload` marshaled to `null`, not `{}` |

## Rehearsal chain

| Run | Reached | Outcome |
|---|---|---|
| `rehearsal-20260905-1788604587` | gateway call | 401, no log — root-caused to IPv4-only peer check (`3952814`) |
| `r2c-1788610705` | `assess_source_repair` | 422 — acquisition ref was a UUID with no scheme (`77e6033`) |
| `r2d-1788611759` | `repair.preview` | 422 `sms_xml` — declared-tag vs structural-format mismatch (`72a121e`) |
| `r2e-1788612588` | `awaiting_repair_decision` | **First run through the gateway to the HITL gate**; clean assessment, 99 chunks, 0 repairs |
| `r2f-1788614408` | `execute_parser` | Decision-without-payload fix verified (200); 9 activities completed (register, retain, assess, resolve, capture_filesystem_metadata, fingerprint_source, inventory_container, extract_embedded_metadata, select_parser); `execute_parser` failed — parser-activity-runtime 422 `invalid byte sequence for encoding "UTF8": 0x00` on `element:8`, surfaced to Temporal as an opaque `decode n8n StageResult: EOF` |

## Defects found by running, not by reading

- **IPv4-only tailnet peer check** — proven by a live 401 with no diagnostic log on either
  branch; the cause had to be found by elimination (`3952814`).
- **Loopback X-Forwarded-For untrusted in tsnet service mode** — proven by `remote_addr`
  logging `127.0.0.1` for every worker call after the IPv4 fix landed (`26a36da`).
- **`r2://` resolver never registered in the worker** — proven by `retain_original_activity`
  dying on scheme `"r2"` despite the worker having held R2 credential plumbing since
  2026-08-29; a stale code comment claimed otherwise (`c3d5475`).
- **Gateway addressed by retained-object UUID, not the acquisition locator** — proven by
  three consecutive 422s naming a UUID as having "no URI scheme" (`77e6033`).
- **Declared platform tag sent instead of detector-reported structural format** — proven
  by a direct A/B against platform-tools on the same fixture: `sms_xml` → 422,
  `xml`/omitted → 200 (`72a121e`).
- **`normalized_record_chunk` dead since `0058` (D-116), nine call sites still named it** —
  proven live: `to_regclass('working.normalized_record_chunk') IS NULL` on `platform`,
  meaning the entire native-evidence vector feed (enqueue, drain, activation,
  reconciliation, Workbench read model) was dead on execution (`cc182a9`).
- **Nil `tool_payload` marshals to `null`, not the `{}` the use-original constraint
  requires** — proven by a live 422 on the first repair decision after the HITL gate
  (`7feea1f`).
- **Parser runtime never mounted `source-objects`** — proven by `execute_parser_activity`
  failing 3× unable to open the retained object (`7feea1f`).

## Open owner rulings

1. **NUL bytes in raw records.** PostgreSQL TEXT cannot store `0x00`. D-136 holds that
   content is immutable and the byte-exact record lives in the envelope/H2 hash, not the
   TEXT rendering — but the TEXT rendering itself still needs a ruled substitution
   strategy plus a flag marking the row as sanitized. **Owner ruling required before
   parse-to-raw can be proven.**
2. **n8n→worker webhook error contract.** A parser 4xx currently surfaces to Temporal as
   an opaque `decode n8n StageResult: EOF` instead of a typed `StageResult` error. Needs
   a contract fix, not another silent catch.

## Owed follow-ups

- Doc drift: root `AGENTS.md` `deploy/docker/` row and `deploy/compose.yaml`
  platform-tools block (`context: ..`, `dockerfile: deploy/docker/tools/Dockerfile`)
  still need reconciling against the 2026-09-01 restructure.
- Probe file left at ovh-app `/data/agno/volumes/tool-gateway/materialize/probe-fixture.xml`
  — never-delete rule applies; owner clears it.
- `platform-tools` watch paths were changed via the Coolify API today — record the change
  formally.
- A `.review_hold/store_...txt.body` stray from an aborted heredoc needs quarantine
  review.
- Two subagent transcripts today printed a Coolify token / sentinel token —
  transcript-only exposure, no tracked file affected (per the owner's 2026-08-12
  transcript-exposure amendment, this is not a rotation-triggering incident, but flagging
  per the same rule's spirit).

## Migration ledger note

Neither `0071` nor `0072` self-writes the ledger; the apply script does. The live ledger
was **0 rows** before today and now holds exactly the two rows for `0071`/`0072` — it is a
going-forward record, not a reconstructed history. Whether to backfill it for migrations
already live on `platform` is an **open owner decision**, not yet made.
