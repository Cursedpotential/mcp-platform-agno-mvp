# Nemotron review — Workbench/UIW direct-tailnet boundary

> _Byline: Codex · GPT-5 · 2026-08-29._
> _Naming: written before the 2026-09-05 rename (D-137..D-141); see docs/NAMING.md for the old->new glossary._

STATUS: REVIEWED

## Lane receipt

- Model: `nemotron-3-ultra:cloud` through the authenticated Ollama CLI.
- Scope: non-sensitive, read-only review of the settled Workbench-to-UIW
  authorization contract.
- Prompt boundary: no Basic auth, passwords, password environment variables, or
  Workbench/UIW bearer token; trust the direct TCP socket peer only when it is in
  `100.64.0.0/10`; ignore forwarded identity headers; strip caller Authorization;
  health may remain public.
- Raw output path: agent tool transcript for the 2026-08-29 session. No raw output
  was copied into the repository because the durable result below is sufficient.

## Root-reviewed result

The useful regression targets were:

1. accept in-range direct IPv4 peers and reject out-of-range peers;
2. prove forwarded identity headers cannot override the socket peer;
3. prove Workbench does not forward a caller Authorization header;
4. keep only the health endpoint public;
5. live-prove the real Docker/tailnet source address seen by the starter.

The model correctly noted that a `100.64.0.0/10` application check identifies a
tailnet node, not specifically the Workbench application. This is acceptable only
with the existing Tailscale ACL/grant layer restricting which node may reach port
8091. No new password or public exposure is proposed.
