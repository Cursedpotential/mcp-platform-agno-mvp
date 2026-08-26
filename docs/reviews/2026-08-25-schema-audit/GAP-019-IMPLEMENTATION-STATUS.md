# GAP-019 Implementation Status — collision-safe deployment-drift checker

> _Byline: Claude Code · Sonnet 5 · 2026-08-26_
> Owning packet (isolated): `scripts/check_deploy_drift.py`, `tests/test_check_deploy_drift.py`,
> `tests/fixtures/deploy_drift/sample.json`, the live receipt JSON alongside this file, this
> status document. No deploy manifest, Coolify resource/env, canon/decision/index doc, Workbench,
> server code, SQL, Timesketch file, or existing shared script was touched.

## Source finding

`docs/reviews/2026-08-25-schema-audit/AUDIT-GAP-REGISTER.md` row 29 (GAP-019, High,
R00/R01/R05/R06/R10/R12/R13/R14):

> Many Coolify Watch Paths still reference pre-move `compose.*` names while active manifests are
> under `deploy/` (read-only Coolify probe, 2026-08-26); app `git_commit_sha` values are `HEAD`,
> not immutable SHAs.

Acceptance gate: "Per-app checker proves branch, manifest path, watch paths, rendered config hash
and finished deployment SHA against intended remote commit."

Related: `PLATFORM-NAMING-CENSUS-AND-HANDOFF.md` §2.5 finding **NC-1** (the compose-consolidation
commit `4dff58a`/`106aacb` moved manifests to `deploy/*.yaml` but did not update watch paths on
"at least a dozen apps") and stop-gate **SG-7** ("false green" — an app must not be marked done
until its deploy was proven triggered by the intended watch path, not a manual redeploy masking a
stale one).

## What was built

### `scripts/check_deploy_drift.py` — the checker

A single, platform-neutral script with no external framework. Two read-only data sources:

1. **Coolify REST API** — `GET /applications` (one call returns every app's `git_repository`,
   `git_branch`, `docker_compose_location`, `watch_paths`, `git_commit_sha`, `config_hash`,
   `status` — no per-app detail call needed) and `GET /deployments/applications/{uuid}` (per-app
   deployment history with each entry's `commit` and `status`). Auth follows the existing
   `scripts/audit_coolify_exec_env.py` convention exactly: token from
   `~/.secrets/coolify-ionos-api.env` via a tolerant `KEY=VALUE` parse, never `source`d. **GET
   only — the client has no write method and cannot mutate Coolify.**
2. **Local git refs** (`origin/<branch>`) in the same checkout — `git rev-parse` /
   `git cat-file -e`, both read-only, neither fetches nor writes. Used to answer "does this path
   exist at the tip of the branch this app claims to deploy from" and "what commit does that
   branch currently point at". A branch not present locally resolves to `None`, which the checker
   reports as `skipped` (with an explicit "run `git fetch`" hint) — **never** as a false
   actionable or a false clean.

Five checks per app, each independently reasoned from the two sources above — no hand-maintained
map of "what each app should be" was created, because that map would itself drift (exactly the
failure mode GAP-019 is about). Instead the checker treats each app's *own* configured branch as
the source of truth and asks whether the app is internally consistent with it:

| Check | Detects |
|---|---|
| `commit_sha_immutability` | `git_commit_sha` is not a 40-hex SHA (i.e. is `"HEAD"` or similar) — the deploy trigger is a moving ref |
| `watch_coverage` | the app's own `docker_compose_location` is not itself covered by any of its watch-path entries (exact match or `dir/**` prefix) — the SG-7 false-green risk, and also catches apps with **no** watch paths at all |
| `retired_watch_paths` | a watch-path entry is a bare root `compose.*.yaml` / `docker-compose.yaml` name that no longer exists at the tip of the app's own branch — the literal NC-1 defect, generalized past the dozen apps NC-1 named by hand |
| `compose_location_exists` | the configured manifest path itself doesn't exist at the tip of the app's own branch (a stronger break than a stale watch path) |
| `deployment_commit_drift` | the latest **finished** deployment's commit doesn't match the current tip of the branch the app is configured to track, or no finished deployment exists at all |

Cross-repo apps (e.g. `legal-workspace`, a different `git_repository` than this checkout) and
apps whose branch isn't fetched locally get the ref-dependent checks (`retired_watch_paths`,
`compose_location_exists`, `deployment_commit_drift`) marked `skipped` with the reason stated —
never silently passed and never fabricated. `commit_sha_immutability` and `watch_coverage` don't
need ref resolution and still run for every app regardless.

Output: a machine-readable JSON receipt (`--out FILE`, else stdout) with one entry per app —
`drift: bool` plus every check's `ok`/`severity`/`detail` — and a concise human summary on
stderr listing only the apps with actionable findings. Exit code `1` if any app has an actionable
finding, `0` if clean, `2` on a hard error (missing token, Coolify unreachable, bad fixture).

