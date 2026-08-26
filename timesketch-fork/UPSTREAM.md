# Upstream provenance — google/timesketch

> Byline: Claude Code · Sonnet 5 · 2026-08-26 (WP-E01, ADR-0060, D-084/D-085)

## Pin

| Field | Value |
|---|---|
| Upstream repository | `https://github.com/google/timesketch` |
| Pinned tag | `20260630` |
| Pinned commit | `10dd077c6fe3b5e74fd9e28cd3ac1ef6c7c85849` |
| Commit date | 2026-06-30 (upstream "Update version to 20260630") |
| Pinned by | owner directive, this session, 2026-08-26 |
| Verification | `git ls-remote --tags` against the live upstream repo confirmed `refs/tags/20260630` resolves to exactly this commit before pinning (not taken on trust) |
| License | Apache License 2.0 (`LICENSE`, unmodified, copyright notices preserved) |

## How this snapshot was produced

This directory is a **plain pinned source snapshot**, not a git subtree and not a
live clone — per owner constraint, no removable `.git` directory may exist inside
this destination.

1. A durable bare mirror of upstream was created (fetch of the `20260630` tag only)
   at `dev-resources/upstream-resources/timesketch-upstream.git` (workspace-root-relative,
   sibling of `Agno-MCP-Platform/` — same convention as the existing
   `dev-resources/upstream-resources/agno-agent-platform/` read-only donor copy).
   That bare repo is the durable, non-destructive local reference for the pin: it
   is what a future re-pin or upstream diff/rebase check reads from, and it is never
   deleted (`.claude`/global "never delete" policy — the owner removes it if it is
   ever no longer wanted).
2. `git --git-dir=<bare-mirror> archive --format=tar 10dd077c6fe3b5e74fd9e28cd3ac1ef6c7c85849`
   piped into `tar -x` at this directory. This is a clean tree export of exactly
   that commit — no `.git`, no history, no working-tree metadata reaches
   `timesketch-fork/`.
3. Verified after export: no `.git*` entries at the top level of `timesketch-fork/`
   other than the upstream repo's own tracked `.github/` and `.gitignore` files
   (which are ordinary tracked content, not a VCS directory).

To re-pin to a newer upstream release later: fetch the new tag into the bare
mirror (`git --git-dir=<bare-mirror> fetch origin tag <new-tag>`), diff the two
commits' trees against this directory to see what upstream changed, then re-run
step 2 against the new commit — reconciling this fork's local edits (currently:
the disable-not-delete seam in `timesketch/lib/analyzers/__init__.py`, see
below) by hand, since there is no subtree/rebase machinery to do it
automatically. That reconciliation-by-hand tradeoff is the accepted cost of a
plain snapshot instead of a subtree, per the owner's explicit decision this
session.

## Security/upstream-sync policy

- **Cadence:** upstream tags roughly every 4-8 weeks (see the tag list fetched
  2026-08-26: `20260119` → `20260630`, ten releases in ~5.5 months). Check
  `git ls-remote --tags https://github.com/google/timesketch.git` periodically
  (no fixed automated cadence exists yet — this is a manual-check policy until a
  later packet wires monitoring).
  A newer tag does not by itself require re-pinning — the trigger is a specific
  disclosed CVE/security advisory affecting a dependency or upstream code path
  this fork actually exercises, or a deliberate feature pull.
- **Dependency surface:** `requirements.txt` (53 lines) and
  `test_requirements.txt` (10 lines) are upstream's own pins, carried unchanged
  in this snapshot. This fork inherits upstream's dependency-update cadence;
  no local dependency pins have been added or changed by WP-E01.
- **Disclosed-vulnerability response:** on notice of a CVE affecting an
  in-scope dependency or upstream code path, re-pin to the earliest upstream
  tag that contains the fix (not necessarily the latest tag), following the
  re-pin procedure above, and record the CVE/tag/date in this file's changelog
  section.
- **Local modifications are isolated, not scattered:** every local change to
  upstream files is tracked below so a re-pin's manual reconciliation has a
  fixed, small checklist rather than a diff against the entire tree.

## Local modifications to upstream files (disable-not-delete seam)

| File | Change | Reason |
|---|---|---|
| `timesketch/lib/analyzers/__init__.py` | Wrapped the upstream DFIR/security analyzer registration imports (all 24 named modules + `authentication`/`contrib`/`dfiq_plugins` subpackages) behind `TIMESKETCH_FORK_ENABLE_UPSTREAM_ANALYZERS` (env var, default off). No analyzer file was deleted, renamed, or edited — the `manager.py`/`interface.py` registration framework is untouched, and every disabled module still imports and runs correctly if the flag is set to `1`. | ADR-0060 requires DFIR-specific analyzers "replaced or disabled ... through isolated extension modules ... so upstream merges remain tractable," and the repository-wide deletion policy forbids removing the files outright. Gating the single import list is the smallest possible diff against upstream, which is what keeps a future `git diff` against a new tag's tree tractable. |

No other upstream files have local modifications as of this pin. See
`docs/reviews/2026-08-25-schema-audit/TIMESKETCH-DFIR-INVENTORY.md` for the full
list of what that gate disables and why each item is DFIR-specific.

## What is deliberately NOT done in this packet (WP-E01 scope)

Per `SEMANTIC-AGENT-WORK-PACKAGES.md` and the TS-00..TS-08 handoff table, WP-E01
is fork *foundation* only. Explicitly out of scope here, reserved for later
packets:

- No PG projector/importer wiring (TS-03 / WP-E02).
- No curation API, no round-trip editing (TS-04 / WP-F01/F02).
- No UI vocabulary relabeling (sketch→case, etc.) (TS-05 / WP-F03).
- No shared platform compose or Coolify wiring — this fork's `docker/dev`,
  `docker/e2e`, `docker/release` compose files are upstream's own, fully
  self-contained (own `timesketch-network`, own Postgres/OpenSearch/Redis,
  ports bound to `127.0.0.1` only), and are not referenced by the platform's
  root `deploy/compose.yaml` or any Coolify app.
- No production deployment (TS-08 / WP-H02).
