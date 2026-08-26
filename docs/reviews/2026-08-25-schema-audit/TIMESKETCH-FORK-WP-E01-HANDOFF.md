# WP-E01 handoff — Timesketch fork foundation

> Byline: Claude Code · Sonnet 5 · 2026-08-26 · ADR-0060, D-084/D-085 ·
> `TIMESKETCH-FORK-CURATION-HANDOFF.md` packet TS-02

## Status: WP-E01 complete — foundation and isolated live smoke verified

> Live-smoke amendment · Codex orchestration + Claude Code Sonnet 5 ·
> 2026-08-26. The Docker-only limitation recorded by the first pass was resolved
> through the established WSL/Podman path. The five-service stack was booted,
> verified, and torn down without wiring it to production or canonical data.

Owner-accepted decisions this session (explicit authorization to proceed without
re-confirmation on these six points):

1. New top-level `timesketch-fork/` sibling of `workbench/`.
2. Upstream release `20260630` pinned to commit `10dd077c6fe3b5e74fd9e28cd3ac1ef6c7c85849`.
3. Plain pinned source snapshot with `UPSTREAM.md` provenance, not a git subtree.
4. Disable-not-delete seams for DFIR-specific behavior.
5. Fixture/interface-only personal-case authority-state scaffolding.
6. Isolated `docker/timesketch` build and smoke tests; no shared compose or Coolify
   wiring unless a genuinely isolated existing target is discovered.

## Changed / added files

| Path | What |
|---|---|
| `dev-resources/upstream-resources/timesketch-upstream.git/` (workspace-root-relative, **outside** this repo, sibling of the existing `dev-resources/upstream-resources/agno-agent-platform/` donor copy) | New durable bare mirror of upstream, fetched at tag `20260630` only. Non-destructive; never deleted. 223M. |
| `Agno-MCP-Platform/timesketch-fork/` | New: clean tree export of the pinned commit, 1082 files, no `.git` (verified). |
| `Agno-MCP-Platform/timesketch-fork/UPSTREAM.md` | New: pin provenance, snapshot method, re-pin procedure, security/upstream-sync policy, local-modifications ledger. |
| `Agno-MCP-Platform/timesketch-fork/timesketch/lib/analyzers/__init__.py` | Modified (upstream file): DFIR analyzer registration gated behind `TIMESKETCH_FORK_ENABLE_UPSTREAM_ANALYZERS` (default off). No analyzer file deleted/renamed/edited. |
| `Agno-MCP-Platform/timesketch-fork/personal_case_authority/` (`__init__.py`, `authority.py`, `fixtures.py`, `README.md`) | New: isolated extension module, fixture/interface-only D-084/D-085 authority-state model + ADR-0060 canonical timeline mapping contract, `TimelineProjectionSource`/`CurationCommandSink` `Protocol` stubs for TS-03/TS-04. |
| `Agno-MCP-Platform/timesketch-fork/docker/dev/smoke-test.sh` | New: isolated build/boot/disable-seam verification script for the upstream `docker/dev` compose stack (unexecuted here — see Open item below). |
| `Agno-MCP-Platform/timesketch-fork/docker/dev/docker-compose.podman.yml` | New: Podman-specific isolated compose variant. It preserves the upstream service graph and changes only the host-port compatibility surface required by WSL/Podman. |
| `Agno-MCP-Platform/timesketch-fork/docker/dev/smoke-test-podman.sh` | New: repeatable WSL/Podman smoke harness with readiness polling, scoped teardown and authority/analyzer assertions. |
| `docs/reviews/2026-08-25-schema-audit/TIMESKETCH-DFIR-INVENTORY.md` | New: full census of DFIR-specific backend surface and disposition of each item. |
| `docs/reviews/2026-08-25-schema-audit/SEMANTIC-AGENT-WORK-PACKAGES.md` | Modified: WP-E01 status row and immediate-TODO checkbox updated to reflect this packet's actual state. |

## Tests executed (this session, this machine)

