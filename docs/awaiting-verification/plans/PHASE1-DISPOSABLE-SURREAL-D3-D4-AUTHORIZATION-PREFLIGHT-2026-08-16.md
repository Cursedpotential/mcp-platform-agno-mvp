# Phase 1 — Disposable Surreal D3/D4 Authorization and Preflight

> _Byline: Codex · GPT-5 · 2026-08-16_
>
> **Status:** AUTHORIZED FOR THE NAMED T0 SLICE ONLY; PREFLIGHT PASSED; DEPLOYMENT PENDING.
> _Naming: written before the 2026-09-05 rename (D-137..D-141); see docs/NAMING.md for the old->new glossary._

## Answer first

The owner separately approved D3 target creation and D4 physical implementation/live testing on
2026-08-16 with: “Yes I approve get it done,” and added the requirement that the SurrealDB GUI be
incorporated into the workspace. This authorization applies only to
`data-surreal-phase1-t0-r1`, fabricated T0 inputs, the isolated runner, and the Workbench
SurrealDB Studio surface.

It does not authorize production corpus copy, PostgreSQL migrations `0026`–`0030`, the parked
legacy target, production Horizon activation, production-agent binding, Graphiti replacement,
or any E1–E5 adoption decision. Every surviving R9 activation hold remains active.

## D3 observed preflight

| Check | Observed result |
|---|---|
| Repository | `main == origin/main` at `1b0f7454676e7518a246d51f4274137e899c3b43` before implementation |
| Push custody | `origin` is `Cursedpotential/mcp-platform-agno-mvp`; lowcarbdev push is disabled |
| Host | `ovh-files` (`100.91.190.107`) exists and was reachable in Coolify inventory |
| Retired host | `ovh-data` is absent from the current Coolify fleet and was not contacted |
| Target absence | No application, service, or database named `data-surreal-phase1-t0-r1` existed |
| Image | SurrealDB `3.2.3`, Linux/amd64 manifest `sha256:e908d5d47f8dfacf955d5679487a06c75a4a8338f49e137582d4fd6ed63ddef2` |
| Image user | Registry config says `nonroot`; layer inspection resolves UID/GID `65532:65532` |
| Storage | New host path `/data/agno/experiments/phase1-surreal-t0-r1`; 2 GiB budget |
| Network | New internal-only `phase1-surreal-t0-r1`; no external/shared network and no published port |
| Namespace/database | New `phase1_surreal` / `t0_slice_r1` |
| Credentials | New random Coolify secrets only; values must never enter Git, reports, or transcripts |
| Stop behavior | Stop through Coolify with Docker cleanup disabled; preserve app, path, logs, and manifests |

The legacy compose authority, endpoint, volume, network, namespace/database aliases, and
credentials remain denylisted in code and tests. Any collision discovered during creation stops
the deployment.

## D4 reviewed artifacts

- `compose.surreal-phase1.yaml` defines the isolated server and one-shot runner only.
- `docker/surreal-phase1-runner/` owns Python 3.12, `surrealdb==2.0.0`, its independent lock,
  SCHEMAFULL SurrealQL, exact filtered-cosine query, synthetic manifest, and evaluation command.
- Root dependency files and `compose.data-surreal.yaml` remain unchanged.
- Workbench `/surreal` incorporates the current official SurrealDB Studio launcher and safe
  connection profile. It exposes no password, token, public endpoint, or authority claim.
- Failing-first coverage checks endpoint identity, horizon prefiltering, positive controls,
  terminal quarantine, linked rewalk semantics, schema safety, and GUI custody.

## Pre-creation gate evidence

- Isolated runner contract suite: **14 passed**.
- Phase-0 plus workspace Surreal tests: **20 passed**.
- SurrealQL schema validation: **PASS**.
- SurrealQL exact-retrieval query validation: **PASS**.
- Workbench production build, including `/surreal`: **PASS**.

These are local artifacts and maps until the target is created and the one-shot runner produces a
live report. `BUILD_STATUS` for live adapter behavior remains `UNKNOWN` until then.
