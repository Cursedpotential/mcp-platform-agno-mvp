# ADR-0016: Consolidated tool containers (platform-tools / sandbox / gateway) + Kasm desktop
- Status: Accepted
- Date: 2026-06-11

## Context
The owner wants as few containers as possible, plus an isolated code-execution space for agents,
plus an OpenCode gateway, plus a persistent desktop. Spinning a container per tool would sprawl
the 8 GB VPS.

## Decision
Three consolidated service images (under compose profile `tools`) plus a desktop:
- **`platform-tools`** — one image (supervisord) hosting SBV (GUI/REST) + a `tools-facade`
  (FastAPI :8090) that fronts the polyglot atomic tools (ADR-0017).
- **`agent-sandbox`** — isolated code-exec for agents: non-root, **no secrets, no published
  ports, no repo mounts**; agents reach `http://sandbox:8070/run` on the internal network only.
  Shares the `agent_workspace` volume with the desktop.
- **`gateway`** — LiteLLM (ADR-0015) + OpenCode in one image.
- **`desktop`** — Kasm browser desktop (`kasmweb/desktop`), persistent home (`kasm_profile`),
  profile `desktop` (opt-in due to RAM). Shares `agent_workspace` so the owner sees agent output.

## Consequences
- Stack stays at ~6–8 services. The sandbox's isolation is the security boundary for agent code.
- Kasm is RAM-heavy (~2 GB) → opt-in profile, brought up only when needed.
- The tools-facade is the single HTTP surface; atomic tools register into it (ADR-0017).

## Alternatives considered
- One container per tool — rejected: sprawl, RAM, ops overhead on a small VPS.
- Code-exec inside platform-tools — rejected: mixing untrusted exec with the tool API breaks isolation.
