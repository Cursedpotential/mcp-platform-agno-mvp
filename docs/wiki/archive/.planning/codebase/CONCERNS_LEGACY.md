# Codebase Concerns

**Analysis Date:** 2026-02-25

---

## Security Concerns

### [CRITICAL] Hardcoded Google API Keys in GCP Plugins

- Risk: Live Google Cloud API keys are hardcoded directly in source files. The key `AIzaSyCmEDGGPNYFRKj4gnmJudWsJfQBQmeE-N8` (and a variant) appears in 5 files. These keys could be committed to git history and exploited for unauthorized GCP usage.
- Files:
  - `MCP_Tool_Platform/MCP_Tool_Platform_Repo/server/mcp/plugins-pending/gcp-document-ai.ts` (line 24)
  - `MCP_Tool_Platform/MCP_Tool_Platform_Repo/server/mcp/plugins-pending/gcp-vision.ts` (line 6)
  - `MCP_Tool_Platform/MCP_Tool_Platform_Repo/server/mcp/plugins-pending/gcp-natural-language.ts` (line 4)
  - `MCP_Tool_Platform/MCP_Tool_Platform_Repo/server/mcp/plugins-pending/gcp-speech.ts` (line 10)
  - `MCP_Tool_Platform/MCP_Tool_Platform_Repo/server/mcp/plugins-pending/gcp-video-intelligence.ts` (line 8)
- Current mitigation: These files are in `plugins-pending/` (not actively loaded), but they exist in the codebase.
- Fix approach: Remove hardcoded keys immediately. Replace with `process.env.GOOGLE_API_KEY`. Rotate the exposed key in GCP console. Add a pre-commit hook or secret scanner (e.g., `gitleaks`) to prevent future leaks.

### [CRITICAL] Hardcoded Service Account Credentials Template in gcp-document-ai.ts

- Risk: `gcp-document-ai.ts` contains a service account email pattern and a private key placeholder structure at lines 28-32. While the private key value is a placeholder, the structural pattern invites developers to paste real credentials directly into source code.
- Files: `MCP_Tool_Platform/MCP_Tool_Platform_Repo/server/mcp/plugins-pending/gcp-document-ai.ts` (lines 26-33)
- Fix approach: Replace with `GoogleAuth` default credential loading from environment or a JSON keyfile path via env var.

### [HIGH] Placeholder Secrets in Committed .env File

- Risk: The `.env` file is committed to the repository with placeholder secrets that look like real configuration. `DATABASE_URL=mysql://root:password@localhost:3306/salem` (line 5), `ENCRYPTION_KEY=placeholder-key-replace-me-with-openssl-rand-hex-32` (line 22), `JWT_SECRET=placeholder-jwt-secret-replace-me` (line 23). While `.gitignore` lists `.env`, the file currently exists in the repo.
- Files:
  - `MCP_Tool_Platform/MCP_Tool_Platform_Repo/.env` (72 lines)
  - `_project_dirs_loose/.env.production` (126 lines — template with placeholder values, less risky)
- Current mitigation: `.gitignore` includes `.env`, but if the file was committed before the gitignore rule, it persists in history.
- Fix approach: Verify `.env` is not tracked with `git ls-files .env`. If tracked, remove from tracking with `git rm --cached .env`. Ensure only `.env.example` and `.env.docker.example` are committed.

### [HIGH] .env Files in Junkyard/Archive Directories

- Risk: Multiple `.env` files exist inside archive/junkyard directories that may contain real credentials.
- Files:
  - `TraceIQ/Junkyard/Source_B_BigOne_Repo/Timeline-Takeout-Ingestor/backend/.env`
  - `TraceIQ/Junkyard/Source_A_Root_Folder/location-admin/.env`
  - `TraceIQ/Junkyard/Source_B_BigOne_Repo/location-admin/.env`
  - `TraceIQ/Junkyard/Timeline_Tools_Backup_20260108_214802/location-admin/.env`
  - `MCP_Tool_Platform/MCP_Tool_Platform_Repo/The_Platform_Archive/TheBigOne_SAFE_COPY/01_Timeline_Forensics/location-admin/.env`
  - `TraceIQ/Junkyard/Source_A_Root_Folder/20260106033151884/Timeline Tools/TL (copy 1)/.gemini/.env`
- Fix approach: Audit each `.env` for real secrets. Remove all `.env` files from archive directories. Add `**/.env` to root `.gitignore`.

