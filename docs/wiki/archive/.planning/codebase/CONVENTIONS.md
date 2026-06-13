# Coding Conventions

**Analysis Date:** 2026-02-25

## Sub-Project Overview

TheBigOne is a monorepo-style collection of independent sub-projects with no shared workspace root config. Each sub-project has its own conventions. The primary actively-developed sub-project is **MCP_Tool_Platform** (`MCP_Tool_Platform/MCP_Tool_Platform_Repo/`). Secondary sub-projects (TraceIQ, Evidence_Analysis, Voice_Analysis) are smaller, less formalized.

---

## Code Style & Formatting

### MCP_Tool_Platform (Primary)

**Formatter:** Prettier v3.6.2
- Config: `MCP_Tool_Platform/MCP_Tool_Platform_Repo/.prettierrc`
- Ignore: `MCP_Tool_Platform/MCP_Tool_Platform_Repo/.prettierignore`
- Run command: `pnpm format` (runs `prettier --write .`)

**Prettier Settings:**
```json
{
  "semi": true,
  "trailingComma": "es5",
  "singleQuote": false,
  "printWidth": 80,
  "tabWidth": 2,
  "useTabs": false,
  "bracketSpacing": true,
  "bracketSameLine": false,
  "arrowParens": "avoid",
  "endOfLine": "lf",
  "quoteProps": "as-needed",
  "jsxSingleQuote": false,
  "proseWrap": "preserve"
}
```

**Key rules to follow:**
- Use double quotes for strings (NOT single quotes)
- Always use semicolons
- 2-space indentation, no tabs
- Trailing commas in ES5 positions (objects, arrays)
- Omit arrow function parens when possible (`x => x` not `(x) => x`)
- LF line endings (not CRLF)

**Linter:** No ESLint configured in active projects. Only found in archived external modules (`Junkyard/` paths). Use TypeScript's `tsc --noEmit` for type checking via `pnpm check`.

### TraceIQ / Evidence_Analysis / Voice_Analysis / Chronicle

**No Prettier or ESLint configured.** These sub-projects have no formatting or linting tooling. Code style varies.

### Python Code (TraceIQ_Main)

**No Ruff, Black, or Flake8 configured.** Python files follow PEP 8 loosely:
- 4-space indentation
- snake_case for functions and variables
- Type hints used occasionally (e.g., `TraceIQ/TraceIQ_Main/logging_config.py` has type annotations)
- No `pyproject.toml` or `setup.py` in active Python code (only `requirements.txt` at `TraceIQ/TraceIQ_Main/requirements.txt`)

---

## TypeScript Strictness

### MCP_Tool_Platform (Primary - Strictest)

**Config:** `MCP_Tool_Platform/MCP_Tool_Platform_Repo/tsconfig.json`

```json
{
  "compilerOptions": {
    "strict": true,
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "preserve",
    "esModuleInterop": true,
    "skipLibCheck": true,
    "allowImportingTsExtensions": true,
    "noEmit": true,
    "incremental": true
  }
}
```

**Key:** `strict: true` is enabled. This means strictNullChecks, strictFunctionTypes, strictPropertyInitialization, noImplicitAny, etc. are all active.

### TraceIQ timeline-explorer-pro & Chronicle_Voice_App

**Config:** `TraceIQ/timeline-explorer-pro/tsconfig.json`, `Voice_Analysis/Chronicle_Voice_App/tsconfig.json`

