# Alpha Repository: Complete Tool Inventory

**Repository:** https://github.com/Cursedpotential/mcp-tool-platform
**Architecture:** Monolithic TypeScript/Node.js with tRPC API
**Total Tools:** 67 identifiable components | **Working:** 45 | **Partial:** 15 | **Broken:** 7

## By Category

### 1. Core Infrastructure (7 tools)
| Tool | File | Status | Porting Priority |
|------|------|--------|------------------|
| MCP Gateway API | `gateway.ts` | ✅ | P2 — DIAL Core replaces this in current |
| Python Bridge | `python-bridge.ts` | ⚠️ | NOT NEEDED — Py MCP server is standalone |
| Plugin Registry | `registry.ts` | ✅ | P2 — current uses FastMCP native registration |
| Task Executor | `workers/executor.ts` | ✅ | P3 — current doesn't have background workers yet |
| Redis Queue | `queue/redis-queue.ts` | ✅ | P3 — queue system not started in current |
| MCP Proxy | `proxy/mcp-proxy.ts` | ⚠️ | P3 — for external MCP servers |
| MCP Config Import | `proxy/mcp-config-import.ts` | ⚠️ | P3 |

### 2. Document Processing (3 tools) — HIGH VALUE
| Tool | File | Status | Porting Priority |
|------|------|--------|------------------|
| **Pandoc converter** | `plugins/document-processors.ts` | ✅ | **P1** — JS MCP server needs this |
| **OCR (Tesseract)** | `plugins/ocr.ts` | ✅ | **P1** — JS MCP server needs this |
| Format converter | `plugins/format-converter.ts` | ✅ | P2 |

### 3. NLP Pipeline (3 tools) — HIGH VALUE
| Tool | File | Status | Porting Priority |
|------|------|--------|------------------|
| **NLP Plugin** (lang detect, NER, keywords, sentiment, toxicity) | `plugins/nlp.ts` (748 lines) | ✅ | **P1** — partially in Py server, needs completion |
| **BERT Sentiment** | `plugins/bert-sentiment.ts` | ⚠️ | P2 — needs ONNX runtime |
| Text miner | `plugins/text-miner.ts` | ✅ | P2 — utility functions |

### 4. Search & Retrieval (4 tools)
| Tool | File | Status | Porting Priority |
|------|------|--------|------------------|
| ripgrep/ugrep search | `plugins/search.ts` | ✅ | P2 — different search in current |
| Content retrieval | `plugins/retrieval.ts` | ✅ | P2 — Directus in current |
| **ChromaDB vector DB** | `plugins/vector-db.ts` | ✅ | P2 — current uses LanceDB instead |
| Vector store abstraction | `plugins/vector-store.ts` | ✅ | P2 — different abstraction in current |

### 5. ML & AI (6 tools)
| Tool | File | Status | Porting Priority |
|------|------|--------|------------------|
| ML inference wrapper | `plugins/ml.ts` | ⚠️ | P3 |
| Summarization | `plugins/summarization.ts` | ⚠️ | P2 — uses LLM API |
| Browser search (Tavily) | `plugins/browser-search.ts` | ⚠️ | P3 — external API |
| LangGraph | `plugins/langgraph-plugin.ts` | ⚠️ | P3 — workflow engine |
| LlamaIndex RAG | `plugins/llamaindex.ts` | ⚠️ | P3 — RAG integration |
| Neo4j graph | `plugins/graph-db.ts` | ⚠️ | P2 — Py server has neo4j tools |

### 6. Forensics (6 tools) — CRITICAL, UNIQUE VALUE
| Tool | File | Status | Porting Priority |
|------|------|--------|------------------|
| **Chain of custody** (SHA-256) | `forensics/chain-custody.ts` | ✅ | **P1** — in DuckDB vault, needs expansion |
| Forensics router | `forensics/forensics-router.ts` | ✅ | P2 — tRPC specific |
| **HurtLex fetcher** | `forensics/hurtlex-fetcher.ts` | ✅ | **P1** — Py server needs this (PY-006) |
| **HurtLex stream** | `forensics/hurtlex-stream.ts` | ✅ | **P1** — Py server needs this (PY-006) |
| **Pattern analyzer** | `forensics/pattern-analyzer.ts` | ✅ | **P1** — not ported (PY-005) |
| **Timeline generator** | `forensics/timeline-generator.ts` | ✅ | **P1** — Py server needs this |