### [HIGH] MCP Gateway Endpoints Are Unauthenticated

- Risk: 13 of the MCP gateway's tRPC procedures use `publicProcedure` (no auth required), including `searchTools`, `describeTool`, `listTools`, `listCategories`, `getToolsByCategory`, `getRelatedTools`, `listWorkflows`, `getWorkflow`, `semanticRoute`, `getStats`, `getRef`, and `recommendTools`. Only `invokeTool` uses `protectedProcedure`. This means anyone can discover and enumerate all tools, workflows, and system stats without authentication.
- Files:
  - `MCP_Tool_Platform/MCP_Tool_Platform_Repo/server/mcp/gateway.ts` (lines 210-1265)
  - `MCP_Tool_Platform/MCP_Tool_Platform_Repo/server/core/trpc.ts` (defines `publicProcedure` vs `protectedProcedure`)
- Fix approach: Change read-only gateway procedures to `protectedProcedure` at minimum. Consider a `readOnlyProcedure` middleware that requires a valid session but not admin role.

### [HIGH] No Security Middleware (Helmet, CORS restrictions, CSRF, Rate Limiting)

- Risk: The Express server at `server/core/index.ts` has no `helmet()` for security headers, no CORS configuration (any origin allowed by default), no CSRF protection, and no rate limiting middleware. The only body-size limit is 50MB (line 35-36), which is extremely generous and could enable DoS.
- Files:
  - `MCP_Tool_Platform/MCP_Tool_Platform_Repo/server/core/index.ts` (lines 31-66)
  - `TraceIQ/TraceIQ_Main/app.py` (line 27: `CORS(app)` — wide-open CORS)
- Current mitigation: None detected. Rate limiting is discussed in types (`server/mcp/llm/smart-router.ts`, `server/mcp/config/config-manager.ts`) but never enforced at the HTTP layer.
- Fix approach: Add `helmet()`, configure CORS with explicit allowed origins, add `express-rate-limit`, reduce body size limit to 10MB for non-upload routes.

### [MEDIUM] ENV Fallback to Empty Strings Silently Fails

- Risk: `server/core/env.ts` falls back to empty strings for all environment variables (e.g., `cookieSecret: process.env.JWT_SECRET ?? ""`). If `JWT_SECRET` is not set, the app starts with an empty JWT secret, which means session tokens are signed with an empty string — trivially forgeable.
- Files: `MCP_Tool_Platform/MCP_Tool_Platform_Repo/server/core/env.ts` (lines 1-10)
- Fix approach: Validate required env vars at startup and throw if missing. Use a library like `envalid` or add manual checks in `startServer()`.

---

## Tech Debt

### [HIGH] Massive Archive/Junkyard Bloat — 4.7GB Total Project

- Issue: The project is 4.7GB total. `TraceIQ/Junkyard/` alone is 3.7GB and `MCP_Tool_Platform/MCP_Tool_Platform_Repo/The_Platform_Archive/` is 967MB. Together these archives consume 4.67GB — 99% of the project size. They contain multiple duplicated copies of the same code (Source_A, Source_B, Timeline_Tools_Backup, TheBigOne_SAFE_COPY, etc.).
- Files:
  - `TraceIQ/Junkyard/` (3.7GB) — Contains `Source_A_Root_Folder/`, `Source_B_BigOne_Repo/`, `Timeline_Tools_Backup_20260108_214802/`, `Source_C_Tools/`, `timeline-analysis/`
  - `MCP_Tool_Platform/MCP_Tool_Platform_Repo/The_Platform_Archive/` (967MB) — Contains `TheBigOne_SAFE_COPY/`, `MCP_BACKUP/`, `voice_app_react_legacy/`
- Impact: Slows git operations, confuses code search results, makes grep/find noisy, wastes disk space.
- Fix approach: Archive to a separate backup location (external drive or cloud). Remove from the active codebase. If git-tracked, move to a separate archival branch or repo.

### [HIGH] Duplicate Files at TraceIQ Root Level