These share identical settings:
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "allowJs": true,
    "noEmit": true
  }
}
```

**Key:** `strict` is NOT set (defaults to `false`). These are looser TypeScript configurations. `allowJs: true` is enabled. `experimentalDecorators: true` is set (unusual for React projects).

---

## Import Patterns

### MCP_Tool_Platform (Primary)

**Path aliases defined in `tsconfig.json` and `vite.config.ts`:**

| Alias | Resolves To | Usage |
|-------|-------------|-------|
| `@/*` | `./client/src/*` | Client-side imports |
| `@shared/*` | `./shared/*` | Shared types and constants |
| `@server/*` | `./server/*` | Server-side cross-refs |
| `@core/*` | `./server/core/*` | Core server modules |
| `@api/*` | `./server/api/*` | API layer |
| `@mcp/*` | `./server/mcp/*` | MCP subsystem |
| `@assets` | `./attached_assets` | Static assets |

**Import conventions observed:**
- **Client code** uses `@/` alias exclusively: `import { trpc } from "@/lib/trpc"` (see `client/src/main.tsx`)
- **Shared imports** use `@shared/`: `import { UNAUTHED_ERR_MSG } from "@shared/const"` (see `server/core/trpc.ts`)
- **Server code** uses relative paths for local imports within the same directory and `@shared` for cross-boundary: `import { z } from "zod"` then `import type { ToolCard } from "../../shared/mcp-types"` (see `server/mcp/gateway.ts`)
- **Third-party imports** come first, then internal aliases, then relative imports
- **No barrel files** (`index.ts` re-exports) in client code except `shared/types.ts`

**Pattern to follow for new code:**
```typescript
// 1. Third-party imports
import { z } from "zod";
import { TRPCError } from "@trpc/server";

// 2. Alias imports (shared, then local)
import { COOKIE_NAME } from "@shared/const";
import { router, protectedProcedure } from "../core/trpc";

// 3. Type-only imports
import type { ToolCard, ToolSpec } from "../../shared/mcp-types";
```

### TraceIQ / Voice_Analysis / Evidence_Analysis

**Path alias:** Only `@/*` mapping to project root (`./*`). Simpler projects use relative imports throughout.

### Python Code

Standard Python imports with no special conventions:
```python
from __future__ import annotations
import argparse, logging, sys
from pathlib import Path
from scripts.pass1_parse_json import run_pass1
```

---

## Naming Patterns

### Files

**TypeScript (MCP_Tool_Platform):**
- Components: `PascalCase.tsx` (e.g., `ErrorBoundary.tsx`, `DashboardLayout.tsx`, `AIChatBox.tsx`)
- Hooks: `camelCase.ts` with `use` prefix (e.g., `useComposition.ts`, `useMobile.tsx`, `usePersistFn.ts`)
- Utilities/libs: `camelCase.ts` (e.g., `trpc.ts`, `utils.ts`)
- Server modules: `kebab-case.ts` (e.g., `content-store.ts`, `chain-custody.ts`, `pattern-analyzer.ts`, `mcp-proxy.ts`)
- Test files: `kebab-case.test.ts` co-located with source (e.g., `gateway.test.ts`, `chain-custody.test.ts`)
- Config files: `kebab-case.ts` (e.g., `drizzle.config.ts`, `vitest.config.ts`)
- Type files: `types.ts` (single file per domain)
- Constants: `const.ts` (e.g., `shared/const.ts`, `client/src/const.ts`)

**TypeScript (TraceIQ/Voice_Analysis):**
- Components: `PascalCase.tsx` (e.g., `FileUpload.tsx`, `DataTable.tsx`, `ReviewDeck.tsx`)
- Utilities: `camelCase.ts` (e.g., `parser.ts`)

**Python (TraceIQ_Main):**
- Scripts: `snake_case.py` (e.g., `pipeline_orchestrator_v6.py`, `logging_config.py`, `validate_timeline_data.py`)
- SQL: `snake_case.sql` (e.g., `schema_complete.sql`, `normalized_geo_schema_v5.sql`)

### Functions & Variables

**TypeScript:**
- Functions: `camelCase` (e.g., `createTestContext`, `getDatabaseClient`, `findAvailablePort`)
- Variables: `camelCase` (e.g., `trpcClient`, `queryClient`, `templateRoot`)
- Constants: `SCREAMING_SNAKE_CASE` (e.g., `COOKIE_NAME`, `ONE_YEAR_MS`, `UNAUTHED_ERR_MSG`, `DATABASE_ROLES`)
- Boolean variables: No consistent `is`/`has` prefix convention

**Python:**
- Functions: `snake_case` (e.g., `setup_logging`, `process_timeline_json`, `generate_short_uuid`)
- Variables: `snake_case` (e.g., `processing_status`, `db_path`)
- Constants: `SCREAMING_SNAKE_CASE` (e.g., `PROJECT_ROOT`, `DEFAULT_SCHEMA`, `REQUIRED_DIRS`, `DB_PATH`)

### Types & Interfaces

- Exported types: `PascalCase` (e.g., `DatabaseRole`, `TrpcContext`, `ApiResponse`, `ContentRef`)
- Type-only imports use `import type` syntax consistently
- Zod schemas for runtime validation: `camelCase` (e.g., `searchToolsInput`, `invokeToolInput`)
- React component props: `PascalCase` with no `I` prefix (e.g., `Props`, `State`)

---

## Error Handling

### MCP_Tool_Platform Server-Side

**Three error patterns observed:**

1. **tRPC errors** for API layer (`server/core/trpc.ts`, `server/mcp/gateway.ts`):
```typescript
throw new TRPCError({ code: "UNAUTHORIZED", message: UNAUTHED_ERR_MSG });
throw new TRPCError({ code: "NOT_FOUND", message: "Tool not found" });
```

2. **Custom HttpError class** for general HTTP errors (`shared/core/errors.ts`):
```typescript
export class HttpError extends Error {
  constructor(public statusCode: number, message: string) {
    super(message);
    this.name = "HttpError";
  }
}
// Convenience constructors
export const BadRequestError = (msg: string) => new HttpError(400, msg);
export const UnauthorizedError = (msg: string) => new HttpError(401, msg);
export const NotFoundError = (msg: string) => new HttpError(404, msg);
```

3. **Try/catch with logging** for infrastructure code (`server/core/db.ts`, `server/core/index.ts`):
```typescript
try {
  const client = await getDatabaseClient(role);
} catch (error) {
  console.log(`Failed: ${(error as Error).message}`);
}
```

### Client-Side

- **ErrorBoundary** component wraps the entire app (`client/src/components/ErrorBoundary.tsx`)
- **Query/mutation error handling** in `client/src/main.tsx` with automatic redirect on auth errors
- **Console.error** with prefixed tags: `console.error("[API Query Error]", error)`
- **Error type narrowing:** `error instanceof Error ? error.message : "Unknown error"` pattern used consistently

### Python (TraceIQ_Main)

- Try/except with logging: `logger.error(f"Database initialization failed: {e}")`
- Raise after logging for critical errors
- `sys.exit()` for fatal CLI errors

---

## Logging

### MCP_Tool_Platform (TypeScript)

**Framework:** `console.*` (no structured logging library like Winston or Pino)

**Patterns observed:**
- `console.log()` for informational output with emoji prefixes in test/debug code
- `console.error()` for errors with descriptive prefixes: `console.error("[API Query Error]", error)`
- No structured logging (no log levels, no JSON output)
- Server-side uses `console.log()` directly: `console.log(\`Server running on http://localhost:${port}/\`)`

### TraceIQ_Main (Python)

**Framework:** Python `logging` module with centralized config

**Config location:** `TraceIQ/TraceIQ_Main/logging_config.py`

**Pattern:**
```python
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('data/logs/app.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('TraceIQ')
```

**Features:**
- Dual output: file + console
- Timestamped log files with module name
- Named loggers per module
- `setup_logging()` factory function for consistent logger creation

---

## Comment & Documentation Style

### File Headers (MCP_Tool_Platform)

Many files include a metadata comment on line 1:
```typescript
// File: server/mcp/gateway.ts | Date: 2026-01-11 | Agent: Claude Code | Model: Opus 4.1
```

This is an AI agent attribution pattern. Use this format for new files.

### JSDoc/TSDoc

**Module-level JSDoc** with description blocks:
```typescript
/**
 * MCP Gateway API
 *
 * Token-efficient gateway exposing 4 core endpoints:
 * - search_tools: Discover tools with minimal token overhead
 * - describe_tool: Get full tool specification on demand
 * - invoke_tool: Execute tools with reference-based returns
 * - get_ref: Retrieve content-addressed artifacts with paging
 */
