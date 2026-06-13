# CONVENTIONS — the one style

> **Authoritative for:** how we write code. Entry point: `docs/PROJECT_CANON.md` (§0).
> The *decision* behind the discipline is **ADR-0021**; this doc is the concrete *how*.
> Last updated: 2026-06-13. One language style, one tool contract, one data shape — no exceptions without an ADR.
> _Byline: Claude Code · Opus 4.8 · 2026-06-13_

## Artifact byline — provenance on EVERYTHING (required)

Every document and every code file we create or edit carries a **byline: `tool/platform · model · date`** —
because this is a multi-tool workflow (Claude Code, OpenCode, Codex, Gemini/Antigravity, human) and we
must know which agent on which model produced each artifact.

- **Markdown docs:** a line directly under the title block — `> _Byline: <tool> · <model> · <YYYY-MM-DD>_`.
  On a later substantive edit by a different tool/model, append lineage: `· updated <date> (<tool> · <model>)`.
- **Code files:** a top-of-file comment — `# Byline: <tool> · <model> · <YYYY-MM-DD>` (Python) /
  `// Byline: <tool> · <model> · <date>` (TS). Vendored/ported files ALSO keep a `provenance:` note
  pointing at the donor source (see the `@register(... provenance=...)` field).
- **Vocabulary:** `tool` ∈ {Claude Code, OpenCode, Codex, Gemini, Antigravity, human}; `model` = the
  actual model id in use (e.g. `Opus 4.8`, `gpt-5-codex`, `gemini-3-pro`, `glm-5.1`).

## Cross-tool compatibility (OpenCode / Codex / Gemini all consume this)

The SSOT is **plain markdown + the `AGENTS.md` standard** — deliberately tool-agnostic:
- **OpenCode** and **Codex** read `AGENTS.md` natively; **Claude Code** reads `CLAUDE.md` (symlink → `AGENTS.md`). Same front door for all three.
- Any other agent (Gemini/Antigravity, a custom Agno agent) is onboarded by pointing it at `docs/PROJECT_CANON.md` → which routes to the 5 authoritative docs. No Claude-specific syntax in the canon/plan/structure/inventory.
- Agno agents inside the platform consume the same docs via the knowledge engine (`platform_design` domain) once Phase B ingests them.
- **Rule:** keep the 5 authoritative docs free of tool-specific directives. Tool-specific setup (hooks, slash-commands) lives in that tool's own config, never in the SSOT.

## Working rules (apply to every change)

- **No silent stubs (ADR-0021).** Unavoidable stub → grep-able `# STUB: <tag>` in code **and** a row in `docs/DEBT.md`. `grep -rn "# STUB:"` must match the register exactly. Prefer *removing* an unfinished tool over shipping a silent `NotImplementedError`.
- **Harness-first tests.** `pytest` + `python -m evals` must run green; write paths (custody/HITL/normalize) aren't trusted until governance/boundary evals pass.
- **Verify Agno against the pinned wheel/image** via the agno skill + agno docs MCP — never from memory. (Current: agno **2.6.13**.)
- **HITL is first-class.** Every write (ingestion/normalize/evidence/config/db) pauses for recorded approval (native `@approval` + `requires_confirmation`; ADR-0002).
- **Owner-comms:** the owner does **not** code. Explain schemas/formats/functions in **plain English**, no code dumps, when discussing design.
- **One canonical data shape:** everything a tool emits normalizes to **`NormalizedRecord`** (`occurred_at` / `knowledge_time` / `disclosure_tier` / `attrs`). Don't invent parallel record types.

## The atomic-tool contract (the heart of the architecture)

Every tool — Python in-process or polyglot — satisfies one capability under the registry contract (`evidence/registry.py`):

```python
# evidence/tools/<format>.py — ONE capability per file, self-registering.
from __future__ import annotations
from evidence.registry import register

@register(
    id="transcripts.chatgpt-export",      # unique, dotted, stable (UI/tests depend on it)
    capability="parse.transcript",         # capability-based resolution; same capability = swappable
    description="ChatGPT official JSON export → NormalizedRecords",
    accept=lambda media_hint, size: media_hint.endswith(".json"),
    provenance="vendored: Agno-MCP-Platform-alpha/chatminer/parsers/chatgpt_official.py",
)
def run(payload: dict) -> dict:
    ...  # payload in → payload out
```

- **Capability resolution:** workflows resolve by `capability`, not function name. First registered = preferred; the rest are **substitution candidates** an agent can swap in on failure.
- **Auto-discovery:** `load_builtin_tools()` imports every non-`_` module in `evidence/tools/`. Underscore-prefixed modules = shared helpers, never tools.
- **Polyglot:** TS/Go/HTTP/MCP tools register with a runner (shell-out / HTTP) under the same contract — same `id`/`capability`/`accepts`/`run`, different transport.
- **Universal exposure — API-first + MCP-wrapped (canon §5):** EVERY tool, agent, AND workflow gets (1) an **internal API** (FastAPI/HTTP) for in-platform callers and (2) an **MCP wrapper over that API** for external/any-surface callers (federated by IBM ContextForge). Everything is **atomically callable**; tools also **compose into workflows** (which may hold a variable tool slot); workflows get the same API+MCP. **Everything gets an API; every API gets an MCP.**
- **Tool exposure pattern (owner, 2026-06-13):** heavy, long-running, or non-Python tools are wrapped as **FastAPI (or similar) HTTP services** — the existing `platform-tools` *tools-facade* pattern — then registered via the registry's HTTP runner and/or federated through **IBM ContextForge**. Lightweight Python tools stay in-process via `@register` but still expose the API+MCP per the universal rule. Either way the *contract* (capability + `NormalizedRecord`/payload I/O) is identical.

## Python style

- Target **3.11**; `from __future__ import annotations`; **type hints required**.
- **pydantic** for schemas/records (e.g. `NormalizedRecord`); `@dataclass` ok for simple value types.
- Formatting via `./scripts/format.sh` (ruff/black). `snake_case` modules and functions.
- **Lazy imports** for packages light consumers shouldn't pull (PEP 562 `__getattr__`, as in `evidence/__init__.py`) so the tools-facade container stays slim.
- Module starts with a purpose docstring (what it owns, what writes where).

## TypeScript style (donor tools wrapped as MCP services)

- Strict TS; **zod** for input schemas; tools expose MCP specs with `name` = `namespace.verb` (e.g. `evidence.hash_file`), a `description`, and an `inputSchema`.
- Keep the donor file header convention: `// File: <path> | Date: <d> | Agent: <who> | Model: <m>`.
- Don't port TS→Python wholesale; wrap behind Agno (REPO_STRUCTURE placement rules).

## SQL / migrations

- Numbered, append-only: `sql/NNNN_name.sql`. Never edit an applied migration — add a new one.
- `evidence` schema is read-only except via `custody.py`; derived data lands in `analysis`.

## Commit discipline

- A locked decision updates **`PROJECT_CANON.md` §5 in the same change** (anti-drift rule).
- New decisions also get an ADR (`docs/adr/`, supersede don't edit).
