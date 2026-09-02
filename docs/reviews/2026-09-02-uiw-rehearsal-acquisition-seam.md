# UIW rehearsal — the acquisition seam is the last blocker

> _Byline: Claude Code · Opus 5 · 2026-09-02 (step 9 rehearsal, live evidence)._

## What the rehearsal proved

First real end-to-end start of `uiw.UniversalImportWorkflow` against the live
stack. Not a synthetic probe — a Temporal workflow that scheduled and ran real
Activities.

- Fixture: `/data/uiw/source-objects/test-fixtures/live-proof-20260827-sample_backup.xml`
  (3,839,897 bytes, sha256 `72640c6c2995d7dd89ce01e5757f7ee5ccc5af2945f1faadefc60339b77c9a55`).
  **Synthetic** — 555-prefix numbers, `contact_name="Mom"`, 95 messages. Never real case material.
- Identity: DEV sentinel per D-126 (`deadbeef-…` / `cafebabe-…`).
- `POST /reference-import/start` → **HTTP 201**, `preview_handle` issued.
- `register_source_activity` → **succeeded**.
- `retain_original_activity` → **FAILED**, 4 attempts, workflow FAILED after 1m15s.

```
retain original: resolve immutable acquisition:
immutable acquisition resolver: acquisition reference must be a file:// URI
```

## Root cause — the worker never wires the scheme router that already exists

`modules/engine/acquisition/` already implements the complete solution:

| Symbol | Resolves | State |
|---|---|---|
| `NewUploadIngressResolver(root)` | `upload://<sha256-hex>` | built + unit-tested |
| `NewCloudflareR2AcquisitionResolver(root, cfg)` | `r2://<bucket>/<key>` | built + unit-tested |
| `NewBackblazeB2AcquisitionResolver(root, cfg)` | `b2://<bucket>/<key>` | built + unit-tested |
| `NewSchemeRouter(map[scheme]resolver)` | dispatches by URI scheme | built + unit-tested |
| `UploadIngress.ServeHTTP` | mints `upload://` refs from posted bytes | built (`acquisition/upload.go`) |

`NewSchemeRouter`'s own doc comment names the intended wiring verbatim:

> `resolvers is keyed by lowercase URI scheme, e.g. {"file": fsResolver, "r2": r2Resolver, "b2": b2Resolver, "upload": uploadResolver}`

**`modules/engine/uiwworker/worker.go:116` bypasses the router entirely**, passing
the bare filesystem resolver straight to `NewSourceLifecycleRepository`:

```go
acquisitionResolver, err := runtimeapi.NewFilesystemImmutableAcquisitionResolver(cfg.SourceObjectDir)
```

So the worker resolves `file://` and nothing else, while the API boundary
(`runtimeapi/source_ref.go`) accepts only `upload://` and `r2://`. The
intersection is empty and every UIW run dies at `retain_original_activity`.

**This is a pure wiring gap, not a missing capability and not a design question.**

> **CORRECTED 2026-09-02:** an earlier revision of this document claimed "no
> resolver exists anywhere" for `upload://` and recommended writing a new
> composite resolver. That was wrong — it was concluded from a grep scoped to the
> wrong directories, which is precisely the "stopped at the first result" failure
> mode. `NewUploadIngressResolver` and `NewSchemeRouter` were both already
> written and tested on 2026-08-28 (Codex · GPT-5). No new resolver is needed and
> no owner design decision is required; the fix is to wire the existing router.

## The fix

In `buildRegistrations` (`modules/engine/uiwworker/worker.go`), construct the
filesystem, upload, and R2 resolvers and combine them with `NewSchemeRouter`
before handing the result to `NewSourceLifecycleRepository`. `upload` and `file`
share `cfg.SourceObjectDir`; `r2` additionally needs the R2 credentials already
mounted at `CASEBIBLE_R2_CONFIG_PATH` (`/run/secrets/casebible-r2.json`).

## Not yet proven

- `execute_parser` never fired, so the n8n bridge still has no end-to-end proof.
  That proof is still owed and still belongs to a completed rehearsal.
- Reject-first (proving `execute_parser` never fires on reject) not reached.
- No `context.*` rows or receipts written beyond `register_source`.
