# Rename follow-ups — agent prompt files

> _Byline: Claude Code · Fable 5.1 · 2026-09-06. One file per task; each is self-contained. Hand a file to a fresh agent as its first message._

| # | File | Who | Needs owner? |
|---|---|---|---|
| 01 | `01-finish-directory-rename.md` | any agent, after all sessions in the tree are closed | no (script prepared) |
| 02 | `02-restore-deny-list-and-gate.md` | owner or explicitly authorized agent | yes (owner's settings file) |
| 03 | `03-r2-dev-fixtures-copy.md` | any agent | yes (billable transfer sign-off) |
| 04 | `04-golden-clone-teardown.md` | the ingest session | yes before touching `platform` |
| 05 | `05-identifier-rulings-needed.md` | any agent, in conversation with the owner | yes (18 rulings) |
| 06 | `06-analysis-engine-split-indagatio.md` | planning agent | plan iterates until owner says done |
| 07 | `07-memory-tooling-repairs.md` | any agent | only for dropping collections |
| 08 | (no file yet) the **advocatio** repo (`modules/advocatio/`, its own commit root, `Cursedpotential/Legal-Workspace`) still calls itself Legal-Workspace and refers to `Agno-MCP-Platform` in its README, AGENTS.md, AGENT_MEMORY.md, pyproject, and docs; it needs its own naming sweep under D-138, with the same alias-vs-replace rule. Same for `modules/vestigia/` (traceIQ). | any agent, from inside that repo | product rename ruled; GitHub repo renames not ruled |

## Standing rules every file assumes (from AGENTS.md / CLAUDE.md)

- Never hard-delete; quarantine under the repo's holding directory (`.review_hold/`). Confirm before live-infra changes. Verify before claiming done: load the real thing, read the real log. Byline every artifact.
- Canon for names: `docs/NAMING.md` (D-137..D-142). Recall stores get the new name APPENDED beside the old; canon docs replace with strike-through.
- Zero committed live evidence exists (D-142): never design around protecting empty stocks; only `reference.*`, hand labels, the Case Bible catalog, and curated docs are precious.
- Persist results in the repo. `docs/registers/RENAME-LIVE-CHANGES-2026-09-06.md` is the live-change ledger: append, do not rewrite.
