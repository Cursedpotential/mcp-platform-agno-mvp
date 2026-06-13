---
phase: 01-foundation
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - server/mcp/storage/duckdb.ts
  - server/mcp/storage/lancedb.ts
  - server/mcp/storage/neo4j/
  - server/mcp/storage/systemRouter.ts
  - server/mcp/python-bridge.ts
  - package.json
  - .env.example
autonomous: true

must_haves:
  truths:
    - DuckDB initializes and creates staging tables
    - LanceDB initializes with schema for binaries + vectors
    - Neo4j connects and creates two named databases
    - Python bridge starts with spaCy/sentence-transformers loaded
    - All 5 storage tiers report healthy on startup
    - MCP tools expose storage status and initialization
  artifacts:
    - path: "server/mcp/storage/duckdb.ts"
      provides: "DuckDB client with staging tables"
      min_lines: 200
    - path: "server/mcp/storage/lancedb.ts"
      provides: "LanceDB client with schema"
      min_lines: 150
    - path: "server/mcp/storage/neo4j/semantic_facts.ts"
      provides: "Neo4j semantic_facts database client"
      min_lines: 100
    - path: "server/mcp/storage/neo4j/temporal_memory.ts"
      provides: "Neo4j temporal_memory database client"
      min_lines: 100
    - path: "server/mcp/python-bridge.ts"
      provides: "Unified Python bridge for NLP"
      min_lines: 300
    - path: "server/mcp/storage/systemRouter.ts"
      provides: "TrinityRouter for multi-tier writes"
      min_lines: 200
  key_links:
    - from: "server/mcp/storage/systemRouter.ts"
      to: "server/mcp/storage/duckdb.ts"
      via: "import and call"
      pattern: "TrinityRouter.*duckdb"
    - from: "server/mcp/storage/duckdb.ts"
      to: "server/mcp/storage/lancedb.ts"
      via: "Arrow integration"
      pattern: "arrow.*Table"
    - from: "server/mcp/python-bridge.ts"
      to: "python-tools/"
      via: "child_process spawn"
      pattern: "spawn.*python"
---

<objective>
Initialize the 5-tier storage architecture: DuckDB (Master Clock), LanceDB (Multimodal Vault), dual Neo4j (Semantic + Temporal), and unified Python bridge. Archive old PostgreSQL code. Fix only TypeScript errors that block storage initialization.

Purpose: Foundation storage layer must be operational before Phase 2 (pipelines) and Phase 4 (enrichment). This is the bedrock of the merged architecture.
Output: All 5 storage tiers initialized, MCP tools exposed, health checks passing
</objective>

<execution_context>
./.opencode/get-shit-done/workflows/execute-plan.md
./.opencode/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/REQUIREMENTS.md
@.planning/ROADMAP.md
@.planning/phases/phase-1/CODEBASE_ANALYSIS.md

Phase 1, Wave 1 — Must complete before any data ingestion.

Key Constraints:
- DuckDB replaces Chroma for temp storage + PostgreSQL for structured
- LanceDB replaces Qdrant/pgvector for vectors + Directus for binaries
- Old PostgreSQL code should be archived, not fixed
- Only fix TypeScript errors that block new storage code
- Python bridge currently 100% stub — needs real implementation
</context>

<tasks>

<task type="auto">
  <name>Task 1: Archive Old Storage Code</name>
  <files>
    - server/mcp/storage/supabase-client.ts
    - server/mcp/chroma/ (working memory, keep but deprecate)
    - drizzle/production-message-schemas.ts (PostgreSQL for messages)
  </files>
  <action>
    Move deprecated storage code to archive location:
    
    1. Create `server/mcp/storage/archive/` directory
    2. Move `supabase-client.ts` to `archive/supabase-client.ts`
       - Add header comment: "DEPRECATED: Use DuckDB/LanceDB instead"
    3. Keep `server/mcp/chroma/` but add deprecation notice to README
    4. Move `drizzle/production-message-schemas.ts` to `drizzle/archive/`
    5. Update imports that reference archived files to point to new storage
    
    DO NOT delete files — archive them for reference.
    DO NOT fix TypeScript errors in archived files.
    
    Files that import archived code will show errors — we'll fix those in Task 2.
  </action>
  <verify>
    Run: `ls server/mcp/storage/archive/`
    Expected: supabase-client.ts exists in archive
    
    Run: `grep -r "from.*supabase-client" server/ --include="*.ts" | grep -v archive | wc -l`
    Expected: 0 (no active imports from supabase)
  </verify>
  <done>
    Old storage code archived. Imports updated. No active references to deprecated storage.
  </done>
