# Coolify Watch Paths — Go Service Trio (BUILD LANE D1)

> _Byline: Claude Code · Sonnet 5 · 2026-09-02 (BUILD LANE D1: repair the three Go
> service builds post-restructure — vendored the Go module graph and made the
> Dockerfiles/compose context hermetic; this file records the corrected Coolify
> Watch Paths that follow from that fix)._

This file is the reference for what to paste into each Coolify application's
**Watch Paths** field for the three Go services built from `modules/engine/`.
Coolify only triggers a rebuild of an app when a changed file matches one of
its own watch paths, so these lists must cover everything that can change the
built image and nothing so broad it forces needless rebuilds. See
`AGENTS.md` → "Deploy & Data-Tier Gotchas" (this repo's root memory) for why
watch paths matter: apps without them redeploy on every push to `main`.

## Why `modules/forks/sbv/**` is deliberately EXCLUDED now

Before this repair, all three Dockerfiles built directly from a live
`vendored/sbv/` (now `modules/forks/sbv/`) checkout via `COPY vendored/sbv/ ...`,
so a change there could change the built binary and the old watch-path comments
listed it for `proffer-worker` and `parser-activity-runtime`.

That is no longer how the build gets sbv's source. `modules/engine/go.mod` has:

```
require github.com/lowcarbdev/sbv v0.0.0
replace github.com/lowcarbdev/sbv => ../forks/sbv
```

`go mod vendor` (run from `modules/engine/`) resolved that replace and
snapshotted sbv's Go source into `modules/engine/vendor/github.com/lowcarbdev/sbv/`.
All three Dockerfiles now build with `-mod=vendor`, which never consults the
`replace` target directory or the network — verified by temporarily moving
`modules/forks/sbv/` out of the way and re-running `go build -mod=vendor ./...`
and `go vet -mod=vendor ./...` from `modules/engine/` (both passed; see the
BUILD LANE D1 report for the transcript). So:

- A change inside `modules/forks/sbv/` does **not** change what Docker builds
  until someone re-runs `go mod vendor` in `modules/engine/`, which lands its
  effect as a diff under `modules/engine/vendor/**` — already covered by the
  `modules/engine/**` watch path below.
- Watching `modules/forks/sbv/**` directly would be both wrong (it's a
  gitignored-at-Coolify-clone-time private submodule Coolify may not even be
  able to check out) and pointless (its content isn't what gets COPYed into
  the build).

If a future change updates the vendored sbv snapshot, that always shows up as
a `modules/engine/vendor/**` diff, so no separate watch path is needed.

## Per-app Watch Paths

### `proffer-worker` (`deploy/proffer-worker.yaml`)

Paste into Coolify's Watch Paths field for this app:

```
modules/engine/**
deploy/docker/proffer-worker/**
deploy/proffer-worker.yaml
```

### `proffer-starter` (`deploy/proffer-starter.yaml`)

```
modules/engine/**
deploy/docker/proffer-starter/**
deploy/proffer-starter.yaml
```

### `parser-activity-runtime` (`deploy/parser-activity-runtime.yaml`)

```
modules/engine/**
deploy/docker/parser-activity-runtime/**
deploy/parser-activity-runtime.yaml
```

## Notes

- These lists intentionally do **not** include `modules/forks/sbv/**` — see
  above.
- `modules/engine/**` includes `modules/engine/vendor/**`, `go.mod`, `go.sum`,
  and all source packages, so a `go mod vendor` re-snapshot, a dependency bump,
  or an ordinary code change under `modules/engine/` all correctly trigger a
  rebuild.
- The build context for all three apps is now the repo root (`context: ..`
  relative to the `deploy/` directory that holds the compose file), and each
  compose file sets an explicit `dockerfile: deploy/docker/<app>/Dockerfile`
  path — see the compose files themselves and the Dockerfiles for the
  corresponding `COPY modules/engine/ ./` step.
- This file is a **paste-in reference**, not something applied automatically —
  no Coolify API call was made as part of producing it (owner instruction:
  "Do NOT call the Coolify API"). Apply these values by hand in each app's
  Coolify **Configuration → General → Watch Paths** field.
