# dial-stack Architecture

> This document is the current architecture reference for active work. Historical or superseded material belongs under `docs/wiki/archive/`.

## Status Model

This document distinguishes:

- `implemented` - present in active code
- `partial` - present but incomplete or uneven
- `planned` - intended direction, not yet complete
- `historical` - preserved for context, not active truth

## Executive Summary

`dial-stack` is an evidence-first forensic processing platform organized as a collection of reusable tools rather than a single monolith. The current architecture direction is:

- `ContextForge` as the main ingress and gateway layer
- `DIAL` as an internal orchestration and chat surface
- federated MCP servers for parsing, storage operations, Semantica, and utilities
- multi-tier storage with distinct forensic and analytical roles
- atomic tools and workflows-as-tools available to both UI and LLM consumers

The most important design constraint is proper evidence handling. Every useful feature is subordinate to preserving integrity, provenance, and traceability.

## Guiding Principles

1. Evidence handling comes before convenience, speed, or UI polish.
2. First touch must preserve source truth, hash, UUID linkage, and provenance.
3. Tools are the core platform unit.
4. Workflows are also tools.
5. Reuse existing proven components where possible.
6. Archive stale docs instead of deleting context.
7. Distinguish current reality from planned direction at all times.

## Architecture State

### Implemented or Partially Implemented

- TS MCP server for parser/storage-adjacent tooling
- Python MCP server for Semantica, workflow tools, and audit hooks
- DuckDB service code for intake-stage forensic handling
- PostgreSQL schema/init scripts for normalized evidence and app data
- workflow configuration and runtime-modifiable workflow tooling in Python

### Active Direction, Not Fully Integrated Yet

- ContextForge as primary ingress
- DIAL as internal orchestration/chat instead of central public gateway
- tighter tool registry/discovery patterns
- cleaner evidence-safe end-to-end message pipeline
- wiki-first documentation canon

## Core Surfaces

### ContextForge

**Role**: main ingress and gateway direction  
**State**: planned / architecture-driving

Expected responsibilities:

- gateway / ingress
- protocol mediation
- policy and plugin execution
- auth-adjacent integration
- tool exposure for external-facing consumers

Important rule:

- ContextForge should govern and enrich flows without corrupting evidence-safe processing.

### DIAL

**Role**: internal orchestration and chat  
**State**: partial direction

Expected responsibilities:

- internal chat surface
- multi-tool coordination
- operator/developer workflows
- optional internal orchestration for composite tasks

Important rule:

- DIAL is not the canonical public ingress assumption anymore.

### UI Surfaces

**Role**: operator-facing or analyst-facing views  
**State**: mixed / partial

Potential consumers:

- DIAL chat
- React/CopilotKit-style analyst UI
- future admin or evidence review surfaces

Important rule:

- UI surfaces should consume tool capabilities, not re-create business logic ad hoc.

## Tool Model

The platform is tool-first.

### Atomic Tools

Examples:

- `parse_sms_xml`
- parser and writer tools in TS MCP
- Semantica and graph tools in Python MCP
- format and adapter utilities

### Workflow Tools

Workflows are composite tools assembled from atomic tools.

Requirements:

- configurable
- callable
- inspectable
- reusable by UI, LLM, or orchestration layers
- able to evolve without rewriting core services

Current implementation anchor:

- `mcp-servers/py-mcp-server/src/tools/workflow_tools.py`
- `mcp-servers/py-mcp-server/config/workflows.json`

## Storage Architecture

### DuckDB

**Role**: first-touch forensic staging  
**State**: implemented / partial integration

Responsibilities:

- intake-stage hashing
- dedup support
- UUID linkage support
- forensic staging / master-clock style tracking

### PostgreSQL

**Role**: canonical normalized evidence and app data  
**State**: implemented / partial integration

Responsibilities:

- normalized evidence records
- conversations, messages, app tables
- durable relational querying
- cross-tier linkage anchors

### Neo4j

**Role**: graph, provenance, relationships  
**State**: partial

Responsibilities:

- entity and relationship structures
- temporal graph structures
- provenance-oriented graph representation

### LanceDB

**Role**: embeddings and semantic retrieval  
**State**: partial

Responsibilities:

- vector search
- embedding storage
- semantic retrieval support

### Tier Semantics

Ignore stale tier-numbering conflicts in older docs when they contradict current role definitions. The important truth is the storage responsibility, not the legacy numbering label.

## Evidence Handling Pipeline

### Current Best Pipeline Reading

1. Source evidence arrives.
2. Format/parser selection occurs.
3. First-touch evidence handling occurs in DuckDB-oriented intake flow.
4. Hashing, linkage, and provenance anchors are established.
5. Normalized relational records are written to PostgreSQL.
6. Initial analysis runs.
7. Downstream analytical representations are written to Neo4j and LanceDB as needed.

### Critical Rules

- Do not mutate source truth during intake.
- Do not let enrichment silently overwrite first-touch evidence facts.
- Preserve exact source references and source content lineage.
- Downstream outputs must remain attributable to source evidence.

## MVP Scope

### Inputs

- `SMS XML` first
- `Facebook JSON` first
- iMessage after the core message path is stable

### MVP Success Path

`source evidence -> parse -> first-touch evidence handling -> normalized storage -> Semantica + first-pass analysis -> traceable outputs`

### MVP Analysis

- NER
- sentiment
- abuse screening

### Explicitly Deferred

- contradiction detection
- broader hindsight analysis
- deep cross-dataset synthesis

## Semantica

**Role**: MVP-critical analysis backbone  
**State**: implemented / partial hardening

Semantica is the current backbone for:

- NER
- graph-oriented enrichment
- relationship and temporal analysis support
- downstream analytical structure building

Architecture rule:

- gateway/plugin layers should not interfere with Semantica’s ability to operate on evidence-critical paths.

## Data Governance and Provenance

Evidence-safe processing requires:

- first-touch hashing
- stable identifiers
- source linkage
- immutable first-pass semantics
- recorded provenance
- no misleading “analysis detached from source” outputs

If a feature weakens any of the above, it is architecturally wrong even if it is technically convenient.

## Reuse Strategy

Default preference order:

1. existing trusted local tools
2. proven OSS components
3. thin wrappers/adapters
4. custom code only where evidence handling, orchestration, or case-specific analysis requires it

## Documentation Policy

### Canonical Current Truth

- `docs/.audit/2026-03-30-source-classification.md`
- this file
- `docs/plans/ROADMAP.md`
- `docs/memory/MEMORY.md`
- `docs/wiki/skills/orchestration/contextforge/`

### Historical Lookup

- `docs/wiki/archive/`

## Known Tensions

1. Some root or older docs still present DIAL as the central gateway.
2. Some older docs still prioritize Facebook HTML over Facebook JSON.
3. Some docs blur implemented and planned capabilities.
4. Some code paths still use brittle dispatch patterns where registry/discovery patterns are intended.
5. Some custom analytical detectors remain placeholders.

These tensions should be resolved in favor of the source-classification note, corrected sprint roadmap, and actual code reality.

## Last Updated

2026-03-30
