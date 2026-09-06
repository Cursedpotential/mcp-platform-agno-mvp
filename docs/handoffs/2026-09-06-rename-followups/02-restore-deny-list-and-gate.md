# Prompt: restore the permission deny list after the named build

> _Byline: Claude Code · Fable 5.1 · 2026-09-06. Agent-ready prompt file. Read `README.md` in this folder for the standing rules._

## Goal
The owner lifted `Edit/Write` denies on `deploy/**`, `modules/**`, `server/**`, `compose.yaml`, `**/AGENTS.md`, `**/AGENT_MEMORY.md` in `.claude/settings.local.json` for the named build "probata/proffer rename" (2026-09-06). The build is live-verified. Restore the full deny list and record the restore.

## Do
1. Read `.claude/settings.local.json` → `permissions.deny`. Restore exactly (keep whatever is already there):
   `Edit(**/AGENTS.md)`, `Edit(**/AGENT_MEMORY.md)`, `Edit(AGENTS.md)`, `Edit(compose.yaml)`, `Edit(deploy/**)`, `Edit(modules/**)`, `Edit(pyproject.toml)`, `Edit(requirements.txt)`, `Edit(server/**)`, `Edit(sql/**)`, `Write(**/AGENTS.md)`, `Write(AGENTS.md)`, `Write(deploy/**)`, `Write(modules/**)`, `Write(server/**)`, `Write(sql/**)`.
2. Under `_build_lift`, add `"restored": "<timestamp> after the probata/proffer rename build landed (commits d7e8f81..606d586, live-verified 2026-09-06 10:29 EDT)"`.
3. This file is the owner's. Only the owner or an explicitly authorized agent edits it. Do not push it (it is local).
4. Run `uv run python scripts/check_naming.py`. It must print `0 hit(s)`. It is also a CI step now.