- Issue: Several Python scripts exist as identical copies at both `TraceIQ/` root and `TraceIQ/TraceIQ_Main/`. The `diff` command shows zero differences.
- Files:
  - `TraceIQ/validate_timeline_data.py` = duplicate of `TraceIQ/TraceIQ_Main/validate_timeline_data.py`
  - `TraceIQ/overnight_analyzer.py` = duplicate of `TraceIQ/TraceIQ_Main/overnight_analyzer.py`
  - `TraceIQ/utils_io.py` = duplicate of `TraceIQ/TraceIQ_Main/utils_io.py`
  - `TraceIQ/schedule_analyzer.py` = duplicate of `TraceIQ/TraceIQ_Main/schedule_analyzer.py`
  - `TraceIQ/logging_config.py` = duplicate of `TraceIQ/TraceIQ_Main/logging_config.py`
  - `TraceIQ/fix_json_manually.py` = duplicate of `TraceIQ/TraceIQ_Main/fix_json_manually.py`
  - `TraceIQ/fix_place_cache.py` = duplicate of `TraceIQ/TraceIQ_Main/fix_place_cache.py`
  - `TraceIQ/test_db_connection.py` = duplicate of `TraceIQ/TraceIQ_Main/test_db_connection.py`
  - `TraceIQ/create_geocoding_database.py` and `TraceIQ/create_geocoding_database_1.py` — appear to be variants
- Impact: Confusing which file is canonical. Edits to one copy are silently lost when the other is used.
- Fix approach: Delete the root-level duplicates. Keep only the copies inside `TraceIQ/TraceIQ_Main/`.

### [HIGH] Pattern Analyzer Stuck in "Temporary Development Mode"

- Issue: `pattern-analyzer.ts` has a prominent banner (lines 12-23) stating it uses SQL.js for local development and that Drizzle ORM imports are commented out. The file imports from `drizzle/schema` (line 26) but then comments out drizzle-orm at line 29. This means the 1,659-line file is operating in a degraded mode that was intended to be temporary.
- Files: `MCP_Tool_Platform/MCP_Tool_Platform_Repo/server/mcp/forensics/pattern-analyzer.ts` (lines 12-29)
- Impact: Pattern analysis doesn't use the production database. Data isn't persisted properly.
- Fix approach: Follow the migration steps in the file comments: uncomment Drizzle imports, switch `server/core/db.ts` back to Drizzle version, test against MySQL/PostgreSQL.

### [HIGH] PatternLibrary.tsx — 21 TODOs, Entirely Stub UI

- Issue: The entire PatternLibrary page (354 lines) is a non-functional stub. All data fetching, mutations, and event handlers are commented out with TODO markers. The page renders UI elements that do nothing. A user clicking "Create Pattern" sees `toast("TODO: Implement pattern creation")`.
- Files: `MCP_Tool_Platform/MCP_Tool_Platform_Repo/client/src/pages/PatternLibrary.tsx` (21 TODO comments, lines 50-351)
- Impact: Core feature is completely non-functional despite having a full backend implementation.
- Fix approach: Wire the existing `trpc.patterns.*` endpoints to the UI components as documented in `TODO.md`.

### [HIGH] GraphConfigSettings.tsx — Backend Not Implemented

- Issue: The entire graph configuration settings component is a stub. All tRPC calls are commented out. The "Save" button simulates a save with `setTimeout` and shows a toast saying "backend not yet implemented."
- Files: `MCP_Tool_Platform/MCP_Tool_Platform_Repo/client/src/components/GraphConfigSettings.tsx` (161 lines, lines 10-47)
- Impact: Graph configuration cannot be saved or loaded. Users see a working-looking UI that does nothing.
- Fix approach: Implement `settings.getGraphConfig` and `settings.updateGraphConfig` tRPC endpoints, then uncomment the client-side calls.

### [MEDIUM] PatternApprovalWorkflow Hardcoded User ID

- Issue: The approval workflow uses `actorId: 'current-user'` as a hardcoded placeholder instead of reading from auth context.
- Files: `MCP_Tool_Platform/MCP_Tool_Platform_Repo/client/src/components/PatternApprovalWorkflow.tsx` (line 200)
- Fix approach: Read `actorId` from the tRPC auth context or a user store.

### [MEDIUM] 5 GCP Plugins in "Pending" State with Wrong Import Paths

- Issue: Five GCP plugin files in `plugins-pending/` import from non-existent modules like `@mcp/core` and `@mcap/core`. They also use a raw Express `app.post()` pattern instead of the project's tRPC/plugin registry system.
- Files:
  - `server/mcp/plugins-pending/gcp-document-ai.ts` (imports from `@mcp/core`)
  - `server/mcp/plugins-pending/gcp-natural-language.ts`
  - `server/mcp/plugins-pending/gcp-speech.ts` (imports from `@mcap/core`)
  - `server/mcp/plugins-pending/gcp-video-intelligence.ts`
  - `server/mcp/plugins-pending/gcp-vision.ts`
