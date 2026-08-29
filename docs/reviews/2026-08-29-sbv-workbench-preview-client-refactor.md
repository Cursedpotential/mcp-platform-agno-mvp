# SBV → Workbench preview-client refactor receipt

> _Byline: Codex · GPT-5.6 · 2026-08-29._

STATUS: PARTIAL — UIW-native Workbench boundary implemented; upstream read surface and legacy SBV retirement remain

BUILD_STATUS: PASS — focused boundary test, Workbench ESLint, TypeScript, and static production build

LIVE_STATUS: NOT DEPLOYED OR LIVE-PROVEN

REVIEW_STATUS: INDEPENDENT REQUEST-CHANGES REMEDIATED LOCALLY; RE-REVIEW REQUIRED

## Result

The useful SBV viewing behavior now has a native Workbench home at
`/evidence/preview`. The route is rendered inside the existing Workbench shell and crosses one
platform-owned boundary: an opaque `preview_handle` returned by intake.

- UIW snapshot and authenticated decision calls keyed only by `preview_handle`;
- a dedicated UIW event stream with monotonic event ids and `Last-Event-ID` replay;
- paginated platform messages, participants, and attachment metadata;
- typed reference-only custody/parser/normalization/storage/completeness receipts;
- an intake completion link carrying only the encoded preview handle into the native route;
- Workbench authentication and fixed-case shell context inherited from the root layout.

The new client contains no SBV login, upload, settings, SQLite, or `:8085` API dependency. It is
read-only except for the governed UIW approve/reject decision. The browser submits only the
decision and reason. The BFF derives immutable `subject_uid` and username from Authentik-backed
`request.state`; it accepts no browser-supplied owner, role, or decider.

The earlier local slice passed Temporal workflow/run ids to legacy records and run-event APIs.
That was a real boundary defect. Those calls are no longer present in the active preview or
intake flow, and the BFF fails closed when the upstream starter returns only workflow/run ids
instead of a dedicated preview handle.

An independent review then found two additional release-blocking defects. Both are remediated in
the local slice:

- the BFF now compares every returned snapshot/message-page handle with the exact requested handle
  and also correlates the decision response handle before accepting it; malformed upstream JSON is
  normalized to a fail-closed 502;
- the browser aborts and generation-fences A→B handle switches, serializes each pagination cursor,
  and deduplicates messages by stable message ID;
- intake no longer exposes approve/reject. It opens the pipeline preview, where a decision stays
  locked until the exact correlated normalized messages, participant/attachment source locators,
  and all required completed receipts have loaded;
- the viewer renders the modeled correlation, generation, receipt, participant, message-provenance,
  and attachment-integrity fields rather than hiding them behind counts.

The executable contract is documented at `docs/plans/uiw-preview-contract.md`.

## Settled boundary implemented

| Concern | Authority after this slice |
|---|---|
| Outer navigation, case context, authentication | Workbench |
| Workflow preview + human decision | Workbench BFF → UIW/Temporal contract |
| Pipeline progress | Workbench same-origin SSE → dedicated UIW preview-event stream |
| Message rendering | Native Workbench client → paginated UIW platform-message projection |
| Canonical storage | PostgreSQL/platform spine — never SBV SQLite |
| Intake and parsing | Shared platform ingest contract / Go coordinator |
| Custody hashing | Separate custody activity before parse |
| Vite unified-operator-surface | Design donor/prototype only; not used by this route |

## Caller and dependency audit

### Legacy SBV remains a stateful application today

`vendored/sbv/main.go` still exposes its own authenticated `/api` surface for registration,
login/logout, password changes, upload/progress, conversations, messages, activity, calls,
date range, media, search, settings, analytics, hashes, universal imports, and automation.
Those handlers read and write SBV-owned databases via `DB_PATH_PREFIX`.

The legacy React application is coupled directly to those routes through `VITE_API_URL` with a
`:8085/api` default. Its useful donor components are conversation listing, message-thread
rendering, activity, calls, search, and media display. Its login, password, settings, upload,
evidence-import, and polling flows belong to the layer being retired and were not ported.

### Production manifests still run and persist legacy SBV

- `docker/tools/supervisord.conf` starts `/opt/sbv/sbv` independently from the Python tool
  facade and pins `DB_PATH_PREFIX=/opt/sbv/data`.
- `deploy/platform-tools.yaml` publishes `:8085`, mounts
  `/data/agno/volumes/sbv_data:/opt/sbv/data`, and describes `platform-tools:8085` as an internal
  dependency.
- `deploy/compose.yaml` and `deploy/exec.yaml` still supply
  `SBV_BASE_URL=http://platform-tools:8085`.
- `server/tools/_sbv_client.py` and `server/analysis/sbv_transcript.py` still call the legacy
  service. This is runtime caller proof that the service cannot yet be quarantined.

