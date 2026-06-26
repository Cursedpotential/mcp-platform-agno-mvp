# evidence/ — Progressive Disclosure Map

> The evidence spine: custody → parse → normalize → store → export.
> This is Part 1 of the three-part arc.

## Directory Map

```
evidence/
  __init__.py          <- Lazy PEP 562 exports (lightweight imports for tools-facade).
  custody.py           <- SHA-256 entry gate; sole writer of the `evidence` schema.
  registry.py          <- Atomic-tool registry (capability-based resolution).
  normalize.py         <- NormalizedRecord — the one canonical shape (bitemporal).
  store.py             <- Persist records → `analysis` schema + knowledge engine.
  workflows.py         <- Named workflows on native agno.workflow (custody-gated).
  cli.py               <- `python -m evidence import|tools|workflows|verify`.
  __main__.py          <- CLI entry point.
  tools/               <- Atomic parser modules (one per format).
    __init__.py        <- Auto-discovery docstring.
    _common.py         <- Shared helpers (underscore = NOT a tool).
    chatgpt_export.py  <- ChatGPT data-export conversations.json parser.
    claude_ai_export.py   <- claude.ai data-export parser.
    claude_code_jsonl.py  <- Claude Code session .jsonl parser.
    markdown_transcript.py <- Plain .md/.txt fallback parser (whole-file record).
  config/
    case_terms.example.yaml <- Case-specific segmentation terms template.
```

## Custody Guarantee

- `custody.py` is the **only** writer of the `evidence` schema.
- Evidence records are immutable: append-only, hashed, write-once blobs on R2.
- Agent DB connections use the readonly engine — they physically cannot write.

## NormalizedRecord — The One Shape

Every parser emits `NormalizedRecord` with:
- `occurred_at` — valid time (when the thing happened)
- `knowledge_time` — when the platform learned it
- `disclosure_tier` — contemporaneous | hindsight | discovered

## Adding a New Parser

1. Create `evidence/tools/<format>.py`.
2. Use `@register(id=..., capability="parse.transcript", ...)` decorator.
3. Implement `parse(payload: dict) -> dict` — returns `{"records": [...], "stats": {...}}`.
4. `load_builtin_tools()` auto-discovers it.