`--fixture FILE` loads a JSON `{"applications": [...], "deployments": {uuid: [...]}}` document
instead of calling the live API — this is what the test suite uses; `--no-git` disables all local
git resolution. `--apps NAME [NAME ...]` narrows to specific apps.

### `tests/test_check_deploy_drift.py` + `tests/fixtures/deploy_drift/sample.json`

18 tests, fixture/mock only — **no live Coolify call, no real `git` subprocess**. A `FakeResolver`
stand-in (matching `GitRefResolver`'s two-method shape) drives every check-logic test so results
never depend on this checkout's actual branch history changing over time. Coverage: each of the
five checks firing and *not* firing, `--no-git`, cross-repo skip behavior, unresolved-branch skip
behavior (proving "can't check" never becomes a false actionable or false clean), the `_covers`/
`_normalize_watch_paths` helpers, app-name filtering, summary rendering, and three end-to-end
`main()` invocations against the fixture file (drift → exit 1, clean subset → exit 0, `--out`
file write). All 18 pass; `ruff check`, `ruff format --check`, and `mypy` are clean on both new
files.

## Live drift findings (read-only probe, 2026-08-26, no Coolify mutation)

Ran `scripts/check_deploy_drift.py --out GAP-019-live-receipt-2026-08-26.json` against the real
27-app Coolify fleet (same instance NC-1 was written from). Full machine-readable output is
`docs/reviews/2026-08-25-schema-audit/GAP-019-live-receipt-2026-08-26.json`, generated in this
same change. Headline: **27 of 27 apps have at least one actionable finding.**

- **`commit_sha_immutability` fires on all 27 apps, no exceptions.** Every application's
  `git_commit_sha` field is the literal string `"HEAD"` — confirms the register's second finding
  is fleet-wide, not a sample.
- **`retired_watch_paths` fires on exactly 12 apps** — precisely matching NC-1's "at least a
  dozen" estimate, now enumerated exactly: `coolify-mcp`, `data-graphiti-case`,
  `data-graphiti-files`, `data-neo4j`, `data-pg-files`, `exec-contextforge`, `exec-desktop`,
  `exec-gateway`, `exec-platform-tools`, `exec-sandbox`, `exec-tier`, `portkey`. All 12 are on
  `main`, whose current tip has zero root-level `compose.*.yaml` files (verified via
  `git ls-tree`) — each of these apps' watch paths still names the pre-`106aacb` root file.
- **`watch_coverage` fires on 17 apps total.** 13 of those are "manifest not covered by any watch
  path" — the 12 `retired_watch_paths` apps above plus `temporal-worker` (its watch paths cover
  `docker/temporal-worker/**`/`server/**`/etc. but never its own `/docker-compose.yaml`). The
  remaining **4 have no watch paths configured at all**: `clone-of-nocodb-*`,
  `data-surreal-phase1-t0-r1`, `legal-workspace`, `nocodb`. Those four can never auto-redeploy on
  any push; none of the 17 were named individually in NC-1 (which estimated "at least a dozen"
  stale *names*, not this broader coverage gap).
- **`deployment_commit_drift` fires on 14 apps** — their last finished deployment's commit is
  behind the current tip of the branch they're configured to track. Two notable data points: (1)
  `data-pg-files`'s last finished deployment is dated 2026-08-12, from *before* the `106aacb`
  compose move — direct evidence that its stale watch path has suppressed every redeploy since,
  exactly the SG-7 failure mode; (2) `exec-tier` and `knowledge-workbench`, whose watch paths
  correctly include `server/**` / `workbench/**`, show **no** commit drift — they redeployed
  during this same session as `main`/`workbench/sprint` advanced, confirming the check doesn't
  over-fire on healthy apps.
- **`compose_location_exists` fires on 1 app**: `temporal-worker`'s manifest path
  (`/docker-compose.yaml`) does not exist at the tip of `main` — a stronger break than a stale
  watch path, since the configured deploy source itself is gone.
- **No false positives on branch-lag apps.** `librechat*`, `librechat-mongo*`, `nocodb-app`, and
  `data-weaviate-files` all reference root `compose.*.yaml` watch paths too, but their apps track
  long-lived feature branches (`infra/librechat`, `infra/nocodb`, `infra/data-weaviate-memgql`)
  that never merged the `106aacb` `deploy/` move — those root files **do** still exist at those
  branches' tips (confirmed via `git ls-tree` against each `origin/<branch>`), so
  `retired_watch_paths` correctly does not fire for them. This is a distinct condition (branch
  never rebased onto the deploy/ convention) from NC-1's "retired path" defect, and this packet
  does not label it actionable — flagging it here for whoever next reconciles those branches.
