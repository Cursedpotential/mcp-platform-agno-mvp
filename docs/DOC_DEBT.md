# DOC_DEBT — documentation backlog (circle-back register)

> _Byline: Claude Code · Opus 4.8 · 2026-06-13_
> Mirror of grep-able `# DOC:` / `// DOC:` markers in code. **Flag now, write later** — don't block the
> build to document. Feeds the **living wiki (ADR-0022)**: every function/plugin/app/tool/3rd-party lib,
> **human-readable AND LLM-readable**. Reconcile: `grep -rn "# DOC:" .` must match the open items here.

## How to use
1. In code: `# DOC: <what's undocumented / why it matters>` (Python) · `// DOC: <what>` (TS).
2. Add a row under **Open items** with file + what's missing.
3. In a dedicated docs pass, write the doc (docstring + wiki entry), then clear the marker + check the row.

## Standing target (the eventual 100%)
- [ ] Every **function** — docstring + wiki entry
- [ ] Every **plugin / tool** — capability, I/O contract, provenance, example invocation
- [ ] Every **app / service** — purpose, API surface (+ OpenAPI), deploy, config, MCP exposure
- [ ] Every **3rd-party library** — why chosen, pinned version, gotchas (wiki "libraries" section)
- [ ] Consistency: one voice, one structure (CONVENTIONS), bylines on every doc

## Open items (seeded 2026-06-13)
- [ ] `chatminer/` vendored package — module overview + per-parser capability notes
- [ ] `evidence/schemas/*` (entity / relationship / event) — document the canonical model once created (HANDOFFS Track 0)
- [ ] `evidence/tools/*` atomic wrappers — capability + example per format (HANDOFFS HA.2)
- [ ] `evidence/config/case_terms*` — how segmentation case-tuning works (link example)
- [ ] ContextForge + SurrealDB integration — setup/config/exposure (after Phase C / D; ADR-0023/0024/0025)
- [ ] Part 3 AI Law Firm — persona inventory + each legal agent's API+MCP surface