### 7. Analysis & Classification (5 tools)
| Tool | File | Status | Porting Priority |
|------|------|--------|------------------|
| General classifier | `analysis/classifier.ts` | ✅ | P2 |
| **Conversation segmentation** | `analysis/conversation-segmentation.ts` | ✅ | **P1** — needed for evidence parsing |
| Multi-pass classifier | `analysis/multi-pass-classifier.ts` | ✅ | P2 |
| NLP classifier | `analysis/nlp-classifier.ts` | ✅ | P2 |
| Priority screener | `analysis/priority-screener.ts` | ✅ | P2 |

### 8. Evidence Parsers (10 tools) — CRITICAL
| Tool | File | Status | Porting Priority |
|------|------|--------|------------------|
| Base loader interface | `loaders/base-loader.ts` | ✅ | P1 — define common interface |
| **SMS loader** | `loaders/sms-loader.ts` | ✅ | DONE — in TS MCP server |
| **SMS XML parser** | `loaders/xml-sms-parser.ts` | ✅ | DONE — in TS MCP server |
| **Facebook parser** | `loaders/facebook-parser.ts` | ✅ | **P0** — code exists in current but BLOCKED |
| **iMessage PDF parser** | `loaders/pdf-imessage-parser.ts` | ✅ | **P0** — stub in current, needs port |
| Unstructured loader | `loaders/unstructured-loader.ts` | ✅ | P2 |
| Lexicon importer | `loaders/lexicon-importer.ts` | ✅ | P2 |
| Document hierarchy | `loaders/document-hierarchy.ts` | ✅ | P2 |
| Embedding pipeline | `loaders/embedding-pipeline.ts` | ✅ | P2 — Py server has this |
| Real embedding service | `loaders/real-embedding-service.ts` | ✅ | P2 — Py server has this |

### 9. Storage Backends (6 tools)
| Tool | File | Status | Porting Priority |
|------|------|--------|------------------|
| ChromaDB client | `storage/chroma-client.ts` | ✅ | P2 — current uses LanceDB |
| Directus client | `storage/directus-client.ts` | ✅ | P2 — in docker-compose |
| Graphiti/Neo4j | `storage/graphiti-client.ts` | ⚠️ | P2 — Py server has neo4j tools |
| pgvector client | `storage/pgvector-client.ts` | ✅ | DONE — in current |
| Storage index | `storage/index.ts` | ✅ | P2 — different in current |
| System router | `storage/systemRouter.ts` | ✅ | P2 — tRPC specific |

### 10. HITL (1 tool)
| Tool | File | Status | Porting Priority |
|------|------|--------|------------------|
| Approval workflow | `hitl/approval.ts` | ✅ | DONE — review_queue in TS MCP server |

### 11. Export Tools (~3 tools)
| Tool | File | Status | Porting Priority |
|------|------|--------|------------------|
| Export directory | `export/` | ⚠️ | P2 — not started in current |

### 12. Library Utilities (6 tools)
| Tool | File | Status | Porting Priority |
|------|------|--------|------------------|
| Cheerio, XML, JSON5, YAML, CSV, Natural.js | `plugins/library-tools.ts` | ✅ | P2 — utility wrappers |
| Filesystem | `plugins/filesystem.ts` | ✅ | P3 — basic ops |
| Diff | `plugins/diff.ts` | ✅ | P3 — text diffing |
| Rules engine | `plugins/rules.ts` | ✅ | P3 — conditional processing |
| Schema resolver | `plugins/schema-resolver.ts` | ✅ | P2 — type inference |
| Python tools | `plugins/python-tools.ts` | ⚠️ | NOT NEEDED — Py server replaces |

### 13. Observability (2 tools)
| Tool | File | Status | Porting Priority |
|------|------|--------|------------------|
| Stats collector | `stats/collector.ts` | ✅ | P2 — needs port |
| Observability | `observability/` | ⚠️ | P3 — not started |

### 14. GCP Plugins (7 tools) — ALL BROKEN
| Tool | File | Status | Porting Priority |
|------|------|--------|------------------|
| Document AI | `plugins-pending/gcp-document-ai.ts` | ❌ | DEFERRED — cloud API, needs per-engine approval |
| Natural Language | `plugins-pending/gcp-natural-language.ts` | ❌ | DEFERRED |
| Speech-to-Text | `plugins-pending/gcp-speech.ts` | ❌ | DEFERRED |
| Video Intelligence | `plugins-pending/gcp-video-intelligence.ts` | ❌ | DEFERRED |
| Vision | `plugins-pending/gcp-vision.ts` | ❌ | DEFERRED |