```

**Test file headers:**
```typescript
/**
 * Pattern Analyzer Tests
 * Tests the forensic pattern analyzer with seeded database patterns
 */
```

**Function-level JSDoc** is sparse. Used for exported utility functions but not for route handlers or component methods.

### Section Separators

Heavy use of comment banners in large files:
```typescript
// ============================================================================
// DATABASE ROLE DEFINITIONS
// ============================================================================
```

This pattern appears in `server/core/db.ts`, `server/api/index.ts`, `server/mcp/gateway.ts` and is used to delineate logical sections within files.

### Python Docstrings

Standard docstring format:
```python
def setup_logging(
    module_name: str = "timeline_processor",
    log_level: int = logging.INFO,
) -> logging.Logger:
    """
    Set up enhanced logging configuration with file and console handlers.
    
    Args:
        module_name: Name of the module for the logger
        log_level: Logging level (default: INFO)
        
    Returns:
        Configured logger instance
    """
```

### Inline Comments

- Used sparingly for non-obvious logic
- `// TODO:`, `// FIXME:` markers present in some files
- Comments explain "why" not "what" in most cases

---

## Git Conventions

### .gitignore

**Primary config:** `MCP_Tool_Platform/MCP_Tool_Platform_Repo/.gitignore` (114 lines, comprehensive)