</task>

<task type="auto">
  <name>Task 2: Install DuckDB + LanceDB Dependencies</name>
  <files>
    - package.json
    - server/mcp/storage/duckdb.ts (create)
    - server/mcp/storage/lancedb.ts (create)
  </files>
  <action>
    Add and install new storage dependencies:
    
    1. Add to package.json dependencies:
       ```json
       {
         "duckdb": "^0.10.0",
         "@lancedb/lancedb": "^0.12.0",
         "apache-arrow": "^15.0.0"
       }
       ```
    
    2. Run: `pnpm install`
    
    3. Create `server/mcp/storage/duckdb.ts`:
       - DuckDB client wrapper (embedded, no server)
       - Initialize connection to file: `./data/duckdb/forensic_vault.db`
       - Create staging tables: `ingestion_log`, `normalized_messages`
       - SHA-256 utilities for chain of custody
       - Write tracking functions
    
    4. Create `server/mcp/storage/lancedb.ts`:
       - LanceDB client wrapper (local, no server)
       - Initialize connection to: `./data/lancedb/multimodal_vault`
       - Create collections: `raw_binaries`, `embeddings`
       - Schema for raw_binaries: uuid, source_hash, timestamp, content_type, data, metadata
       - Schema for embeddings: uuid, source_hash, embedding_vector, text, metadata
       - Arrow integration with DuckDB
    
    Fix ONLY TypeScript errors that prevent compilation of these new files.
    Ignore errors in unrelated files for now.
  </action>
  <verify>
    Run: `pnpm install` completes successfully
    
    Run: `npx ts-node -e "import('./server/mcp/storage/duckdb').then(m => console.log('DuckDB module loads'))"`
    Expected: "DuckDB module loads" (no TypeScript errors)
    
    Run: `npx ts-node -e "import('./server/mcp/storage/lancedb').then(m => console.log('LanceDB module loads'))"`
    Expected: "LanceDB module loads" (no TypeScript errors)
  </verify>
  <done>
    DuckDB and LanceDB dependencies installed. Client modules created. No blocking TypeScript errors.
  </done>
</task>

<task type="auto">
  <name>Task 3: Configure Dual Neo4j Databases</name>
  <files>
    - server/mcp/storage/neo4j/semantic_facts.ts (create)
    - server/mcp/storage/neo4j/temporal_memory.ts (create)
    - server/mcp/storage/graphiti-client.ts (update)
  </files>
  <action>
    Set up dual Neo4j database configuration:
    
    1. Create `server/mcp/storage/neo4j/semantic_facts.ts`:
       - Neo4j client for `semantic_facts` database
       - Connection to Neo4j Aura or local instance
       - Functions: connect, query, createNode, createRelation
       - PROV-O provenance tracking helpers
    
    2. Create `server/mcp/storage/neo4j/temporal_memory.ts`:
       - Neo4j client for `temporal_memory` database
       - Connection using same Neo4j instance, different database name
       - Functions: connect, query, createEpisodicFact, createTemporalEdge
       - valid_at/invalid_at timestamp handling
    
    3. Update `server/mcp/storage/graphiti-client.ts`:
       - Replace stub implementation
       - Use `temporal_memory` database
       - Implement: add_episode, search, get_by_id
       - Call Python bridge for entity extraction
    
    4. Ensure both databases can be selected via session.run("USE database")
       or by specifying database in driver.session({ database: "..." })
    
    Environment variables needed:
    - NEO4J_URI=bolt://localhost:7687
    - NEO4J_USERNAME=neo4j
    - NEO4J_PASSWORD=password
  </action>
  <verify>
    Run: `npx ts-node -e "
      import { SemanticFactsDB } from './server/mcp/storage/neo4j/semantic_facts';
      import { TemporalMemoryDB } from './server/mcp/storage/neo4j/temporal_memory';
      console.log('Neo4j modules load');
    "`
    Expected: "Neo4j modules load" (no TypeScript errors)
  </verify>
  <done>
    Dual Neo4j database clients created. Graphiti client updated. No blocking TypeScript errors.
  </done>
</task>