- Impact: These files cannot compile. They represent a stalled integration effort.
- Fix approach: Rewrite to use the project's plugin registry pattern (`getPluginRegistry().registerTool()`), move API keys to env vars, or delete if not needed.

### [MEDIUM] `copy-of-timeline-explorer-pro (1)/` — Accidental Copy

- Issue: An apparent duplicate of `timeline-explorer-pro/` with a space and `(1)` in the directory name, characteristic of a file manager copy operation.
- Files: `TraceIQ/copy-of-timeline-explorer-pro (1)/` (147KB)
- Impact: Confusing; unclear which is canonical.
- Fix approach: Verify contents match `timeline-explorer-pro/` and delete.

### [MEDIUM] `@google/genai: "latest"` in Chronicle Voice App

- Issue: The Chronicle Voice App pins `@google/genai` to `"latest"`, which means every install gets whatever version is current. This is a reproducibility and breaking-change risk.
- Files: `Voice_Analysis/Chronicle_Voice_App/package.json` (line 14)
- Fix approach: Pin to a specific version (e.g., `"^1.0.0"`).

---

## Missing Error Handling

### [HIGH] Bare `except:` Clauses Throughout TraceIQ Python Code

- Issue: Extensive use of bare `except:` (no exception type) and `except Exception:` with `pass` throughout the TraceIQ Python codebase. This silently swallows all errors including `KeyboardInterrupt`, `SystemExit`, and `MemoryError`. Found 29+ instances in active code, 251+ across the full TraceIQ tree (including Junkyard).
- Files (active code only):
  - `TraceIQ/TraceIQ_Main/validate_timeline_data.py` (line 60)
  - `TraceIQ/TraceIQ_Main/overnight_analyzer.py` (line 20)
  - `TraceIQ/TraceIQ_Main/quick_audit.py` (lines 9, 58, 64)
  - `TraceIQ/TraceIQ_Main/precision.py` (lines 26, 52)
  - `TraceIQ/TraceIQ_Main/import_cache_batches.py` (lines 29, 45, 49, 54, 72)
  - `TraceIQ/TraceIQ_Main/utils_io.py` (lines 28, 34, 113, 125)
  - `TraceIQ/TraceIQ_Main/src/analytics/geocode_resolver_v4.py` (lines 16, 21, 49, 78)
- Impact: Errors in timeline forensic processing are silently lost. Data corruption or missing records go undetected. This is especially dangerous for a forensic tool where data integrity is paramount.
- Fix approach: Replace bare `except:` with specific exception types. At minimum, log the exception before continuing. For forensic data, consider failing loudly rather than silently.

### [HIGH] Bare `except:` in ConflictAnalysisApp

- Issue: Same pattern in the Evidence Analysis sub-project. 14 instances of bare/overly-broad exception handling.
- Files:
  - `Evidence_Analysis/ConflictAnalysisApp/src/parsers.py` (lines 18, 29, 134, 174, 192, 249)
  - `Evidence_Analysis/ConflictAnalysisApp/src/message_analyzer.py` (lines 15, 18)
  - `Evidence_Analysis/ConflictAnalysisApp/src/sms_backup_parser.py` (line 56)
  - `Evidence_Analysis/ConflictAnalysisApp/src/taggers.py` (line 23)
  - `Evidence_Analysis/ConflictAnalysisApp/src/app.py` (lines 57, 86, 102, 226)
- Impact: Evidence parsing failures are hidden. Parsed data may be incomplete without any indication.
- Fix approach: Add specific exception types and logging.

### [MEDIUM] 474 console.log/error/warn Calls Instead of Structured Logging (MCP Platform Server)

- Issue: The MCP Platform server uses `console.log`, `console.error`, and `console.warn` throughout (474+ instances). There is no structured logging framework (winston, pino, etc.). Log messages use inconsistent prefix formats like `[ChromaManager]`, `[GraphitiClient]`, `[PostgreSQL]`.
- Files: Throughout `MCP_Tool_Platform/MCP_Tool_Platform_Repo/server/` — every module.
- Impact: No log levels, no JSON output for log aggregation, no way to filter/search logs in production, no request tracing.
- Fix approach: Adopt a structured logging library (pino recommended for Node.js). Create a logger factory that auto-prefixes module names. Replace console calls.

