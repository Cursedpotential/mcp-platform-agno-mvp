# Wiki Archive

This directory preserves stale, superseded, or legacy documentation in a mirrored layout so older context stays easy to locate inside the main wiki tree.

## Archive Rules

1. Mirror the active `docs/` structure when archiving files.
2. Prefer moving stale material into the matching relative path under `docs/wiki/archive/`.
3. Do not flatten unrelated documents into one dump directory.
4. Keep canonical current-truth docs outside this archive.
5. When a file is archived because it was replaced, the active doc should point to the newer canonical location when helpful.
6. Keep the archive inside the wiki root so Obsidian and LLM context tooling can still discover historical material.

## Examples

- `docs/wiki/architecture/ARCHITECTURE.md`
  archives to
  `docs/wiki/archive/wiki/architecture/ARCHITECTURE.md`
- `docs/plans/ROADMAP.md`
  archives to
  `docs/wiki/archive/plans/ROADMAP.md`
- `docs/.planning/codebase/CONCERNS_LEGACY.md`
  archives to
  `docs/wiki/archive/.planning/codebase/CONCERNS_LEGACY.md`

## Current Purpose

This tree now holds relocated stale and superseded docs in mirrored paths so historical context remains discoverable without polluting the active wiki.