| Check | Result |
|---|---|
| `git ls-remote --tags` against live `google/timesketch` before pinning | Confirmed `refs/tags/20260630` == `10dd077c6fe3b5e74fd9e28cd3ac1ef6c7c85849` exactly — not taken on the owner's word alone |
| Bare mirror clone + `cat-file -t` + `log -1` on the pinned commit | Commit present, dated 2026-06-30, message "Update version to 20260630" |
| `git archive` export + `find timesketch-fork -maxdepth 1 -name ".git*"` | No `.git` directory in destination; only ordinary tracked `.github/`/`.gitignore` files |
| `ast.parse` on the edited `analyzers/__init__.py` | Parses cleanly |
| `yaml.safe_load` on all three upstream `docker/*/docker-compose.yml` files | All three valid YAML |
| `bash -n` + `ast.parse` on each embedded Python block in `smoke-test.sh` | Valid |
| Live Python import: `from personal_case_authority import fixtures`, construct and print all 3 fixtures | Ran successfully, printed all 3 authority states correctly (stdlib only, no dependency on Timesketch's own requirements) |
| `command -v docker` / `docker --version` on this desktop | Confirmed absent (exit 127) — matches the documented environment constraint, re-verified live rather than assumed from memory |
| WSL Podman + podman-compose 1.6.0 isolated stack | Five services created and started; Timesketch migrations and dev bootstrap completed; no production/Coolify wiring |
| Timesketch HTTP surface | HTTP 302 login redirect observed after gunicorn startup — expected unauthenticated response and proof the UI listener was reachable |
| OpenSearch from the running application stack | Cluster reported `green` |
| Analyzer disable seam, default | Zero upstream DFIR analyzers registered with `TIMESKETCH_FORK_ENABLE_UPSTREAM_ANALYZERS` unset/default-off |
| Analyzer disable seam, reversible | Enabling the flag restored the upstream analyzer registrations, proving disable-not-delete rather than removal |
| Scoped teardown audit | All five test containers, the `timesketch-network` network and smoke-created volumes removed; a final `podman ps -a`/network check returned no scoped remnants |

## Resolved item — isolated build/smoke proof

Native Windows still has no Docker CLI. The established WSL/Podman environment
provided the isolated runtime instead. Podman Compose required a standalone
compatibility compose file because list-merge behavior appended rather than
replaced host-port bindings, and the upstream development container required
explicit gunicorn startup after its readiness banner. Both behaviors are now
encoded in the Podman smoke harness rather than hidden in session-only commands.

The live run proved service bootstrap, migrations, UI reachability, OpenSearch
connectivity, default-off analyzer registration and reversible re-enablement.
The stack touched no production application, canonical PostgreSQL schema or
case data. Teardown was independently rechecked after the agent exited because
its final integrated rerun left the scoped stack mid-stop; the remaining
containers and network were then removed through the verified Compose project.

## Unresolved risks / compatibility notes

- `sigma_tagger.py` registers two classes both under `NAME = "sigma"`
  (`timesketch/lib/analyzers/sigma_tagger.py:16` and `:142`) — an upstream
  characteristic noticed while writing the smoke-test's registry-key assertions,
  not something this packet caused or needs to fix. Flagging in case a later
  packet's analyzer work touches this file.
- The disable seam is deliberately coarse (one flag disables all 24+ modules).
  `tagger` and `llm_log_analyzer` are architecturally generic and may be worth
  re-enabling individually before WP-E02 if their default config
  (`data/tags.yaml`, the default LLM prompt) is swapped for personal-case
  equivalents — noted in `TIMESKETCH-DFIR-INVENTORY.md`, not actioned here.
- No upstream files were deleted, renamed, or had their tests removed;
  `run_tests.py`, `test_requirements.txt`, and every `*_test.py` file are present
  unchanged in the snapshot, so upstream's own test suite is still runnable
  wherever Python + the pinned `requirements.txt` are installed (not attempted
  in this session — no verified Python environment with Timesketch's actual
  dependency set was built here; doing so would be part of the build-verify
  step above, not a separate action).

## Rollback

Everything added this session is net-new (no existing tracked file outside
`timesketch/lib/analyzers/__init__.py` was touched, and that edit is additive/
conditional, not destructive). To roll back entirely: remove
`Agno-MCP-Platform/timesketch-fork/` (move to `to_be_deleted/`, owner-only actual
deletion per repository policy) and leave the durable bare mirror at
`dev-resources/upstream-resources/timesketch-upstream.git/` in place (harmless,
reusable for a future attempt).

## Downstream acknowledgement

None yet — no downstream packet (TS-03/WP-E02) has started or acknowledged this
manifest. This file is the acknowledgement target for that packet.