---

## Test Coverage Gaps

### [HIGH] 13% Test-to-Source File Ratio (MCP Platform)

- What's not tested: Only 18 test files exist for 138 source files in `server/` (13% ratio). No client-side tests exist at all (0 test files for 40+ client components/pages).
- Files:
  - Test files present: `server/core/db.test.ts`, `server/mcp/forensics/chain-custody.test.ts`, `server/mcp/forensics/hurtlex-stream.test.ts`, `server/mcp/forensics/pattern-analyzer.test.ts`, `server/mcp/forensics/timeline-generator.test.ts`, `server/mcp/gateway.test.ts`, `server/mcp/gateway.agent.test.ts`, `server/mcp/loaders/document-loaders.test.ts`, `server/mcp/orchestration/langchain-memory.test.ts`, `server/mcp/orchestration/langgraph.test.ts`, `server/mcp/plugins/schema-resolver.test.ts`, `server/mcp/store/content-store.test.ts`, `server/mcp/workers/executor.test.ts`, `server/tests/auth.logout.test.ts`, `server/tests/database-connections.test.ts`, `server/tests/routers/settings.test.ts`, `server/tests/storage/chroma-client.test.ts`, `server/tests/storage/graphiti-client.test.ts`
  - No tests for: API router (`server/api/index.ts` — 1,269 lines), plugin registry (`server/mcp/plugins/registry.ts` — 2,198 lines), LLM provider hub (`server/mcp/llm/provider-hub.ts` — 1,725 lines), evidence linker, NLP, format converter, approval system, graph analytics, config manager, all tRPC routers except settings, all client pages/components
- Risk: Regressions in core gateway, API routing, and plugin execution go undetected.
- Priority: HIGH — The largest and most complex files have no tests.

### [CRITICAL] Zero Tests in TraceIQ, Voice_Analysis, Evidence_Analysis

- What's not tested: No test files detected in any sub-project outside MCP_Tool_Platform.
- Files:
  - `TraceIQ/TraceIQ_Main/` — 0 test files for 40+ source files
  - `Voice_Analysis/Chronicle_Voice_App/` — 0 test files
  - `Voice_Analysis/story-voice-backend/` — 0 test files
  - `Evidence_Analysis/ConflictAnalysisApp/` — 0 test files
  - `Evidence_Analysis/forensic-data-refinery/` — 0 test files
- Risk: All forensic data processing, timeline analysis, and evidence parsing runs without any automated verification. For a legal/forensic tool, this is especially concerning since incorrect output could affect court proceedings.
- Priority: CRITICAL

### [MEDIUM] No Test Configuration for Sub-projects

- What's missing: TraceIQ has no `pytest.ini`, `conftest.py`, or testing configuration. Voice_Analysis and Evidence_Analysis similarly lack any test infrastructure.
- Fix approach: Add `pytest` to TraceIQ requirements.txt, create `conftest.py`, add test fixtures for timeline data parsing.

---

## Performance Concerns

### [HIGH] Oversized Server Files — God Module Risk

- Problem: Several server modules are extremely large, suggesting they handle too many responsibilities.
- Files:
  - `server/mcp/plugins/registry.ts` — 2,198 lines
  - `server/mcp/llm/provider-hub.ts` — 1,725 lines
  - `server/mcp/plugins/graph-analytics.ts` — 1,672 lines
  - `server/mcp/forensics/pattern-analyzer.ts` — 1,659 lines
  - `server/mcp/workers/executor.ts` — 1,614 lines
  - `server/mcp/gateway.ts` — 1,431 lines
  - `server/mcp/forensics/timeline-generator.ts` — 1,287 lines
  - `server/api/index.ts` — 1,269 lines
  - `client/src/pages/ComponentShowcase.tsx` — 1,440 lines
  - `client/src/pages/Settings.tsx` — 1,034 lines
- Cause: Monolithic design. Each file handles multiple concerns.
- Improvement path: Split into focused modules. E.g., `registry.ts` could become `registry/index.ts`, `registry/discovery.ts`, `registry/lifecycle.ts`.

### [MEDIUM] 50MB Body Parser Limit