No manifest, volume, database, or legacy frontend file was removed or changed in this slice.

### Corrected platform contract and current upstream gap

The Workbench BFF now defines these same-origin routes:

- `GET /api/uiw/previews/{preview_handle}` — correlation, parser identity/config digest,
  preview digest, phase, and typed receipts;
- `GET /api/uiw/previews/{preview_handle}/messages?cursor=&limit=` — participants, messages,
  and attachment metadata;
- `GET /api/uiw/previews/{preview_handle}/events` — typed monotonic SSE events; forwards
  `Last-Event-ID` and fails on malformed, mismatched, or non-monotonic events;
- `POST /api/uiw/previews/{preview_handle}/decision` — approve/reject plus server-derived actor.

The Go starter currently exposes only workflow-id start/decision/preview endpoints. It does not
yet return `preview_handle` or implement the three UIW read surfaces above. The BFF deliberately
does not derive or relabel a handle from those ids, so current live start/read calls fail closed
until the Go contract is implemented.

## Files changed or added

- `workbench/web/src/app/evidence/preview/page.tsx`
- `workbench/web/src/components/sbv/uiw-preview-client.tsx`
- `workbench/web/src/components/sbv/platform-message-viewer.tsx`
- `workbench/web/src/components/intake/unified-intake.tsx`
- `workbench/web/src/lib/api-client.ts`
- `workbench/web/src/lib/shared/types.ts`
- `workbench/web/smoke/sbv-preview-boundary.contract.test.mjs`
- `workbench/api/app/types/uiw.py`
- `workbench/api/app/service/uiw.py`
- `workbench/api/app/runtime/uiw.py`
- `workbench/api/tests/test_uiw_contract.py`
- this receipt

After proving they had no remaining callers, the first erroneous legacy-ID preview component and
its record-presentation helper were moved (not deleted) to repository-root `to_be_deleted`.

## Verification performed

From `workbench/web`:

```text
node --test smoke/sbv-preview-boundary.contract.test.mjs
PASS — 5 tests

npm run lint -- --quiet
PASS

npm run build
PASS — Next.js 16.3.1; /evidence/preview generated as a static route

uv run pytest -q workbench/api/tests/test_uiw_contract.py
PASS — 17 tests

uv run ruff check workbench/api/app/types/uiw.py workbench/api/app/service/uiw.py \
  workbench/api/app/runtime/uiw.py workbench/api/tests/test_uiw_contract.py
PASS
```

These checks prove the local client boundary and production build only. They do not prove a
deployed route, the missing upstream preview-handle/read contract, a live Temporal workflow, a
live UIW SSE stream, or live platform messages.

## Required next slices

1. **Go preview boundary.** Generate and persist an opaque preview handle at start; resolve it
   server-side to the workflow plus request/source/generation correlation; implement the
   snapshot, paginated message/participant/attachment, typed receipt, decision, and replayable
   monotonic event endpoints expected by the BFF.
2. **Conversation/thread query.** The platform read surface must preserve reviewed first-/third-
   party participants and conversation anchors without inventing grouping in the browser.
3. **Full content and attachments.** The UIW message page must return platform-owned source
   locators and attachment metadata/derivative references; the client must never fall back to
   `/api/media` on SBV.
4. **Legacy caller cutover.** Move the remaining `_sbv_client` and `sbv_transcript` behavior to
   Go coordinator/platform contracts, prove no callers remain, inventory the mounted SBV data,
   then quarantine the old app/manifests/data references under `to_be_deleted`. No hard delete.
5. **Navigation exposure and live proof.** Add the route to the focused Workbench navigation only
   after Coolify deployment plus a real workflow are verified.

## Known safety boundary

The client does not claim that preview messages are evidence, keeps PostgreSQL canonical, and
performs no promotion. Custody remains a separate upstream activity and is represented only by
a typed receipt reference; it is never simulated in the browser.

## Owner addendum — retained-source authority and pre-port defects

Retained source XML, not SBV SQLite, is the historical MMS migration/completeness authority. The
SQLite `media_data` BLOBs contain only the first decoded non-SMIL MMS part, while the retained XML
contains all parts. Migration proof must therefore enumerate and verify source XML attachments;
matching SQLite rows would preserve the historical loss.

Three defects must be fixed before port/re-ingest acceptance: the first-MMS-part-only decoder,
empty RCS group names from `extractGroupNameFromTrID`, and H3 continuity restarting at batch
boundaries. H3 remains the responsibility of the separate custody activity, not the parser or UI.
The custody activity's dedupe false-success guard has independent focused proof for its three
branches (`tests/test_c26_resilience.py -k dedupe`: 3 passed), but this receipt does not claim the
three port defects or live re-ingest are complete.