<task type="auto">
  <name>Task 4: Create TrinityRouter (Multi-Tier Write Coordinator)</name>
  <files>
    - server/mcp/storage/systemRouter.ts (create)
  </files>
  <action>
    Create TrinityRouter to coordinate writes across all storage tiers:
    
    1. Create `server/mcp/storage/systemRouter.ts`:
       - Import DuckDB, LanceDB, and Neo4j clients
       - Class: TrinityRouter
       - Methods:
         - `initializeAll(): Promise<void>` - Initialize all storage tiers
         - `healthCheck(): Promise<StorageHealth>` - Check all tier statuses
         - `ingestEvidence(data: EvidenceData): Promise<IngestionResult>` - Write to all tiers
         - `getStatus(): StorageStatus` - Current status of each tier
    
    2. Ingestion flow:
       - SHA-256 hash at first touch
       - Write to DuckDB: ingestion_log + normalized_messages
       - Write to LanceDB: raw_binaries (if media) or embeddings (if text)
       - Write to Neo4j semantic_facts: if entities extracted
       - Write to Neo4j temporal_memory: if temporal relationships
       - Track write status per tier
    
    3. Health check endpoints:
       - Check DuckDB: SELECT 1
       - Check LanceDB: list collections
       - Check Neo4j: CALL dbms.components()
       - Check MySQL: SELECT 1
       - Check Python bridge: ping endpoint
    
    4. Fix only TypeScript errors in this file and its direct imports.
  </action>
  <verify>
    Run: `npx ts-node -e "import('./server/mcp/storage/systemRouter').then(m => console.log('TrinityRouter loads'))"`
    Expected: "TrinityRouter loads" (no TypeScript errors)
  </verify>
  <done>
    TrinityRouter created. Coordinates multi-tier writes. Health checks defined. No blocking TypeScript errors.
  </done>
</task>

<task type="auto">
  <name>Task 5: Implement Unified Python Bridge</name>
  <files>
    - server/mcp/python-bridge.ts (rewrite)
    - python-tools/main.py (create)
    - python-tools/requirements.txt (update)
  </files>
  <action>
    Replace stub Python bridge with real implementation:
    
    1. Create `python-tools/main.py`:
       - FastAPI or Flask server
       - Endpoints:
         - POST /nlp/extract_entities - spaCy NER
         - POST /nlp/embed - sentence-transformers embeddings
         - POST /graphiti/extract - temporal facts
         - GET /health - status check
       - Load models on startup and keep in memory
       - Return proper JSON responses
    
    2. Update `python-tools/requirements.txt`:
       ```
       spacy>=3.7.0
       sentence-transformers>=2.3.0
       fastapi>=0.109.0
       uvicorn>=0.27.0
       pydantic>=2.5.0
       ```
    
    3. Rewrite `server/mcp/python-bridge.ts`:
       - Class: PythonBridge
       - Spawn Python process with main.py
       - Methods:
         - `start(): Promise<void>` - Start Python server
         - `extractEntities(text: string): Promise<Entity[]>`
         - `generateEmbeddings(texts: string[]): Promise<number[][]>`
         - `extractTemporalFacts(text: string): Promise<TemporalFact[]>`
         - `healthCheck(): Promise<boolean>`
       - Handle process lifecycle (restart on crash)
       - Type-safe interfaces
    
    4. Fix TypeScript errors only in this file.
  </action>
  <verify>
    Run: `cd python-tools && pip install -r requirements.txt`
    Expected: All packages install successfully
    
    Run: `python python-tools/main.py &` then `curl http://localhost:8000/health`
    Expected: {"status": "ok"}
    
    Run: `npx ts-node -e "import('./server/mcp/python-bridge').then(m => console.log('Python bridge loads'))"`
    Expected: "Python bridge loads" (no TypeScript errors)
  </verify>
  <done>
    Python bridge implemented. FastAPI server runs. TypeScript client connects. No blocking TypeScript errors.
  </done>
</task>

