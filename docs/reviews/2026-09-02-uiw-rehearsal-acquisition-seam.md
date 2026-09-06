# UIW rehearsal — the acquisition seam (FIXED, verified live) and what it uncovered

> _Byline: Claude Code · Opus 5 · 2026-09-02 (step 9 rehearsal, live evidence)._
> _Naming: written before the 2026-09-05 rename (D-137..D-141); see docs/NAMING.md for the old->new glossary._

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

## ~~Not yet proven~~ superseded — see the live results below

### (original section, kept for the record)

#### Not yet proven

- `execute_parser` never fired, so the n8n bridge still has no end-to-end proof.
  That proof is still owed and still belongs to a completed rehearsal.
- Reject-first (proving `execute_parser` never fires on reject) not reached.
- No `context.*` rows or receipts written beyond `register_source`.


---

# LIVE RESULT — the fix works, and the next blocker is a cross-host path assumption

> _Appended 2026-09-02 after redeploy. Byline: Claude Code · Opus 5._

## The acquisition seam is CLOSED (verified live, not inferred)

`modules/engine/uiwworker/worker.go` now builds the filesystem and upload resolvers and
combines them with `acquisition.NewSchemeRouter`. Deployed via Coolify (auto-deploy fired
on push; the worker container restarted `2026-09-02T21:57:39Z`).

Rehearsal run 2 — workflow `07918399-c2fc-4020-8ca1-18be271ef986`, DEV sentinel identity,
synthetic fixture `upload://72640c6c…` (95 messages, 555-prefix numbers):

| Stage | Before the fix | After |
|---|---|---|
| `POST /reference-import/start` | 201 | 201 |
| `register_source_activity` | OK | OK |
| `retain_original_activity` | **FAILED** — "acquisition reference must be a file:// URI" | **SUCCEEDED** |
| `assess_source_repair_activity` | never reached | **FAILED** — new blocker below |

**A UIW run has now resolved an `upload://` reference and retained an original for the
first time.** That was the defect blocking every run since the workflow was written.

## New blocker — platform-tools is on a different host than the object it is asked to read

`assess_source_repair_activity` calls `POST {PLATFORM_TOOLS_BASE_URL}/tools/repair.detect/run`
with `{"path": <worker-local filesystem path>}` (`activities/repair.go`, via
`Store.ResolveOriginalPath`). The response is a 404 whose body is the path itself:

```
{"detail":"/data/uiw/source-objects/objects/sha256/72/72640c6c….source"}
```

Ground truth:

- worker runs on **ovh-files** (`100.91.190.107`)
- `PLATFORM_TOOLS_BASE_URL=http://100.72.169.40:8090` → **ovh-app**
- `/data/agno/volumes/universal-import/source-objects` **does not exist on ovh-app**
- the platform-tools container mounts only `/opt/sbv/data` and `/r2`

So this is not a missing tool and not a routing error. `repair.detect` **is** registered.
The UIW passes a host-local filesystem path across a host boundary. Same class of defect as
the acquisition seam: two individually-correct halves with an incompatible contract.

It also violates the atomicity rule committed today (AGENTS.md): references may travel,
host-local paths may not.

## Correction — platform-tools exposes 39 tools, not the engine's 11

An earlier chat-only claim that the Lost and Found corpus had "no parser" for Claude
exports, `.docx`, and PDFs was **wrong**: it counted only the Go engine's registered
parsers. `GET /tools` on platform-tools returns **39**, including
`transcripts.claude-ai-export`, `transcripts.chatgpt-official`, `transcripts.perplexity-gdpr`,
`transcripts.markdown`, `transcripts.generic-md`, `documents.extract-docling`,
`documents.extract-text`, `repair.pdf-inspect`, and the `messages.*` family. Format coverage
is materially better than reported; the gap is delivery, not capability.

## RULED 2026-09-02 — (B), the Go tool gateway. (A) is rejected.

- **(A) Interim, config only:** run a second platform-tools on ovh-files with the
  `source-objects` volume mounted and repoint `PLATFORM_TOOLS_BASE_URL`. Unblocks the
  rehearsal today; leaves a duplicate service to dismantle later.
- **(B) Go tool gateway on tsnet (owner proposal, 2026-09-02):** a Go front end with its own
  Tailscale identity that indexes the tools, accepts **locators** (`upload://`, `r2://`)
  instead of host paths, resolves bytes through the existing
  `acquisition.NewSchemeRouter`, materializes locally, and calls the Python tool with a path
  that genuinely exists. The Python tools keep their one-job contract unchanged. Permanent,
  removes the cross-host assumption everywhere, and each call becomes a clean atomic unit
  schedulable as an Activity or wrappable as an n8n node.

**Owner ruled (B) and rejected (A) outright, 2026-09-02:** "Otherwise what will end up
happening is what we joke around about when we're working on houses about things that get
done temporarily. It becomes temporary-permanent." A second platform-tools stood up to
unblock one evening would never be dismantled; it would become the architecture by default.
No interim instance is to be created. See D-132.
