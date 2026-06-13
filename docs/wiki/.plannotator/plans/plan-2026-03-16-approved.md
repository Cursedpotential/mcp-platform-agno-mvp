## Scope
- Continue dial-stack tasks without structural changes; only annotations/notes/audit coverage updates.
- Validate guidance in `CLAUDE.md` and any `AGENTS.md` under dial-stack before edits.
- Add IBM MCP gateway ("IBM context platform") deep dive and wiki entry using Morph + Context7.

## Step 1: Validate local guidance
- Read `C:\Users\matts\Projects\TheBigOne\dial-stack\CLAUDE.md` and any `AGENTS.md` files in the dial-stack tree.
- Adjust the plan if those files specify additional constraints or required update locations.

## Step 2: Expand audit coverage in py-mcp-server (no restructuring)
- Inventory tool entrypoints in `mcp-servers/py-mcp-server/src/tools/*.py`.
- Apply `@audit_tool` where missing, consistent with existing pattern in `dpk_tools.py`.
- Limit changes to annotations and minimal supporting notes.

## Step 3: SBV parser port plan (notes only)
- Inventory legacy SBV files in `MCP_Tool_Platform` and map dependencies.
- Draft a minimal port plan and interface contract without moving files.
- Record recommendations in `tools/TOOLS_REQUIRING_DISCUSSION.md`.

## Step 4: Smart Chunker + Conversation Extractor deep dive (notes only)
- Read AI_Workspace implementations and summarize inputs/outputs/dependencies.
- Update `tools/TOOLS_REQUIRING_DISCUSSION.md` with integration guidance.

## Step 5: IBM MCP gateway deep dive + wiki entry
- Use Context7 to pull authoritative documentation about the IBM context platform / MCP gateway implementation.
- Use Morph tooling to extract and summarize relevant implementation details.
- Write a new wiki page under `docs/wiki/` with the findings (tool purpose, APIs, required configs, integration points, risks).

## Step 6: Memory updates
- Update structured memory (`project-learnings`, `session-continuity`) with audit coverage status and IBM MCP gateway notes.

## Deliverables
- Audit annotations in py tool modules.
- SBV/Smart Chunker/Conversation Extractor integration notes in `tools/TOOLS_REQUIRING_DISCUSSION.md`.
- New IBM MCP gateway wiki page in `docs/wiki/`.
- Memory updates.

## Constraints
- No structural changes; annotations/notes/auditing only unless explicitly approved.