# HANDOFF — R7 Persistent OpenCode Workspace and Sandbox (2026-08-15)

> _Byline: Codex · GPT-5 · 2026-08-15_
STATUS: PARTIAL
BUILD_STATUS: UNKNOWN

## Verified-live state (do not re-derive)

| Thing | State |
|---|---|
| OpenCode server | Exposes authenticated OpenAPI, sessions, messages, agents, provider auth, files, commands, MCP, and SSE events |
| Existing platform | Workbench contains an OpenCode Copilot integration; repository also has a minimal isolated sandbox service |
| Hosting decision | Use existing self-hosted infrastructure; Vercel-hosted runtime/sandbox is not required |

## Findings / work done

- Use a persistent OpenCode control service for repos, configuration, provider authentication, caches, and sessions.
- Expose workspace lifecycle through a neutral `WorkspacePort`: create, start, stop, restart, fork, attach, inspect, export.
- Persistent control does not justify unrestricted host execution.
- Execute untrusted or agent-generated code in isolated child jobs with explicit snapshots, non-root identity, no secrets/evidence mounts, denied egress, and resource limits.

## UNRESOLVED (mandatory)

- Container/job backend and how it is exposed without a Docker socket.
- Persistence-volume layout, concurrent-workspace limits, and backup policy.
- Package-install policy and controlled egress exceptions.

## Pending owner decisions

- Adopt persistent-control/ephemeral-execution split — WHAT: keep workspace/session state while isolating each risky execution · WHY: persistence and safety are separate requirements · APPROACHES: one unrestricted hosted box, fully ephemeral sandboxes, or split design · SHORTCOMINGS: split design needs a broker. Recommendation: split.

## Next steps (work in order)

1. Inventory current Copilot and sandbox contracts.
2. Specify workspace/session/job records and API.
3. Deploy authenticated internal OpenCode service with persistent volumes.
4. Implement isolated job broker and output manifests.
5. Test restart persistence, cross-workspace isolation, secret absence, cancellation, and cleanup.
6. Integrate Workbench lifecycle and diffs.

## Owner working-style contract

- Never expose host shell, Docker socket, unrestricted external paths, or case data to a coding workspace without explicit scope.
