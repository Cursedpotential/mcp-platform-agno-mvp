# Codex Claude Octopus hook repair — 2026-08-29

> _Byline: Codex · GPT-5 · 2026-08-29_

STATUS: VERIFIED LOCALLY — restart Codex once more to prove the full-plugin disable in a new session.

## Owner intent

Keep explicit, owner-requested delegation to external CLIs, especially Antigravity (`agy`) and
OpenCode, while preventing Claude Octopus hooks or routing from triggering unrequested provider
work or generating repeated hook failures.

## Changes

- Initially kept `claude-octopus@nyldn-plugins` enabled and disabled its 18 recognized hook-state
  entries. A fresh-session transcript proved that this was insufficient: Codex continued running
  additional plugin events that had no persisted per-hook state.
- Corrective action: set the entire `claude-octopus@nyldn-plugins` plugin to `enabled = false`.
  Direct `agy` and OpenCode delegation remains available through their installed CLIs and dedicated
  user skills; it does not depend on the Octopus plugin.
- Set `OCTOPUS_AUTO_ROUTER_MODE = "off"` in Codex's shell environment policy.
- Set `enabled = false` on all 18 Claude Octopus hook-state entries recognized by Codex:
  session start/end, user-prompt submit, post-tool, pre/post-compact, and subagent-stop hooks.
- Did not edit the plugin cache manifest. Cache-local changes would be overwritten by an update.
- Did not disable unrelated hooks or plugins.

## Failure audit

The current Codex log database contained 12 recent hook-runtime failures, all attributed to the
legacy `notify` callback rather than Claude Octopus: 11 Windows error 206 failures (command line
too long) and one Windows error 3 failure (path not found). The legacy callback is already absent
from the active configuration; a Codex restart is required to clear any copy loaded by an
already-running process.

Claude Octopus shipped a large Claude-oriented hook manifest and Codex had trusted 18 compatible
entries without an explicit disabled state. Those 18 entries are explicitly disabled, but the
fresh-session transcript still showed four failed SessionStart hooks, two failed
UserPromptSubmit hooks, repeated failed/timed-out PreToolUse hooks, and three failed PostToolUse
hooks. Their event counts and timing matched the Octopus manifest. Full plugin disable is therefore
the enforced boundary.

## Verification

- `codex --version`: `codex-cli 0.149.1`.
- `codex features list`: passed, establishing that the edited TOML parses successfully.
- Configuration inspection after correction: plugin enabled = false; auto-router off = true;
  Octopus hook states = 18; explicitly disabled = 18.
- `agy --version`: `1.1.22` from the WinGet link.
- `agy models`: live catalog returned successfully. This was a catalog/auth reachability probe,
  not a model inference request.
- Octopus installation: 63 skill entrypoints; 31 mention Antigravity/AGY; orchestrator and hook
  manifest both present.
- `C:\Program Files\Git\bin\bash.exe -n ...\scripts\orchestrate.sh`: PASS.
- `HKCU:\Environment\NVIDIA_NIM_API_KEY`: present. The value was not printed. A running process
  that predates the Registry update will not inherit it until restart.
- Explicit Antigravity allocation: `agy` with `gemini-3.7-flash-low`, plan+sandbox mode, returned
  exactly `AGY_ALLOCATION_OK`.
- Explicit OpenCode allocation: separate OpenCode processes in an isolated temporary directory,
  read-only `plan` agent, model `opencode/nemotron-3.5-lightning-free`, returned exactly
  `OPENCODE_ALLOCATION_OK`. During Windows argument/stdout diagnosis two free-seat probes completed;
  OpenCode recorded cost `$0` for both, but each loaded approximately 75k–77k input tokens for the
  tiny prompt. Direct delegation works, but its global context loading is inefficient and should be
  reduced before routine micro-task delegation.
- OpenCode control result: `ollama-cloud/glm-5.3-flash` reached the provider but failed with HTTP
  429 because the Ollama Cloud session usage limit was exhausted. The CLI's normal terminal output
  hid the provider error; the error was verified in OpenCode's session database.

## Manual operating contract

After restarting Codex, explicit requests such as “delegate this to Antigravity” or “delegate this
to OpenCode” invoke the installed CLIs through their dedicated user skills. Ordinary prompts, tool
calls, compaction, subagent completion, and session lifecycle events must not invoke Octopus.

The two explicit allocation probes were owner-requested. OpenCode reported `$0` for its successful
free-seat probe.

## Follow-up proof

Start one fresh Codex session and confirm:

1. no Octopus session-start hook runs;
2. no legacy `notify` error is logged after a short and a long turn;
3. no Octopus PreToolUse or PostToolUse hooks appear around a harmless command.

If Octopus is ever re-enabled, first replace or remove its automatic hook manifest for Codex rather
than relying on per-hook state alone.