**Key ignores:**
- `**/node_modules`, `.pnpm-store/`
- `dist/`, `build/`
- `.env`, `.env.local`, `.env.*.local` (but `.env.example` and `.env.docker.example` ARE committed)
- `.vscode/`, `.idea/`
- `*.db`, `*.sqlite`, `*.sqlite3`
- `coverage/`, `*.lcov`, `.nyc_output`
- `*.log`
- `*.tsbuildinfo`

**Sub-project .gitignore files** exist at: `TraceIQ/timeline-explorer-pro/.gitignore`, `Voice_Analysis/Chronicle_Voice_App/.gitignore`, `_project_dirs_loose/.gitignore`

### Repository Structure

**No git repo at TheBigOne root** (`git log` fails at root level). The MCP_Tool_Platform_Repo appears to have had a git repo but may not currently be initialized (empty `git log` output). GitHub remote configured as `https://github.com/Cursedpotential/TraceIQ.git` per CLAUDE.md.

### Commit Message Convention

No enforced convention (no commitlint, no husky, no conventional commits config). Per CLAUDE.md, the workflow is:
1. Run `git status` and `git log -5` before starting work
2. No specific commit message format required

### Branch Strategy

Not explicitly documented. The CI workflow (`integration.yml`) triggers on `push` and `pull_request` to `main` branch.

---

## Environment Configuration

### MCP_Tool_Platform (Primary)

**Environment files:**
- `MCP_Tool_Platform/MCP_Tool_Platform_Repo/.env` - Active local config (gitignored)
- `MCP_Tool_Platform/MCP_Tool_Platform_Repo/.env.example` - Template with all vars (138 lines, committed)
- `MCP_Tool_Platform/MCP_Tool_Platform_Repo/.env.docker.example` - Docker variant
- `MCP_Tool_Platform/MCP_Tool_Platform_Repo/.env.postgres.example` - PostgreSQL variant
- `MCP_Tool_Platform/MCP_Tool_Platform_Repo/server/python-tools/.env` - Python tools env

