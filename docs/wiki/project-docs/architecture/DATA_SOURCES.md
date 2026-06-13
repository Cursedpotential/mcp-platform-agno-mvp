# External Data Sources

This document tracks data sources outside the `dial-stack` and `MCP_Tool_Platform` directories that contain important context, application pieces, and assets for future integration.

---

## D: Drive — AI Workspace

**Path:** `D:\` (Windows)
**Status:** 🔒 Currently inaccessible — Windows Search Indexer holds a file lock on this drive even though the service is disabled. This is a known Windows bug and needs manual intervention.

### Known Contents (To Be Cataloged)

The D: drive contains an older version of the AI application workspace with:

- **Additional application modules** built in prior development cycles
- **Training data and custom NLP models** for entity extraction
- **Behavioral pattern definitions** (303+ patterns)
- **Evidence analysis scripts and tools** beyond what's in `Evidence_Analysis/`
- **Configuration files** from previous deployment attempts
- **Historical conversation data** and test fixtures

### Action Items

- [ ] Resolve D: drive access (kill `SearchIndexer.exe`, disable via Group Policy, or exclude D: from indexing)
- [ ] Once accessible, perform a full scan and catalog of all relevant files
- [ ] Identify modules suitable for wrapping as MCP tools
- [ ] Copy relevant assets into `dial-stack/` for integration
- [ ] Update `docs/wiki/architecture/TOOL_CATALOG.md` with newly discovered tools

### Workaround for Search Indexer Lock

If Windows Search Indexer keeps locking the D: drive despite being "disabled":

```powershell
# Option 1: Force-stop the service
Stop-Service WSearch -Force
Set-Service WSearch -StartupType Disabled

# Option 2: Remove the indexed location via Group Policy
# Run: gpedit.msc → Computer Configuration → Administrative Templates 
# → Windows Components → Search → "Prevent indexing certain paths"
# Add D:\ to the exclusion list

# Option 3: Nuclear option — unregister the search service entirely
sc delete WSearch
```

---

## C: Drive — TheBigOne Mono-Repo

**Path:** `C:\Users\matts\Projects\TheBigOne\`

### Directory Map

```
TheBigOne/
├── .agent.md              ← Global agent rules (READ-ONLY policy)
├── .claude.md             ← Claude-specific agent rules
├── .gemini.md             ← Gemini-specific agent rules
├── .cursorrules           ← Cursor-specific agent rules
│
├── MCP_Tool_Platform/     ← ARCHIVED, READ-ONLY legacy codebase
│   ├── .planning/         ← 51 planning docs, roadmaps, requirements
│   ├── archive/           ← 76 archived docs from prior iterations
│   ├── docs/              ← 43 spec files, ADRs, guides
│   ├── plans/             ← 6 architecture plans
│   ├── server/mcp/        ← Core TS codebase (parsers, storage, ingest)
│   ├── python-tools/      ← Python memory service
│   ├── Evidence_Analysis/ ← Python conflict analysis scripts
│   ├── cosmo/             ← WunderGraph GraphQL federation
│   └── CLAUDE.md          ← Legacy agent instructions (436 lines)
│
├── dial-stack/            ← NEW active application (this project)
│   ├── docs/              ← Planning, roadmap, specs, tool catalog
│   ├── infrastructure/core/              ← AI DIAL config
│   ├── infrastructure/settings/          ← DIAL settings
│   ├── mcp-servers/ts-mcp-server/     ← TypeScript MCP tools
│   ├── mcp-servers/py-mcp-server/     ← Python MCP tools (Semantica, LanceDB, Neo4j)
│   └── mcp-servers/js-mcp-server/     ← JavaScript MCP tools (Docling, Pandoc)
│
├── TraceIQ/               ← SEPARATE project (forensic evidence tracing)
└── Evidence_Analysis/     ← SEPARATE project (conflict analysis)
```

---

**Last Updated:** March 12, 2026