- Problem: Express body parser accepts up to 50MB JSON/URL-encoded payloads (`server/core/index.ts` lines 35-36). This makes the server vulnerable to memory exhaustion attacks.
- Files: `MCP_Tool_Platform/MCP_Tool_Platform_Repo/server/core/index.ts` (lines 35-36)
- Fix approach: Use route-specific limits. 50MB for file upload routes, 1MB for API routes.

### [MEDIUM] API Key Usage Stats Fetches All Logs Into Memory

- Problem: `getApiKeyUsageStats()` in `api-keys.ts` fetches ALL usage logs for an API key into memory, then reduces them in JavaScript. No SQL aggregation, no pagination.
- Files: `MCP_Tool_Platform/MCP_Tool_Platform_Repo/server/mcp/auth/api-keys.ts` (lines 348-371)
- Fix approach: Use SQL `COUNT()`, `SUM()`, `AVG()` aggregations instead of fetching all rows.

### [LOW] TraceIQ Flask App Uses Global Mutable State

- Problem: `app.py` uses a global `processing_status` dictionary (lines 34-43) that is mutated during processing. This is not thread-safe and will fail if Flask runs with multiple workers.
- Files: `TraceIQ/TraceIQ_Main/app.py` (lines 34-43, 82-83)
- Fix approach: Use a database or Redis for processing status. Or use Flask's application context.

---

## Configuration Issues

### [MEDIUM] `.env` and `.env.example` Are Out of Sync

- Problem: `.env.example` (138 lines) contains many variables not in `.env` (72 lines) and vice versa. For example, `.env.example` includes `SUPABASE_URL`, `QDRANT_URL`, `MEM0_URL`, `N8N_URL`, `SANDBOX_ROOT` which are absent from `.env`. Meanwhile `.env` has `MYSQL_HOST/PORT/USER/PASSWORD/DATABASE`, `PGVECTOR_ENABLED` which are absent from `.env.example`.
- Files:
  - `MCP_Tool_Platform/MCP_Tool_Platform_Repo/.env` (72 lines)
  - `MCP_Tool_Platform/MCP_Tool_Platform_Repo/.env.example` (138 lines)
- Fix approach: Synchronize `.env.example` with all actually-used variables. Remove unused ones.

### [MEDIUM] No `.env.example` for Sub-projects

- Problem: TraceIQ, Voice_Analysis, and Evidence_Analysis have no `.env.example` or setup documentation for their environment requirements. TraceIQ's `geocode_resolver_v4.py` reads `RAW_API_DIR` from environment (line 8) with a default of `/mnt/data/raw_api` which is a Linux-specific path that won't work on Windows.
- Files:
  - `TraceIQ/TraceIQ_Main/` — no `.env.example`
  - `TraceIQ/TraceIQ_Main/src/analytics/geocode_resolver_v4.py` (line 8: hardcoded `/mnt/data/raw_api`)
  - `Voice_Analysis/Chronicle_Voice_App/` — no `.env.example`
  - `Voice_Analysis/story-voice-backend/` — has `SETUP.md` but no `.env.example`
- Fix approach: Create `.env.example` for each sub-project documenting required variables.

### [LOW] Multiple Database URL Patterns

- Problem: The MCP platform simultaneously references MySQL (`DATABASE_URL=mysql://...` in `.env`), PostgreSQL (`POSTGRES_HOST/PORT/USER/PASSWORD/DB` in `.env`), and the `db.ts` router tries to manage both. The `env.ts` reads `DATABASE_URL` but `db.postgres.ts` also reads `DATABASE_URL`. It's unclear which database is actually primary.
- Files:
  - `MCP_Tool_Platform/MCP_Tool_Platform_Repo/.env` (lines 5, 12-17)
  - `MCP_Tool_Platform/MCP_Tool_Platform_Repo/server/core/env.ts` (line 4)
  - `MCP_Tool_Platform/MCP_Tool_Platform_Repo/server/core/db.ts` (lines 44-47 — exports both `primary` and `mysql`)
  - `MCP_Tool_Platform/MCP_Tool_Platform_Repo/server/core/db.postgres.ts`
  - `MCP_Tool_Platform/MCP_Tool_Platform_Repo/server/core/db.mysql.ts`
- Fix approach: Decide on a primary database (PostgreSQL per architecture docs) and document the role of MySQL clearly.

---

## Documentation Gaps

### [MEDIUM] Sub-projects Lack README or Setup Instructions

