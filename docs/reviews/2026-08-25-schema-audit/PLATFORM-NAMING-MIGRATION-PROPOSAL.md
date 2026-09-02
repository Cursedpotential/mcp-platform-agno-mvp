# Platform naming migration proposal


> _Recovery note: this file was lost (never committed) after being authored in a Codex CLI session on 2026-08-26/27. Reconstructed 2026-09-02 by Claude Code · Sonnet (recovery lane C) from the session's own `apply_patch` tool-call history in `C:\Users\matts\.codex\sessions\2026\08\`, per the method in `RECOVERY-NOTE.md`. All accepted `apply_patch` hunks touching this file located and applied cleanly; full recovery, high confidence._

> Status: owner-approved canonical scheme · 2026-08-26
>
> Owner direction: retire Agno/AgentOS naming because the product and runtime
> are moving away from Agno. Do not perform a blind textual replacement.

> **2026-08-27 owner addendum (D-091):** the database/role scheme is now fixed. The fresh
> application database is `platform`; migration/admin is `platform_admin`; runtime is
> `platform_runtime`; domain capability roles remain specific (for example,
> `context_import_writer`). Existing database `ai` and role `agno_app` remain untouched legacy/source
> resources through preservation review. This is a fresh database, not an in-place rename. Migration
> 0036 is held and must never be applied to `ai`.

Owner confirmation: **The Platform** is the human-facing umbrella and
`platform-*` is the canonical owned technical naming family. This approval
activates N00/N01 census work; runtime cutover remains gated by the semantic
packets and compatibility rules below.

## Recommended canonical scheme

| Scope | Canonical name/pattern |
|---|---|
| Human-facing umbrella | **The Platform** |
| Technical/service prefix | `platform` |
| Core API | `platform-api` |
| Operator application | `platform-workbench` |
| Domain services/workers | `platform-<domain>` |
| Owned environment variables | `PLATFORM_*` |
| Fresh application database | `platform` |
| Migration/admin identity | `platform_admin` |
| Runtime identity | `platform_runtime` |
| Domain roles | capability-specific, for example `context_import_writer` |
| Existing Agno/AgentOS-owned identifiers | `legacy`; temporary compatibility alias only |

The recommendation reuses the workspace's existing umbrella vocabulary, does
not lock the product to one legal workflow, and gives every owned deployment a
predictable technical prefix. No replacement public DNS name is proposed here.

## Scrub rules

1. Replace only names owned by this project. Keep `agno` where it identifies an
   actual third-party package, import, API contract or historical fact until the
   corresponding dependency is removed.
2. Preserve append-only ADR and decision history. Add supersession notes rather
   than rewriting what an old deployment was called.
3. Inventory and migrate service names, DNS, Coolify resources, branch/watch
   paths, environment variables, API clients, CORS/auth configuration, metrics,
   dashboards, runbooks and operator shortcuts as one receipt-backed program.
4. Provide compatibility aliases during rollout; remove them only after caller
   census, live tests and rollback proof show zero legacy consumers.
5. Treat framework removal separately from branding. Renaming `agentos-api` does
   not prove that Agno runtime imports or AgentOS contracts are gone.
6. Do not invent a new branded product name during the mechanical scrub.

## Proposed semantic packets

- **N00 — Registry freeze:** owner confirms the canonical matrix and exceptions.
- **N01 — Census:** exact owned names versus third-party/historical references.
- **N02 — Code/config aliases:** clients, env, routes and telemetry dual-name phase.
- **N03 — Deployment migration:** Coolify resources, branches, watch paths and DNS.
- **N04 — Documentation/operator surfaces:** current docs, runbooks and shortcuts.
- **N05 — Agno framework retirement:** replace actual imports/runtime contracts by
  capability domain; this is not a string-renaming packet.
- **N06 — Cutover:** live caller census, alias removal, rollback and reconciliation.

## Stop gate

The canonical scheme is confirmed. One agent now owns the registry/census;
implementation agents receive non-overlapping semantic packets and exact
file/resource scopes. Runtime aliases may be removed only after caller census,
live verification and rollback proof.