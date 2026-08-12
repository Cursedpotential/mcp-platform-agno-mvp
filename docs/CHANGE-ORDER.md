# CHANGE-ORDER — Agno-MCP-Platform

> _Byline: Claude Code · Fable 5 · 2026-08-12_
> Running, append-only ledger of executed changes (newest on top). Per the workspace
> memory contract: append the same turn as any executed change. Complements
> `DECISION_LOG.md` (the why) — this is the what/where/verified. Strike; never delete.

---

## 2026-08-12

### CH-3 — `require_tracked_code` PreToolUse hook: `.py` extension false-positive fixed
- **What:** In `~/.claude/local-plugins/plugins/case-bible/hooks/require_tracked_code.py`,
  the `EXEC_TEMP` interpreter alternation `\b(?:python3?|py|bash|sh|node|pwsh|powershell)\b`
  matched the `py` in `.py` **file extensions** (`\b` matched because the preceding `.` is a
  non-word char). Any `.py` filename was treated as the `py` interpreter, so any later `/tmp/`
  path in the same command string false-blocked legitimate staging (e.g.
  `docker cp /tmp/x.py c:/app/y.py` paired with `ssh @100.`/`docker exec`).
- **Fix:** replaced the leading `\b` with `(?<![\w.])` — a negative lookbehind rejecting
  word-char and dot prefixes — so extensions cannot pose as interpreters. Real invocations
  (`python x.py`, `bash run.sh`, `py script.py`) still match.
- **Verified:** `scripts/_test_hook_regex_tmp.py` — blocked staging now ALLOWs; real
  `python /tmp/script.py` still BLOCKs; output-redirect INTO temp still ALLOWs.
- **Why now:** the false block was preventing the live Task-3 ops (hot-patch + wipe +
  re-ingest). Owner: "Fix that hook or that file or whatever the fuck is stopping."

### CH-2 — ADR-0045 OQ-8 / D-042 amended (AI-chat context lane reverses auto-assert hindsight)
- **What:** `docs/adr/0045-horizon-clocks-and-checkpoint-derivation.md` — struck the OQ-8
  clause ("the AI-chat context lane auto-asserts `hindsight` tier at write") with a dated
  2026-08-12 correction: the context lane asserts NO tier; the horizon is a query-level
  distinction derived from clocks + HITL realization events. `docs/DECISION_LOG.md` D-056
  appended (newest-on-top).
- **Scope:** context lane only; ADR-0045 Decision C (normalized_record keeps
  `disclosure_tier` as an asserted hint) unchanged.

### CH-1 — `working.context_record` drops `disclosure_tier` (context lane = just normalized data)
- **What:** `sql/0023_drop_context_record_disclosure_tier.sql` (idempotent `DROP COLUMN`,
  applied live 2026-08-12). `server/analysis/context_chat_ingest.py` (the ONLY reader/writer
  of `context_record`) hot-patched: INSERT and `load_pending_context` SELECT no longer
  reference the column.
- **Live ops (VPS, container agentos-api-…-194330527059):** column DROPPED → confirmed
  absent in `information_schema` → 1617 `source='claude-ai-export'` test rows wiped
  (124 other-source rows untouched) → re-ingested `data-2025-12-08-batch-0001.zip` with the
  hot-patched code → **1617 rows back, `disclosure_tier` column absent** (an INSERT
  referencing a dropped column would have errored, so the patch is provably live).
- **Open / deferred (separate, not this change):** R2 nexus blob upload still `dry_run`
  (assets_materialized.uploaded=0); companion files (users.json/projects.json/memories.json)
  not yet folded into context rows; baseline `sql/bootstrap/schema_baseline.sql` still does
  NOT contain `context_record` (0021/0022/0023 applied live but baseline never regenerated —
  pg_dump --schema-only regen is the follow-up).