<task type="auto">
  <name>Task 6: Expose MCP Tools for Storage Status</name>
  <files>
    - server/mcp/tools/storage-tools.ts (create)
    - server/mcp/tools/initialize-tools.ts (create)
  </files>
  <action>
    Create MCP tools for storage management:
    
    1. Create `server/mcp/tools/storage-tools.ts`:
       - Tool: `duckdb_status` - Check DuckDB health
       - Tool: `lancedb_status` - Check LanceDB health
       - Tool: `neo4j_status` - Check Neo4j health (both databases)
       - Tool: `python_bridge_status` - Check Python bridge
       - Tool: `storage_health` - Check all tiers at once
       
    2. Create `server/mcp/tools/initialize-tools.ts`:
       - Tool: `initialize_storage` - Initialize all storage tiers
       - Tool: `initialize_duckdb` - Initialize just DuckDB
       - Tool: `initialize_lancedb` - Initialize just LanceDB
       - Tool: `initialize_neo4j` - Initialize Neo4j databases
    
    3. Register tools in MCP gateway
    
    4. Add REST API endpoints:
       - GET /api/v1/health/storage - Storage health check
       - POST /api/v1/storage/init - Initialize storage
    
    5. Add Portal UI components (basic):
       - Storage status dashboard
       - Initialize buttons
    
    Fix only TypeScript errors that block tool registration.
  </action>
  <verify>
    Run: `pnpm dev` and check logs for MCP tool registration
    Expected: "Registered tool: storage_health" in logs
    
    Test MCP tool: Call `storage_health` via MCP
    Expected: Returns status for all 5 tiers
  </verify>
  <done>
    MCP tools exposed for storage status and initialization. REST API endpoints working. Portal UI basic dashboard ready.
  </done>
</task>

<task type="auto">
  <name>Task 7: Startup Integration and Health Verification</name>
  <files>
    - server/index.ts (update)
    - server/mcp/storage/duckdb.ts
    - server/mcp/storage/lancedb.ts
    - server/mcp/storage/neo4j/
    - server/mcp/python-bridge.ts
  </files>
  <action>
    Integrate storage initialization into app startup:
    
    1. Update `server/index.ts`:
       - Import TrinityRouter
       - On startup:
         - Initialize TrinityRouter
         - Run health check
         - Log status of each storage tier
         - If any tier fails, log warning but don't crash (graceful degradation)
    
    2. Create `.env.example` with all required env vars:
       ```
       # Application
       DATABASE_URL=mysql://...
       
       # DuckDB
       DUCKDB_PATH=./data/duckdb/forensic_vault.db
       
       # LanceDB
       LANCEDB_PATH=./data/lancedb/multimodal_vault
       
       # Neo4j
       NEO4J_URI=bolt://localhost:7687
       NEO4J_USERNAME=neo4j
       NEO4J_PASSWORD=password
       
       # Python Bridge
       PYTHON_BRIDGE_PORT=8000
       ```
    
    3. Create data directories:
       - `mkdir -p data/duckdb`
       - `mkdir -p data/lancedb`
    
    4. Verify all tiers initialize on startup:
       - Run: `pnpm dev`
       - Check logs for:
         - "DuckDB initialized"
         - "LanceDB initialized"
         - "Neo4j semantic_facts connected"
         - "Neo4j temporal_memory connected"
         - "Python bridge started"
    
    5. Fix any TypeScript errors that prevent app from starting.
  </action>
  <verify>
    Run: `pnpm dev`
    Expected: App starts, logs show all storage tiers initialized
    
    Run: `curl http://localhost:3000/api/v1/health/storage`
    Expected: JSON with status for all 5 tiers (even if some show "disconnected")
    
    Test MCP: `storage_health` tool
    Expected: Returns status object for all tiers
  </verify>
  <done>
    App starts successfully. All 5 storage tiers initialize. Health checks passing. MCP tools working. Phase 1 complete.
  </done>
</task>

</tasks>

<verification>
[ ] `pnpm dev` starts without blocking TypeScript errors
[ ] App logs show: DuckDB initialized, LanceDB initialized, Neo4j connected, Python bridge started
[ ] GET /api/v1/health/storage returns status for all 5 tiers
[ ] MCP tool `storage_health` returns complete status
[ ] Old PostgreSQL code archived (not deleted)
[ ] TrinityRouter coordinates multi-tier writes
[ ] Python bridge serves NLP requests
</verification>

<success_criteria>
- Zero TypeScript errors blocking storage code
- All 5 storage tiers report healthy on startup
- DuckDB staging tables created (ingestion_log, normalized_messages)
- LanceDB collections created (raw_binaries, embeddings)
- Neo4j dual databases configured (semantic_facts, temporal_memory)
- Python bridge running with spaCy and sentence-transformers
- MCP tools expose storage status and initialization
- Foundation ready for Phase 2 (pipelines)
</success_criteria>

<output>
After completion, create `.planning/phases/01-foundation/01-01-SUMMARY.md`

Summary should include:
- Which storage tiers are operational
- Any TypeScript errors deferred (non-blocking)
- Python bridge status
- Next steps for Phase 2
</output>
