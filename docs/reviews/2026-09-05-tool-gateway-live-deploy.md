# Tool gateway live deploy attempt — BLOCKED on three committed-repo defects

> _Byline: Claude Code · Opus 5 · 2026-09-05._
>
> Owner-authorized live infra execution (2026-09-04 23:50). Constraint in force
> for this session: **no git commits or pushes.** Every blocker below is a
> one-to-few-line repo change, which is exactly why the session stopped here.

## Outcome, first

| Step | Result |
|---|---|
| 1. platform-tools materialize mount | **STOPPED — compose is repo-sourced.** Needs a commit. |
| 2. Create + deploy Coolify app `tool-gateway` | App **created** (`ws67wgw1qxdgxo956p2k1jvi`); **build failed twice**. No container, no tailnet node. |
| 3. Repoint `universal-import-worker` | **NOT DONE — blocked by code, not config.** The worker cannot speak the gateway protocol. |
| 4. Rerun the UIW rehearsal | **NOT RUN.** Nothing downstream of step 2 exists. |

The rehearsal state is unchanged from 2026-09-02: still blocked at
`assess_source_repair_activity`.

## Ground truth gathered live (ovh-app, 2026-09-05T04:03Z)

- platform-tools container `platform-tools-e1mshujml6bv8ldtoe8n7je0-232025273521`,
  `StartedAt = 2026-08-29T23:26:12.769922584Z`, `Up 6 days (healthy)`.
- Its mounts are only `/data/agno/volumes/sbv_data -> /opt/sbv/data` and the
  rclone `r2-nexus -> /r2`. **No materialize mount.**
- `curl http://100.72.169.40:8090/tools` → **200**. `curl http://127.0.0.1:8090/tools`
  → **000 (connection refused)**. platform-tools binds `BIND_IP`, not loopback, so
  the correct value is `PLATFORM_TOOLS_BASE_URL=http://100.72.169.40:8090` even for
  a co-located `network_mode: host` caller. `GET /` returns 404; `/tools` is the
  working liveness route.
- platform-tools runs as **uid 0** inside the container, so it can read a
  materialize bind mount regardless of host ownership.
- Host prep verified present: `/data/agno/volumes/tool-gateway/{materialize,seal,tsnet}`
  (10001:10001, 0750), `/data/agno/secrets/tool-gateway/{ts-authkey,service-token}`,
  `/data/agno/secrets/casebible-r2.json`.
- **Change made (host, non-destructive):** the three secret files were owned
  root:root 0600/0400 while the gateway container runs as uid 10001, so they were
  chowned to `10001:10001` (0400) and `casebible-r2.json` to `root:10001` (0440).
  No secret values were read or printed.
- `tailscale status` on ovh-app: **no `tool-gateway` node**. `tailscale serve status`
  still shows only `https://workbench.tilapia-skilift.ts.net (tailnet only) (svc:workbench)`.

## Blocker 1 — platform-tools' compose is repo-sourced, and it cannot rebuild at all

Coolify app `exec-platform-tools` (`e1mshujml6bv8ldtoe8n7je0`) is
`build_pack=dockercompose`, `git_repository=Cursedpotential/mcp-platform-agno-mvp`,
`git_branch=main`, `base_directory=/`, `docker_compose_location=/deploy/platform-tools.yaml`.
`docker_compose_raw` is a normalized copy of the repo file and is re-read from git
on every deploy. **Editing it through the API would be discarded.** Adding
`/data/agno/volumes/tool-gateway/materialize:/data/toolgw/materialize:ro` therefore
requires editing `deploy/platform-tools.yaml` and pushing.

**Worse, and newly discovered:** redeploying platform-tools today would fail the
build. The deployment log proves Coolify runs
`docker compose --project-directory /artifacts/<uuid> -f /artifacts/<uuid>/deploy/<file>.yaml build`,
so `context: .` resolves to the **repository root**, not the compose file's
directory. Under that rule:

- `deploy/platform-tools.yaml` names `dockerfile: docker/tools/Dockerfile` →
  `<root>/docker/tools/Dockerfile`, which **no longer exists** (moved to
  `deploy/docker/tools/` in the 2026-09-01 restructure).
- `deploy/docker/tools/Dockerfile` is itself internally inconsistent: it does both
  `COPY docker/tools/tools/ ...` (only valid with a `deploy/` context) and
  `COPY server/ ...` (only valid with a repo-root context). Neither context
  satisfies both.

> **CORRECTION to `AGENTS.md` (2026-09-01 restructure note).** The claim that
> "compose files in `deploy/` now resolve their `./docker/...` build contexts
> correctly per the compose spec" is **false under Coolify**, which passes
> `--project-directory <repo root>`. The working reference is
> `deploy/universal-import-worker.yaml`: `context: .` +
> `dockerfile: deploy/docker/universal-import-worker/Dockerfile`, which built and
> deployed successfully (worker container `StartedAt = 2026-09-02T22:08:06.702442351Z`).
> `deploy/tool-gateway.yaml` already follows that correct pattern;
> `deploy/platform-tools.yaml` and `deploy/docker/tools/Dockerfile` do not.

Consequence: the materialize-mount commit **must also** fix the platform-tools
dockerfile path and the tools Dockerfile COPY paths, or the redeploy that applies
the mount will take platform-tools down.

## Blocker 2 — the tool-gateway image cannot build from `main`

Coolify app **created successfully**:

- name `tool-gateway`, uuid `ws67wgw1qxdgxo956p2k1jvi`
- server `ovh-app` (`fmuao9enq3nxk8qw5hqjzzce`), project `agno-platform`
  (`nbg0ocqqrf91xag492yjqf5i`), environment `production`