**Config module:** `server/core/env.ts` - Simple object with `process.env` reads:
```typescript
export const ENV = {
  appId: process.env.VITE_APP_ID ?? "",
  cookieSecret: process.env.JWT_SECRET ?? "",
  databaseUrl: process.env.DATABASE_URL ?? "",
  oAuthServerUrl: process.env.OAUTH_SERVER_URL ?? "",
  // ...
};
```

**No Zod validation on env vars.** Defaults to empty strings with `??` operator. The `drizzle.config.ts` is the only file that throws on missing env vars.

**Critical env var categories** (from `.env.example`):
- Database: `DATABASE_URL`, `POSTGRES_*`, `NEO4J_*`, `CHROMA_URL`, `QDRANT_URL`
- Auth: `JWT_SECRET`, `ENCRYPTION_KEY`, `OAUTH_SERVER_URL`
- LLM: `OPENAI_API_KEY`, `GOOGLE_API_KEY`, `OLLAMA_URL`
- Storage: `SUPABASE_URL`, `SUPABASE_KEY`, `DATA_ROOT`
- Feature flags: `ENABLE_VECTOR_DB`, `ENABLE_GRAPH_DB`, `ENABLE_MEM0`, `ENABLE_N8N`
- Server: `PORT`, `NODE_ENV`, `LOG_LEVEL`

**Vite client-side env:** Variables prefixed with `VITE_` are exposed to the client (standard Vite convention).

### TraceIQ (Python)

Environment configuration is done inline via `os.environ` or hardcoded paths. No `.env` loader configured in `requirements.txt` (no `python-dotenv`).

---

## Module Design & Exports

### MCP_Tool_Platform

**Shared types barrel file:** `shared/types.ts` re-exports from schema and errors:
```typescript
export type * from "../drizzle/schema";
export * from "./core/errors";
```

**Server modules** use the factory/singleton pattern extensively:
```typescript
// Lazy singleton pattern
export function getPluginRegistry() { ... }
export function getTaskExecutor() { ... }
export function getContentStore() { ... }
export function getMCPProxy() { ... }
```

**tRPC router composition** in `server/api/index.ts`:
```typescript
export const appRouter = router({
  system: systemRouter,
  mcp: mcpGatewayRouter,
  config: configRouter,
  stats: statsRouter,
  // ...
});
export type AppRouter = typeof appRouter;
```

**Validation:** All API inputs validated with Zod schemas inline (not extracted to separate files):
```typescript
const searchToolsInput = z.object({
  query: z.string().min(1).max(200),
  topK: z.number().int().min(1).max(50).default(10),
});
```

### Constants Pattern

Shared constants in `shared/const.ts`:
```typescript
export const COOKIE_NAME = "app_session_id";
export const ONE_YEAR_MS = 1000 * 60 * 60 * 24 * 365;
export const UNAUTHED_ERR_MSG = "Please login (10001)";
```

---

## Framework & Library Conventions

### React (Client)

- **Routing:** `wouter` (not React Router)
- **State management:** React Query (`@tanstack/react-query`) for server state, `useState` for local
- **API layer:** tRPC client with `superjson` transformer
- **UI components:** Radix UI primitives + shadcn/ui pattern (`client/src/components/ui/`)
- **Styling:** Tailwind CSS v4 with `tailwind-merge` and `class-variance-authority`
- **Icons:** `lucide-react`
- **Toasts:** `sonner`
- **Forms:** `react-hook-form` with `@hookform/resolvers` (Zod)
- **Theme:** Custom `ThemeProvider` with `next-themes`
- **Component pattern:** Function components, default exports, named interfaces for Props

### Express (Server)

- Express with tRPC adapter (`@trpc/server/adapters/express`)
- `dotenv/config` imported at entry point
- Body parser with 50MB limit for file uploads
- tRPC at `/api/trpc`
- OAuth routes registered separately

---

*Convention analysis: 2026-02-25*
