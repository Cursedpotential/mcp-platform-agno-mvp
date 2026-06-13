# ADR-0009: Build and run on the OVH Debian VPS; author locally and sync over SSH
- Status: Accepted
- Date: 2026-06-01

## Context
The Windows host can't run the stack (Python 3.14, no Agno, Docker not the target runtime). The owner
provisioned an OVH Debian VPS (`40.160.5.19`, `d2-8-us-east-va-1`) and said "use that VPS." Probe: Debian
6.1, **Docker 29.4.3 + Compose v5.1.3**, 4 vCPU, 50 GB disk (46 GB free), no containers — a clean Docker host.

## Decision
The VPS is the **build + run + deploy host** for the containerized stack (postgres PG18, agno-app, n8n,
MCP servers, R2 volume). Development model: **author code locally in `agno-mvp/`, sync to the VPS, build
and run with `docker compose` on the VPS over SSH.** All "verify inside the image" / Definition-of-Done
checks run on the VPS, not the Windows host. The agent drives the VPS non-interactively via
`ssh -i <key> debian@40.160.5.19` (key auth confirmed working); privileged steps use `sudo -S`.

## Consequences
- No host venv; the Python-3.14/no-Agno problem is moot.
- Need a sync mechanism (tar-over-ssh or rsync or git) local → VPS; keep `.env`/secrets on the VPS only,
  never committed.
- Credentials (SSH key, sudo password) are owner-provided for this box; handle carefully, never log/commit them.
- Resource ceiling: 4 vCPU / ~8 GB / 50 GB — fine for MVP; watch image sizes and Postgres volume.

## Alternatives considered
- Build on the Windows host — rejected (wrong runtime, no Docker target, version mismatch).
- Author directly on the VPS over SSH heredocs — rejected (slow, error-prone; local edit tools are richer).
