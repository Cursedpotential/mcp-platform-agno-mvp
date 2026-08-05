# DOC_DEBT — documentation backlog (circle-back register)

> _Byline: Claude Code · Opus 4.8 · 2026-06-13 (reconciliation instruction corrected 2026-07-11 Claude Code · Sonnet 5)_
> Backlog of undocumented code/config. Feeds the **living wiki (ADR-0022)**: every
> function/plugin/app/tool/3rd-party lib, **human-readable AND LLM-readable**.
> **Reconciliation (corrected 2026-07-11):** the original design called for grep-able `# DOC:` /
> `// DOC:` in-code markers mirrored here (`grep -rn "# DOC:" .` was supposed to match the open
> items below). That marker convention was **never adopted** — the grep returns zero hits in
> `server/` as of 2026-07-11. **This register is the source of truth on its own**; maintain the
> Open items list below by hand. Do not add `# DOC:` markers to code to make the old instruction
> true after the fact.

## How to use
1. Add a row under **Open items** with file + what's missing.
2. In a dedicated docs pass, write the doc (docstring + wiki entry), then check the row.

## Standing target (the eventual 100%)
- [ ] Every **function** — docstring + wiki entry
- [ ] Every **plugin / tool** — capability, I/O contract, provenance, example invocation
- [ ] Every **app / service** — purpose, API surface (+ OpenAPI), deploy, config, MCP exposure
- [ ] Every **3rd-party library** — why chosen, pinned version, gotchas (wiki "libraries" section)
- [ ] Consistency: one voice, one structure (CONVENTIONS), bylines on every doc

## Open items (seeded 2026-06-13)
- [ ] `server/vendored/chatminer/` vendored package — module overview + per-parser capability notes. **Partial coverage added 2026-07-11** (merged 2026-08-05): `docs/reference/parsers.md`'s `parsers/ai_chat` section documents, per chatminer-backed wrapper, the exact source-format grammar (from each vendored parser's own docstring) and the shared `ParsedMessage -> NormalizedRecord` mapping contract (`_chatminer_adapter.run_chatminer_parser` / `message_to_record`) that all 9 delegating wrappers rely on. Still open: a module-by-module overview of the **vendored package's own internals** — `core/base.py` / `core/types.py` / `core/pipeline.py` / `core/artifacts.py`, the `parsers/discovery.py` auto-detection mechanism, and the `segmenters/` + `skills/` subpackages. Only the wrapper-facing contract is documented.
- [ ] `server/evidence/schemas/*` (entity / relationship / event) — document the canonical model once created (HANDOFFS Track 0)
- [x] `server/tools/parsers/*` + `server/tools/extractors/*` atomic wrappers — capability + example per format (HANDOFFS HA.2). **Done 2026-07-11** (merged 2026-08-05): `docs/reference/parsers.md` — one section per module (23 total: messaging 9, ai_chat 11, generic 2, extractors 1), each with registered id / capability / accept rule, input grammar + snippet, output shape (RecordTypes, attrs, participants + `conversation_id` derivation, DisclosureTier), edge-case handling, provenance, and a runnable `registry.get(id).run({"path": ...})` example; plus the shared capability-resolution mesh and forensic-guarantee mechanics documented once at the top. Verified 1:1 against the live registry (`load_builtin_tools()` → 23 tools, no gaps).
- [ ] `server/evidence/config/case_terms*` — how segmentation case-tuning works (link example)
- [ ] ContextForge + SurrealDB integration — setup/config/exposure (after Phase C / D; ADR-0023/0024/0025)
- [ ] Part 3 AI Law Firm — persona inventory + each legal agent's API+MCP surface
