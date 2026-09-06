# Prompt: finish the directory renames (probata / vestigia / memory store)

> _Byline: Claude Code · Fable 5.1 · 2026-09-06. Agent-ready prompt file: paste the whole file to a fresh agent. Self-contained. Read `README.md` in this folder for the standing rules._

## Goal
Rename the checkout `E:\AI_Workspace\Projects\the-platform-workspace\Agno-MCP-Platform` → `probata`, nested `modules/traceIQ` → `modules/vestigia`, and the path-keyed Claude memory store `~/.claude/projects/E--AI-Workspace-Projects-the-platform-workspace-Agno-MCP-Platform` → `…-probata`, leaving JUNCTIONS at every old path (alias rule, D-142), aliasing the workspace routers, committing both repos with explicit allowlists, pushing, and re-indexing memsearch.

## Precondition
Windows refuses the rename while ANY process has the directory as cwd. Close every Claude/Codex session and terminal inside `the-platform-workspace` first. `modules/Legal-Workspace` → `modules/advocatio` is already done (junction at the old name).

## Do
1. From PowerShell at `C:\`, run the prepared script (read it first; it is idempotent):
   `& "C:\Users\matts\AppData\Local\Temp\claude\E--AI-Workspace-Projects-the-platform-workspace-Agno-MCP-Platform\4c3c2ef8-1973-446c-9239-6373b26eb455\scratchpad\finish_rename_dirs.ps1"`
   If the scratchpad is gone, recreate it from this description: `git rm --cached` the old gitlink → `Rename-Item` → `git add` the new path → `New-Item -ItemType Junction` old→new; the same for the memory dir; Python edits to `E:\AI_Workspace\AGENTS.md`, `AGENT_MEMORY.md`, `Projects\AGENTS.md`, `Projects\AGENT_MEMORY.md`, `Projects\REPOSITORY_BOUNDARIES.md`, `Projects\the-platform-workspace\AGENTS.md`, `AGENT_MEMORY.md`, and both `.gitignore`s (add `probata/`, the junction names, `modules/advocatio/`, `modules/vestigia/`). Router edits use the alias form: new name with "(formerly …)" beside it.
2. Verify: `git -C E:\AI_Workspace ls-files -s Projects/the-platform-workspace/probata` shows mode 160000; `Get-Item` on each old path shows `LinkType: Junction`; `memsearch search "proffer rename probata" -c ms_agno_mcp_platform_9e350219 -k 3` returns the 2026-09-05 naming entry.
3. Append the outcome to `docs/registers/RENAME-LIVE-CHANGES-2026-09-06.md` §8 (checkout directory row → DONE with timestamp).

## Do NOT
- Do not touch the parent index entry `Projects/traceIQ` (a gitlink whose directory is absent); it needs its own boundary decision.
- Do not rename the GitHub repos `Legal-Workspace` or `TraceIQ`. Product names only (D-138/D-140); repo renames are a separate decision.
