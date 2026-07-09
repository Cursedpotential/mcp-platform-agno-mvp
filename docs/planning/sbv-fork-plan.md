# SBV forensic fork — plan & status

> _Byline: Claude Code · Opus 4.8 · 2026-07-09_
>
> **Reconciliation note:** the authoritative `sbv-fork-plan.md` (with the full
> Phase 0-5 findings) was NOT present on this feature branch's base
> (`main` @ e2086c2); it lives on a parallel branch. This file was created by the
> `feature/sbv-forensic-fork` implementation to record the phase statuses the
> brief asked for. The main agent should reconcile it with the fuller plan.

## Scope

Forensic fork of SBV (Go SMS-XML viewer/parser) into the platform monorepo, with
raw-bytes H1/H2/H3 chain-of-custody hashing that our Python custody gate
cross-checks and records. **Phases 1-4 only** — Phase 5a (native Go automation
endpoints) is DEFERRED, not built. DB-target = FUNCTIONAL: SBV never gets DB
credentials; `custody.py` / `sbv_sms.py` are the only DB writers.

## Phase status

| Phase | Description | Status |
|---|---|---|
| **1** | Vendor the fork at `vendored/sbv/` via `git subtree` (`--squash`) + `UPSTREAM.md` | **DONE** |
| **2** | Build-from-source `docker/tools/Dockerfile` (reproduce upstream node→go→alpine stages); bump `platform-tools` build context to repo root in both compose files; bake `server/` into the facade image (drop the broken bind mount) | **DONE** (deploy-verify) |
| **3** | H1/H2/H3 hashing in the Go fork matching the custody schema; hooks in `parser.go` / `database.go`; `GET /api/hashes/{importID}`; `content_hash` in payloads; Go unit tests | **DONE** (go unavailable locally → CI/deploy-verified) |
| **4** | Python custody integration: consume SBV H1/H2/H3, cross-check H1 → `verified`/`integrity_violation`, emit H2/H3 evidence rows; pytest | **DONE** |
| **5a** | Native Go automation endpoints | **DEFERRED (out of scope)** |

## Key artifacts

- `vendored/sbv/UPSTREAM.md` — provenance + `git subtree pull` update recipe.
- `vendored/sbv/CUSTODY.md` — byte-level H1/H2/H3 canonicalization spec.
- `vendored/sbv/internal/custody.go` (+ `custody_test.go`) — hashing core + tests.
- `docker/tools/Dockerfile`, `compose.yaml`, `compose.exec.yaml`, `.dockerignore`
  — build-from-source + repo-root context + baked `server/`.
- `server/evidence/custody.py` — `reconcile_sbv_import` + `record_custody_event`
  / `record_evidence_hash`.
- `server/evidence/tools/{sbv_sms.py,_sbv_client.py}` — H2 fold-in, `hashes()`
  client method, opt-in `_reconcile_custody`.
- `tests/test_sbv_custody.py` — verified vs integrity_violation coverage.

## Gates

- Python: `ruff format` + `ruff check` + `mypy` clean; `pytest` **191 passed**
  (was 186; +5 new).
- Go: `go` is not installed on the build host → `go test ./...` is **CI/deploy-
  verified only** (tests written, not run locally).
- Docker build-from-source: **deploy-verify only** (no local docker).
