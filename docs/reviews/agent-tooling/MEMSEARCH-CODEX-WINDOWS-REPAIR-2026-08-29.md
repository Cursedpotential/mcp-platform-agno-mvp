# Memsearch Codex and OpenCode Windows repair receipt — 2026-08-29

> _Byline: Codex · GPT-5.6-Sol · 2026-08-29._

STATUS: VERIFIED WITH EXTERNAL-HOOK BOUNDARY

## Scope

Repair and verify Memsearch capture, indexing, recall, Codex hooks, and the OpenCode startup
interaction for this checkout. This receipt concerns Memsearch's own memory system; it is separate
from Codex built-in memory.

## Findings and repairs

- Codex had the Claude Code marketplace flavor of Memsearch enabled. Its hook manifest used
  `${CLAUDE_PLUGIN_ROOT}`, Claude transcript parsing, and Claude-specific settings. That marketplace
  plugin is now disabled in `C:/Users/matts/.codex/config.toml`.
- A durable source checkout now exists at
  `C:/Users/matts/.codex/plugins/sources/memsearch`. The official Codex installer was not run because
  it contains `rm -rf`; its safe hook and skill installation steps were applied manually.
- Codex-specific Memsearch skills were installed additively under
  `C:/Users/matts/.agents/skills/{memory-recall,memory-config,memory-to-skill}`.
- `C:/Users/matts/.codex/hooks.json` now contains Codex-specific SessionStart,
  UserPromptSubmit, and Stop hooks routed through
  `C:/Users/matts/.codex/hooks/memsearch_codex_hook.ps1`. The reviewed commands were trusted through
  Codex's hook-review UI.
- The upstream Codex scripts' PID/work-file cleanup was changed from permanent deletion to moves
  under `<project>/to_be_deleted/memsearch-runtime`.
- The resolved embedding provider had regressed to local ONNX. It is now the remote OpenAI-compatible
  NVIDIA endpoint using `nvidia/nemotron-3-embed-1b`; the API key is referenced as
  `env:NVIDIA_NIM_API_KEY`, not stored inline.
- The OpenCode plugin was the process repeatedly rewriting the provider to ONNX: on Windows it used
  literal relative `~` when `HOME` was absent. Its active cached source and the durable Memsearch
  source checkout now fall back through `USERPROFILE` and `os.homedir()`.
- The historical collection `ms_agno_mcp_platform_9e350219` is 4,096-dimensional while the current
  remote embedding is 2,048-dimensional. It was preserved. `.memsearch/.collection` pins the active
  replacement `ms_agno_mcp_platform_9e350219_nemotron3_d2048`.
- Codex native summarization now requests catalog-valid `gpt-5.6-luna` instead of unsupported
  `gpt-5.1-codex-mini`.

## Verification

- `memsearch` version: `0.4.19`; latest GitHub release checked on 2026-08-29: `v0.4.19`.
- Full force index into the replacement collection completed: `Indexed 3035 chunks`.
- `.memsearch/.index-state.json` finished with `status=ok`, the replacement collection, no
  `last_error`, and zero failed files.
- Collection stats after the concurrent watch/index reconciliation reported 4,998 indexed chunks.
- Semantic search against the replacement collection returned live results from project memory.
- The Codex Stop hook created the 2026-08-29 11:06 journal entry, quarantined its detached-worker
  payload, indexed the entry, and an exact semantic query returned it as the top result.
- `opencode debug startup` completed after the Windows-home patch and the provider remained
  `openai`; it no longer reverted to ONNX.
- A fresh non-interactive Codex probe showed two SessionStart hooks and two UserPromptSubmit hooks
  completing. Other installed, non-Memsearch hooks still produced failures and require their own
  hook-system audit; they are outside this Memsearch repair proof.

## Security and restart boundary

An embedding credential was previously stored inline and was printed by an early resolved-config
diagnostic. The config no longer stores it inline. Rotate `NVIDIA_NIM_API_KEY` if that credential is
still active. A newly launched Codex process is required to inherit the user-level environment and
load the repaired hooks; fresh child-process verification was completed, but the already-running
parent session retains its original startup environment.

## Update durability

The Codex integration uses the durable source checkout. An OpenCode npm cache refresh can overwrite
its active cache-local Windows-home patch; the same patch is preserved in the durable source checkout
for reconciliation until it is released upstream or OpenCode is pointed directly at that checkout.
