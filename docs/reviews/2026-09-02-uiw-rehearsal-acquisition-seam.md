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

## Root cause — the API boundary and the worker accept disjoint URI schemes

| Scheme | API accepts? (`runtimeapi/source_ref.go`) | Worker resolves? (`uiwworker/worker.go:116`) |
|---|---|---|
| `upload://<sha256>` | **yes** | **no resolver exists anywhere** |
| `r2://casebible-sorted/<key>` | **yes** | resolver EXISTS (`acquisition.NewCloudflareR2AcquisitionResolver`) but is **not wired** |
| `b2://…` | no | resolver exists, not wired |
| `file://<abs path>` | **no** | **yes** — the only one wired |

**Every URI form the API accepts is unresolvable by the worker, and the only form
the worker resolves is rejected by the API.** The intersection is empty. This is
why no UIW run has ever completed end to end — it is not a config slip, it is an
unclosed seam between two correct halves.

`worker.go:116` wires only `runtimeapi.NewFilesystemImmutableAcquisitionResolver(cfg.SourceObjectDir)`.

## Secondary findings (both real, neither is the blocker)

1. **Duplicate `POST /reference-import/start` handlers.** `temporal/httpapi.go`
   `StarterHTTPHandler` (tailnet IP + honors `PLATFORM_DEV_AUTH_BYPASS`) and
   `runtimeapi/uiw_preview.go` `PreviewHTTPHandler` (tailnet IP **AND** bearer
   service token, **ignores the bypass**). The live service runs the preview
   handler — correct, since it carries the full HITL surface. So the **D-125 dev
   bypass was wired to the handler that is not serving**. Consequence: n8n's
   container egress still cannot reach the starter, because the bypass it relies
   on is inert on the live route. Amends the D-125 §9 note.
2. **`preview` query 503 is a symptom, not a bug.** `workflow.SetQueryHandler`
   (`uiw/workflow.go:99`) runs *after* `retain_original`, so a run blocked there
   never registers the handler. `KnownQueryTypes` showing only builtins is
   expected under this failure, not evidence of a missing handler.

## Owner decision needed — how `upload://` resolves

The object is already content-addressed on disk at
`<SOURCE_OBJECT_DIR>/objects/sha256/<xx>/<sha256>.source`, published by the
filesystem resolver's hard-link primitive. Two candidate closures:

- **(A) Scheme-dispatching composite resolver.** One resolver that routes by
  scheme: `upload://<sha>` → the already-published immutable object (a lookup,
  not a re-copy — the bytes are already sealed and hashed); `r2://` → the
  existing Cloudflare resolver; `file://` retained for internal callers only.
  Smallest change, wires what already exists, keeps one boundary.
- **(B) Widen the API to accept `file://`.** Rejected on its face — it would let
  a caller name any absolute path on the worker, which is exactly what the
  `upload://`/`r2://` allowlist exists to prevent.

Recommendation: **(A)**. It closes the seam without weakening the boundary, and
`upload://` resolving to an already-sealed content-addressed object is the
semantics the digest form was clearly designed for.

## Not yet proven

- `execute_parser` never fired, so the n8n bridge still has no end-to-end proof.
  That proof is still owed and still belongs to a completed rehearsal.
- Reject-first (proving `execute_parser` never fires on reject) not reached.
- No `context.*` rows or receipts written beyond `register_source`.