- Problem: Most sub-projects have no README or inadequate setup documentation.
- Files:
  - `Evidence_Analysis/ConflictAnalysisApp/` — no README
  - `Evidence_Analysis/forensic-data-refinery/` — no README, no package.json
  - `Voice_Analysis/Context_Analysis_Suite/` — no README
  - `TraceIQ/location-admin/` — no README
  - `_project_dirs_loose/` — has `AGENTS.md` but no explanation of purpose
- Fix approach: Add a README.md to each sub-project with purpose, setup steps, and usage.

### [MEDIUM] TODO.md Is 5+ Weeks Stale

- Problem: `TODO.md` says "Last Updated: January 20, 2026" and references sprint timelines that have passed. It lists ~80 TypeScript errors, 21 PatternLibrary TODOs, and integration work as "next 1-2 weeks" — all still unresolved.
- Files: `MCP_Tool_Platform/MCP_Tool_Platform_Repo/TODO.md` (269 lines)
- Fix approach: Update to reflect current state or replace with issue tracker.

---

## Dead Code and Unused Files

### [MEDIUM] `_project_dirs_loose/` Contains Orphaned Files

- Issue: This directory contains loose files that appear to be legacy leftovers:
  - `Markdown Code Extractor (Advanced)_20250624133009.py` — standalone script with timestamp in name
  - `MarkdownCodeExtractor.py` — similar script
  - `mcp_recovery_memory.json` — recovery artifact
  - `pasted_content/` — contains a `requirements.txt`
  - `02_Voice_Analysis/` and `03_Evidence_Analysis/` — seem to be old category directories from a previous organizational scheme
  - `.env.production` — production env template that should live inside MCP_Tool_Platform
- Files: `_project_dirs_loose/` (all contents)
- Fix approach: Move `.env.production` to `MCP_Tool_Platform/MCP_Tool_Platform_Repo/`. Evaluate if other files are needed. Delete or archive what isn't.

### [MEDIUM] `TraceIQ/copy-of-timeline-explorer-pro.zip` — Archive File in Source Tree

- Issue: A zip file of the timeline explorer sitting alongside the actual directory.
- Files: `TraceIQ/copy-of-timeline-explorer-pro.zip`
- Fix approach: Delete. The source directory is the canonical version.

### [LOW] Build Error Logs Committed to Repository

- Issue: Build error logs are checked into the repository.
- Files:
  - `MCP_Tool_Platform/MCP_Tool_Platform_Repo/build_errors.log`
  - `MCP_Tool_Platform/MCP_Tool_Platform_Repo/build_errors_v2.log`
  - `MCP_Tool_Platform/MCP_Tool_Platform_Repo/tsc_output.log`
- Fix approach: Add `*.log` to `.gitignore` (already there, so these may be tracked from before). Remove from git tracking.

### [LOW] Deployment Archives in Source Tree

- Issue: Deployment-related tar.gz and zip files exist in the source tree.
- Files:
  - `MCP_Tool_Platform/MCP_Tool_Platform_Repo/site_deploy.tar.gz`
  - `MCP_Tool_Platform/MCP_Tool_Platform_Repo/mcp-tool-platform (1).zip`
  - `MCP_Tool_Platform/MCP_Tool_Platform_Repo/mcp-tool-platform-main.zip`
- Fix approach: Delete from source tree. Use CI/CD for deployment artifacts.

---

## Type Safety Concerns

### [MEDIUM] `as any` Casts and `@ts-ignore` Suppress Type Checking

- Issue: 25 instances of `as any` type casts and `@ts-ignore` directives in the server code. These bypass TypeScript's type safety, which is particularly risky in a forensic application where data integrity matters.
- Files (significant instances):
  - `server/core/db.ts` (line 5: `@ts-ignore` for sql.js module)
  - `server/core/db.mysql.ts` (line 62: `@ts-ignore` for mysql2 version mismatch)
  - `server/core/sdk.ts` (lines 140-144, 251-255: multiple `as any` casts on auth data)
  - `server/mcp/auth/api-keys.ts` (lines 276, 285: `"*" as any` for wildcard permissions)
  - `server/mcp/storage/graphiti-client.ts` (line 166: `as any` on Neo4j query results)
  - `server/mcp/plugins-pending/gcp-document-ai.ts` (lines 102, 144, 194: `as any` on GCP responses)
  - `server/mcp/analysis/classifier.ts` (line 136: `as any` on pattern enum)
- Fix approach: Create proper TypeScript interfaces for external library responses. Fix the mysql2 type mismatch. Remove `@ts-ignore` for sql.js by providing proper type declarations.

