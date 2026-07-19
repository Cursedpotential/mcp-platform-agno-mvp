# Exec-tier bundle split — 2026-07-19

> _Byline: Claude Code · Sonnet · 2026-07-19_

Owner order: "separate anything that can be separated — if it doesn't have to
be on the same compose then it shouldn't be." Mirrors the proven data-tier
split (commit `18c42d2`, `compose.data-vector.yaml` pattern).

## What changed

The `exec-tier` Coolify app (`rz41wqhpjfh1rj796ixvjhfs`, OVH-1/ovh-app) held
8 services in one `compose.exec.yaml`. Split into 6 independent Coolify apps
+ a 2-service rump:

| Service | New app | Compose file |
|---|---|---|
| contextforge | `exec-contextforge` (`k272znxpa4gh6drmolut723w`) | `compose.contextforge.yaml` |
| desktop | `exec-desktop` (`t130q2xn4r1tux3huee9gal1`) | `compose.desktop.yaml` |
| gateway | `exec-gateway` (`f29166r47gro6fjiq4d8ya92`) | `compose.gateway.yaml` |
| platform-tools | `exec-platform-tools` (`e1mshujml6bv8ldtoe8n7je0`) | `compose.platform-tools.yaml` |
| sandbox | `exec-sandbox` (`mn2autapl223gmgcpjqy7def`) | `compose.sandbox.yaml` |
| agent-ui | *(removed, not split)* | — redundant with standalone `agent-ui` app (`ee2vevjrutfzxlytlu081frh`) |
| agentos-api + agentos-mcp | `exec-tier` (rump, unchanged uuid) | `compose.exec.yaml` |

All bind mounts reattached at the same absolute host paths — **zero data
migration**. A new shared external docker network `agno` was created on
OVH-1 (`docker network create agno`), mirroring OVH-3's `agno` net from the
data-tier split, so agentos-api/mcp keep reaching `contextforge:4444` and
`platform-tools:8085` by the SAME docker-DNS names as before — env values
(`CF_GATEWAY_URL`, `SBV_BASE_URL`) are unchanged.

## Cutover mechanics

Doors policy: each new app was created, had its env subset copied from the
bundle, deployed, and functionally verified BEFORE the corresponding old
container was stopped and the block removed from `compose.exec.yaml`. Since
each service binds a single host port shared with its bundle twin, a literal
zero-gap handoff isn't physically possible (same host, same port) — the
practical equivalent used: verify the new app on an alternate bind (or its
own uuid-scoped port) where possible, then do a stop-old → start-new →
verify swap measured in seconds, with an immediate rollback path (`docker
start` the old container) if verification failed.

Full per-service before/after, verification evidence, and the agent-ui
investigation are in `exec-tier-split-result.md` (delivered separately to
the owner's OneDrive AI Space folder, not checked into this repo since it
contains infra UUIDs and Coolify app inventory detail).

## Reversible

Revert this commit + `docker start` any stopped bundle containers still
present + delete the new apps. No volumes or images were touched.