- `legal-workspace` (a different `git_repository`, `Cursedpotential/Legal-Workspace`) correctly
  shows every ref-dependent check as `skipped`, not fabricated.

## Static reasoning for correctness

- **No blind global rule.** The retired-path check only matches a *bare* root filename
  (`compose\.[A-Za-z0-9_.-]+\.yaml` or `docker-compose.yaml` with no `/`), so it cannot mistake a
  legitimate `deploy/**` glob or a source-tree path for a stale reference.
- **Skip is never silently treated as pass.** `CheckResult.severity` has three states
  (`actionable`/`info`/`skipped`); `drift` is computed only from `actionable` entries, and every
  `skipped` entry carries its reason in the JSON receipt, so a reviewer can tell "checked and
  clean" apart from "couldn't check" at a glance.
- **Self-consistency, not a hand-authored intent table.** Every check compares an app against
  facts derived from its *own* configured branch (via live git refs), not a separately maintained
  "should be" table this packet would have had to keep in sync with future renames — the
  documented failure mode this whole exercise is about.

## Limitations / explicitly out of scope for this packet

- **No branch-mismatch-vs-external-intent check.** The register's required-capability line names
  "branch mismatch" as a detection target. This packet detects *internal* inconsistency (an app
  vs. its own configured branch) exhaustively, but does not maintain a separate "app X should be
  on branch Y" table, because no durable, owner-approved source for that intent exists yet outside
  NC-1's snapshot table (which this packet was told not to treat as a live source of truth to
  avoid re-encoding drift). If an owner-approved intended-branch map is produced later, it can be
  passed to `check_app()`/`build_receipt()` as an additional optional check without changing the
  existing five — the function signatures were kept small and functional for exactly this reason.
- **`config_hash` is captured in the receipt but not diffed against anything.** The register's
  acceptance gate names "rendered config hash" explicitly; this packet surfaces the live value
  per app (see the JSON receipt) but has no second config-hash source to diff it against (Coolify
  does not expose a "hash Coolify computed at intended-config-time" separately from "hash of what
  it has now"). Recorded here as an open half of the acceptance gate rather than silently dropped.
- **Nothing was fixed.** Per task scope, this packet only detects and reports; watch paths,
  `docker_compose_location`, Coolify env, and deploy manifests were not touched. The 12 apps with
  retired watch paths, the 4 apps with zero watch-path coverage, and `temporal-worker`'s missing
  compose location all need a live Coolify write to correct — root's job, not this packet's.
- Branch-lag apps (`librechat*`, `nocodb*`, `data-weaviate-files`) are flagged above as a
  distinct, unresolved condition this packet does not attempt to fix or classify further.

## Required live verification handoff (for root / whoever corrects Coolify config)

1. Re-run `scripts/check_deploy_drift.py` (fresh `git fetch` first) after any watch-path/compose-
   location correction; the same 5 checks re-prove the fix without needing a new script.
2. For the 12 `retired_watch_paths` apps: add the actual `deploy/*.yaml` path to each app's watch
   paths (removing or keeping the retired name is root's call — removing it is cleaner, keeping it
   is harmless once the real path is also present).
3. For the 4 zero-watch-path apps: decide per-app whether auto-redeploy-on-push is wanted at all;
   if yes, set a watch path that covers the real manifest.
4. For `temporal-worker`: repoint `docker_compose_location` to wherever its manifest actually
   lives on `main` today (this packet did not investigate which file that should be — out of
   scope, no `deploy/**` edits permitted here).
5. `git_commit_sha` universally being `"HEAD"` is a Coolify application-level setting
   (pin-to-commit vs. track-branch-HEAD); deciding whether to pin, and to what, is an owner/root
   call this packet does not make.
6. Decide whether to reconcile or intentionally retire the branch-lag apps
   (`infra/librechat`, `infra/nocodb`, `infra/data-weaviate-memgql`) — they are currently running
   from branches dozens of commits behind `main`.

## Files changed

- `scripts/check_deploy_drift.py` — new.
- `tests/test_check_deploy_drift.py` — new.
- `tests/fixtures/deploy_drift/sample.json` — new.
- `docs/reviews/2026-08-25-schema-audit/GAP-019-live-receipt-2026-08-26.json` — new (live receipt
  generated by this packet's own tool, read-only against the real Coolify fleet).
- `docs/reviews/2026-08-25-schema-audit/GAP-019-IMPLEMENTATION-STATUS.md` — new (this file).

No other files were modified. No deploy manifest, Coolify resource, Coolify env var, canon/
decision/index doc, Workbench file, server code, SQL, Timesketch file, or existing shared script
was touched. No Coolify write call was made at any point (verified: `CoolifyClient` in
`scripts/check_deploy_drift.py` defines only `list_applications`/`list_deployments`, both `GET`).