- `POST /applications/private-github-app`, `github_app_uuid=r4mhpblr8cnxk3481r07xxz0`
  (`cursedpotential`, the same private GitHub app the other apps use) → **HTTP 201**
- `git_branch=main`, `base_directory=/`,
  `docker_compose_location=/deploy/tool-gateway.yaml`
- watch paths set at creation: `modules/engine/**`,
  `deploy/docker/tool-gateway/**`, `deploy/tool-gateway.yaml`
- env set via `PATCH .../envs/bulk` → **HTTP 201**:
  `PLATFORM_TOOLS_BASE_URL=http://100.72.169.40:8090`,
  `TOOL_GATEWAY_TS_HOSTNAME=tool-gateway`, `TOOL_GATEWAY_TS_SERVICE=svc:tool-gateway`,
  `TOOL_GATEWAY_TS_TAGS=tag:docker`, `TOOL_GATEWAY_PORT=8099`,
  `TOOL_GATEWAY_IMAGE=platform-tool-gateway:latest`

### Deploy 1 — `s1fwlsj3wodibvo1jbmpxrdw` → failed

```
#12 0.361 go: go.mod requires go >= 1.26.6 (running go 1.25.14; GOTOOLCHAIN=local)
```

`modules/engine/go.mod` declares `go 1.26.6`, but **all four** Go service
Dockerfiles still pin `FROM golang:1.25-bookworm`
(`tool-gateway`, `universal-import-worker`, `universal-import-starter`,
`parser-activity-runtime`). The whole Go build lane on `main` is broken; the UIW
worker only survives because its image was built on 2026-09-02, before the bump.

**Config-only workaround applied, and it must not become permanent:** a
build-time env `GOTOOLCHAIN=auto` was added to the `tool-gateway` app, which lets
the toolchain self-download (log: `go: downloading go1.26.6 (linux/amd64)`).
**Delete that variable once the Dockerfiles pin `golang:1.26`.** It is recorded
here specifically so it does not become temporary-permanent (D-132).

### Deploy 2 — `xcgutfwuov4ahtxjs2uril6w` → failed

```
#12 0.359 go: downloading go1.26.6 (linux/amd64)
#12 10.42 vendor/github.com/tailscale/web-client-prebuilt/embed.go:12:12:
          pattern build: no matching files found
```

Root cause, verified: the vendored package carries its **own** `.gitignore`
containing `build/`
(`modules/engine/vendor/github.com/tailscale/web-client-prebuilt/.gitignore:9`),
so `git ls-files .../web-client-prebuilt/build` returns **0 files** — the embedded
asset directory exists on the developer's disk but was never committed. Every
clean clone (Coolify, CI, any other machine) fails this `//go:embed build`.
`tailscale.com/client/web/assets.go:19` pulls it into the `tsnet` import graph, so
this blocks every future tsnet service, not just this one.

Fix options, all requiring a commit: force-add the directory (`git add -f`), add a
negating rule in the repo `.gitignore`, or exclude the web client from the build.

## Blocker 3 — the worker cannot call the gateway (code, not config)

Even with a running gateway, step 3 is not a config change:

- `modules/engine/activities/repair.go:122` calls
  `a.Client.Run(ctx, "repair.detect", map[string]any{"path": path})` — the raw
  platform-tools payload with a **worker-local path**.
- `modules/engine/toolgateway/http.go:106` decodes with `DisallowUnknownFields`
  and requires `{"source_ref": "...", "args": {...}}`. A `{"path": ...}` body is a
  **400**, not a 404 — the failure mode would change, not disappear.
- `modules/engine/runtimeapi/platform_tools_client.go` sends **no `Authorization`
  header**, and `modules/engine/uiwworker/config.go` has **no service-token
  variable**. With `TOOL_GATEWAY_SERVICE_TOKEN_FILE` mounted, every worker call
  would be **401**. (`/healthz` is deliberately unauthenticated; `/tools` and
  `/tools/{id}/run` are not.)

So repointing `PLATFORM_TOOLS_BASE_URL` at the gateway today would replace one
broken call with a differently broken call. The gateway-shaped client
(locator + bearer) and a `RepairActivityStore` that yields a **locator** instead of
`ResolveOriginalPath`'s host path are still owed engine work.

## Required change set before this can be retried

1. `deploy/docker/tool-gateway/Dockerfile` — `golang:1.25-bookworm` → `golang:1.26-bookworm`
   (and the other three Go Dockerfiles, which are equally broken).
2. `modules/engine/vendor/github.com/tailscale/web-client-prebuilt/build/**` —
   commit the embedded assets (or exclude the web client).
3. `deploy/platform-tools.yaml` — add the materialize `:ro` mount **and** fix
   `dockerfile:` to `deploy/docker/tools/Dockerfile`; reconcile
   `deploy/docker/tools/Dockerfile`'s COPY paths to a repo-root context.
4. `deploy/tool-gateway.yaml` — correct the "reached over loopback" comment;
   loopback is refused, the `BIND_IP` address is required.
5. Engine work for Blocker 3 (separate change, after the gateway is proven live).

Then: redeploy platform-tools, deploy `tool-gateway`, verify the tsnet node joins
and `svc:tool-gateway` is advertised, and only afterwards take up Blocker 3.

## Session artifacts

- Coolify app `tool-gateway` = `ws67wgw1qxdgxo956p2k1jvi` (exists, never ran).
  Failed deployments `s1fwlsj3wodibvo1jbmpxrdw`, `xcgutfwuov4ahtxjs2uril6w`.
- No repository files were changed and nothing was committed or pushed.
- Host changes on ovh-app: secret-file ownership only (above). No deletions.