---

## Dependency Health

### [MEDIUM] Massive Dependency Surface — 108 Direct Dependencies

- Issue: The MCP Platform `package.json` lists 108 direct dependencies (124 including devDependencies). Many are heavyweight cloud SDKs that may not be actively used: `@aws-sdk/client-comprehend`, `@aws-sdk/client-rekognition`, `@aws-sdk/client-textract`, `@google-cloud/aiplatform`, `@google-cloud/documentai`, `@google-cloud/language`, `@google-cloud/speech`, `@google-cloud/storage`, `@google-cloud/vertexai`, `@google-cloud/video-intelligence`, `@google-cloud/vision`, `llamaindex`, `@langchain/community`, `@langchain/core`, `faiss-node`, `chromadb`, `neo4j-driver`, etc.
- Files: `MCP_Tool_Platform/MCP_Tool_Platform_Repo/package.json` (lines 16-153)
- Impact: Slow installs, large `node_modules`, increased attack surface, potential version conflicts.
- Fix approach: Audit which dependencies are actually imported in active code. Move unused ones to `optionalDependencies` or remove entirely. The GCP plugins in `plugins-pending/` account for at least 8 unused `@google-cloud/*` packages.

### [LOW] Patched Dependency (wouter@3.7.1)

- Issue: `pnpm` config includes a patch for `wouter@3.7.1` but the installed version is `^3.3.5`. The patch may not apply correctly to different versions.
- Files: `MCP_Tool_Platform/MCP_Tool_Platform_Repo/package.json` (lines 157-159)
- Fix approach: Verify the patch still applies. Update the patch if wouter version has changed.

### [LOW] TraceIQ Requirements Are Version-Floored Only

- Issue: `requirements.txt` uses `>=` without upper bounds (e.g., `Flask>=2.3`, `gunicorn>=20`). This allows major version bumps that could break the application.
- Files: `TraceIQ/TraceIQ_Main/requirements.txt` (5 lines)
- Fix approach: Pin to specific versions or use compatible release operators (e.g., `Flask~=2.3`).

---

## Scalability Concerns

### [MEDIUM] SQLite for Timeline Processing

- Issue: TraceIQ's `app.py` uses SQLite for timeline data storage. SQLite has a single-writer limitation and doesn't support concurrent write operations. The app uses threading (line 13: `import threading`) with SQLite, which requires careful connection management.
- Files: `TraceIQ/TraceIQ_Main/app.py` (lines 30, 59-63, 102)
- Limit: Single concurrent writer. Will fail under concurrent timeline processing requests.
- Fix approach: For single-user forensic analysis, SQLite is adequate if connections are properly managed per-thread. For multi-user, migrate to PostgreSQL.

### [LOW] ChromaDB Health Check Is Hardcoded to True

- Issue: In `db.ts`, the `initAllDatabases()` function hardcodes ChromaDB health to `true` with the comment "ChromaDB doesn't have test connection yet."
- Files: `MCP_Tool_Platform/MCP_Tool_Platform_Repo/server/core/db.ts` (line 204)
- Fix approach: Implement a ChromaDB health check (e.g., list collections) or mark as `unknown`.

---

## Anti-Patterns

### [MEDIUM] Dynamic Imports to Avoid Circular Dependencies

- Issue: `db.ts` uses dynamic `await import()` inside functions to avoid circular dependency issues with the Drizzle schema.
- Files: `MCP_Tool_Platform/MCP_Tool_Platform_Repo/server/core/db.ts` (lines 238-239, 272-273)
- Impact: Breaks tree-shaking, makes dependencies opaque, introduces subtle timing bugs.
- Fix approach: Restructure module boundaries to eliminate circular dependencies. Move user-related DB operations out of `db.ts` into a `users.ts` service.

### [LOW] SQL Injection Risk in TraceIQ geocode_resolver_v4.py

- Issue: The `upsert()` function builds SQL using f-strings for table names and column names. While the values use parameterized queries (`?` placeholders), the table and column names are interpolated directly.
- Files: `TraceIQ/TraceIQ_Main/src/analytics/geocode_resolver_v4.py` (lines 27-29)
- Current mitigation: Table/column names come from internal code, not user input. Risk is low but pattern is unsafe.
- Fix approach: Use an allowlist of valid table/column names or use an ORM.

---

*Concerns audit: 2026-02-25*
