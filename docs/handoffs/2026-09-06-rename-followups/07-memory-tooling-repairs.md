# Prompt: memory and recall tooling, what was fixed and what remains

> _Byline: Claude Code · Fable 5.1 · 2026-09-06. Agent-ready prompt file. Read `README.md` in this folder for the standing rules._

## State (2026-09-06)
- `~/.claude/skills/recall/recall_all.py`: the cnf source now searches both `.cnf` and `.claude` stores (it used to short-circuit on the first); memsearch searches the project collection named in `.memsearch/collection` (`ms_agno_mcp_platform_9e350219`); uv-tool subprocesses (`ccc`, `memsearch`) run with `VIRTUAL_ENV` and `PYTHONPATH` scrubbed, which fixes the `annotationlib` failure under `uv run`; timeouts raised (ccc 90s, memsearch 60s, smart-explore 60s).
- `ccc` works (`ccc status` healthy; a search takes about 48s while an index refresh runs).
- The smart-explore engine was re-extracted to `~/.agents/skills/smart-explore/` with its `.venv`. Its CLI takes the path positionally: `bash ~/.agents/skills/smart-explore/se index .` then `se search "<query>" --path . --max 3`. The index build for this repo was started 2026-09-06 12:14.
- Global `~/.memsearch/config.toml` still points `milvus.collection` at `agent_session_memory_nemotron3` (the global journal). Project journals are in `ms_agno_mcp_platform_9e350219`. Two stray collections from the 2026-09-03 crash remain (`…_nemotron3_d2048`, 3082 chunks; `agent_session_memory_nemotron3`, 506).

## Do
1. Run `python3 ~/.claude/skills/recall/recall_all.py "probata proffer"` from the repo. Every source must report `ok` or a precise reason. Fix any that do not.
2. Confirm `bash ~/.agents/skills/smart-explore/se search "ProfferWorkflow" --path . --max 3` returns hits, and that the recall source passes the query before `--path` (the CLI wants the query positionally).
3. Decide with the owner whether the global memsearch collection should be the project one. Do not drop the stray collections without the owner's yes.
