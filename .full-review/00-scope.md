# Review Scope

## Target

Overall functionality and ability to ingest knowledge as mvp

## Files

- server/agents/ingestion_orchestrator.py
- server/agents/ingestion.py
- server/tools/parsers/ (all parser files)
- server/evidence/normalize.py
- server/core/embedder.py
- server/core/reranker.py
- server/agents/document_digest.py
- server/tools/gateway/
- deploy/
- docker/
- scripts/
- server/agents/analysis_orchestrator.py
- server/agents/review_gatekeeper.py
- server/agents/project_pal.py
- server/agents/dev_copilot.py
- server/agents/forensic_data_agent.py
- server/contracts/records.py
- knowledge/ (knowledge base)
- docs/ (documentation)

## Flags

- Security Focus: no
- Performance Critical: no
- Strict Mode: no
- Framework: auto-detected (Agno AgentOS with FastAPI)

## Review Phases

1. Code Quality & Architecture
2. Security & Performance
3. Testing & Documentation
4. Best Practices & Standards
5. Consolidated Report