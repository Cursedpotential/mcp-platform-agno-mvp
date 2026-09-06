# Prompt: copy the dev fixtures to the proffer prefix in R2 (dry-run first)

> _Byline: Claude Code · Fable 5.1 · 2026-09-06. Agent-ready prompt file. Read `README.md` in this folder for the standing rules._

## Goal
Code expects dev fixtures at `r2://nexus/proffer/test-fixtures/…` (`modules/engine/runtimeapi` `devFixturePrefix`, dev-bypass only). The objects sit at `nexus/uiw/test-fixtures/`. Copy them server-side inside the bucket; keep the old prefix until the copy is verified.

## Do
1. Config: the rclone remote for the `nexus` bucket (see `~/.secrets/INDEX.md` for the remote name; never print keys).
2. DRY-RUN and state count and size: `rclone copy remote:nexus/uiw/test-fixtures remote:nexus/proffer/test-fixtures --dry-run -v`.
3. Get owner sign-off (every transfer is billable; Class-A ops cost money). Then run without `--dry-run`, then `rclone check` both prefixes.
4. Record in `docs/registers/RENAME-LIVE-CHANGES-2026-09-06.md` §7 → DONE with counts. Do not delete the old prefix; that is the owner's call.
