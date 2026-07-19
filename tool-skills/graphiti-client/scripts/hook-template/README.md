# Graphiti write-hook template (design only — NOT installed)

> _Byline: Claude Code · Sonnet · 2026-07-19_

This is a **template**, not a wired hook. It shows the pattern for any plugin (case-bible,
memsearch, etc.) to auto-write Graphiti episodes on tool use or session end, via `grc add` —
so plugins get durable knowledge-graph memory without hand-rolling the MCP dance. Per owner
instruction: **do not install these into any plugin's `hooks/` dir or `settings.json` yet** —
the owner wires this in per-plugin, deliberately, later.

## Why a hook and not "just call grc add manually"

Claude Code hooks (`PostToolUse`, `Stop`, etc.) run automatically on events — no agent turn spent
remembering to write the episode. The tradeoff is noise: a hook that fires on every tool call and
writes an episode for each one will flood the graph with chit-chat, violating the
"one focused episode per durable fact" write discipline. **Every hook installed from this template
needs a filter** deciding what's actually durable — this template ships permissive defaults and
expects the owner/plugin author to tighten them per use case.

## Two patterns included

### 1. `post-tool-use-episode.py` — capture on a specific tool

Fires on `PostToolUse`, matched to specific tools (e.g. `Write`, `Edit` for a docs plugin, or a
plugin's own custom tool). Reads the hook JSON payload from stdin, extracts `tool_name`,
`tool_input`, `tool_response`, and — **only if a simple heuristic says the change looks durable**
(see `_should_record()`) — shells out to `grc add`.

Example use: case-bible's `cb-sort-assist` could fire this after a `case-bible:cb-quarantine`
tool call to record "N files quarantined for reason X" as an episode, instead of every intermediate
file move.

### 2. `stop-episode-summary.py` — capture a session summary

Fires on `Stop` (end of an agent turn/session). Reads the transcript path from the hook payload,
optionally lets the plugin author supply a pre-written summary via an env var, and writes ONE
episode for the whole session — closer to how a human would journal it. Lower noise than
per-tool-call hooks; better fit for plugins whose "episode-worthy" unit is a whole task, not a
single tool call.

## Wiring pattern (for when the owner says go)

In the target plugin's `hooks/hooks.json` (or the relevant `settings.json` hooks block):

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "python \"${CLAUDE_PLUGIN_ROOT}/hooks/post-tool-use-episode.py\"",
            "timeout": 15
          }
        ]
      }
    ]
  }
}
```

Env vars the template scripts read (set these per-plugin, do not hardcode in the script):

| Var | Purpose | Example |
|---|---|---|
| `GRC_HOOK_GROUP` | Graphiti `group_id` for episodes this hook writes | `case-bible` |
| `GRC_HOOK_NAME_PREFIX` | Prefix for episode names, so they're identifiable by source | `cb-sort:` |
| `GRC_PATH` | Path to `grc.py` if not on PATH | `C:/Users/matts/.claude/skills/graphiti-client/scripts/grc.py` |

## Do / Don't for whoever wires this in later

**Do:**
- Start with the `Stop` pattern (lower noise, one episode per task) before reaching for
  `PostToolUse` (fires far more often).
- Write a plugin-specific `_should_record()` filter — the template's default is a permissive
  placeholder (length/keyword heuristic), not a real filter.
- Test with `grc doctor` + a throwaway `--group <plugin>-hook-test` before pointing at the real
  group_id.

**Don't:**
- Don't fire a hook on every single tool call without a filter — that's exactly the chit-chat
  problem the write-discipline rule exists to prevent.
- Don't block the tool-use/session-end path on Graphiti being reachable — these scripts must fail
  soft (log to stderr, exit 0) so a Graphiti outage never breaks the plugin's actual job.
- Don't add secrets/tokens into the hook command line — `grc` already reads them from
  `~/.secrets/contextforge.env` at call time.
