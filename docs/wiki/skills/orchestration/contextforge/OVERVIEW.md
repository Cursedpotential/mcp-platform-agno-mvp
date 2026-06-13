---
title: IBM ContextForge MCP Gateway
version: 1.0.0
created: 2026-03-16 16:31
modified: 2026-03-16 16:31
author: thinking@opencode
project: dial-stack
status: draft
---

# IBM ContextForge MCP Gateway

## Overview

**ContextForge** is an open source registry and proxy that federates MCP servers, A2A agents, and REST/gRPC APIs into one clean endpoint for AI clients. It provides centralized governance, discovery, and observability across AI infrastructure.

**Repository**: https://github.com/IBM/mcp-context-forge  
**PyPI**: `mcp-contextforge-gateway`  
**Docker**: `ghcr.io/ibm/mcp-context-forge:1.0.0-RC-2`

---

## Key Features

### 1. Multi-Protocol Federation
- **MCP Gateway**: Federate any MCP server
- **A2A Integration**: Agent-to-Agent protocol, OpenAI/Anthropic agent routing
- **REST-to-MCP**: Adapt REST APIs into MCP tools with JSON Schema extraction
- **gRPC-to-MCP**: Automatic service discovery via reflection protocol

### 2. Transports Supported
- HTTP
- JSON-RPC
- WebSocket
- SSE (Server-Sent Events with configurable keepalive)
- stdio
- streamable-HTTP

### 3. Plugin Extensibility (40+ Plugins)
| Plugin Category | Examples |
|----------------|-----------|
| **Security** | `pii_filter`, `secrets_detection`, `code_safety_linter`, `virus_total_checker` |
| **Content** | `content_moderation`, `harmful_content_detector`, `html_to_markdown`, `markdown_cleaner` |
| **Performance** | `cached_tool_result`, `response_cache_by_prompt`, `rate_limiter`, `retry_with_backoff` |
| **Monitoring** | `tools_telemetry_exporter`, `watchdog`, `webhook_notification` |
| **Transformation** | `toon_encoder`, `summarizer`, `json_repair`, `timezone_translator` |
| **Integration** | `vault`, `url_reputation`, `robots_license_guard`, `unified_pdp` |

### 4. Observability
- **OpenTelemetry** (OTLP protocol)
- **Backends**: Phoenix (LLM-focused), Jaeger, Zipkin, Tempo, DataDog, New Relic
- **Metrics**: Token usage, costs, model performance
- **Distributed tracing** across federated gateways

### 5. Admin UI
- Built with HTMX + Alpine.js
- Real-time log viewer with filtering/search/export
- Airgapped deployment support
- Auth: Basic, JWT, OAuth, custom schemes

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        ContextForge Gateway                      │
│                                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │   MCP    │  │   A2A    │  │   REST   │  │      gRPC        │  │
│  │  Server  │  │  Agent   │  │   API    │  │    Service       │  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────────┬─────────┘  │
│       │            │             │                  │            │
│  ┌────▼────────────▼─────────────▼──────────────────▼─────────┐  │
│  │                    Protocol Translation                     │  │
│  │   REST-to-MCP  │  gRPC-to-MCP  │  stdio wrapper             │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │                     Plugin Pipeline                         │  │
│  │  pii_filter → content_moderation → rate_limiter → cache    │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │                   Observability Layer                       │  │
│  │  OpenTelemetry → Phoenix/Jaeger/Zipkin                     │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────┐  ┌──────────────────┐  ┌────────────────┐  │
│  │   Admin UI       │  │  Auth Layer      │  │  Redis Cache  │  │
│  │  HTMX + Alpine   │  │  Basic/JWT/OAuth │  │  Federation   │  │
│  └──────────────────┘  └──────────────────┘  └────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Integration with Dial-Stack

### Relevance to Evidence Analysis Platform

ContextForge is **highly relevant** for our dial-stack architecture:

| Feature | Dial-Stack Use Case |
|---------|---------------------|
| **Tool Federation** | Unify all forensic tools under single MCP endpoint |
| **Plugin Pipeline** | Apply `pii_filter`, `content_moderation`, `secrets_detection` to all evidence |
| **gRPC-to-MCP** | Wrap existing gRPC-based forensic services (if any) |
| **OpenTelemetry** | Chain-of-custody audit trail across all tool invocations |
| **Admin UI** | Evidence processing dashboard with real-time logs |
| **Caching** | Cache repeated analysis results (hash-based) |

### Potential Integration Points

1. **Wrap Python MCP Server**
   ```yaml
   # ContextForge configuration
   servers:
     - name: evidence-tools
       transport: stdio
       command: uv run --directory ./mcp-servers/py-mcp-server mcp-server
       tools:
         - dpk_hap_score
         - dpk_pii_redact
         - user_behavioral_detection
         - fingerprint_voice
   ```

2. **Plugin Integration**
   ```yaml
   plugins:
     - name: pii_filter
       enabled: true
       config:
         patterns:
           - ssn
           - credit_card
           - email
     - name: secrets_detection
       enabled: true
       config:
         scan_binary: false
   ```

3. **Observability Configuration**
   ```yaml
   observability:
     otlp_endpoint: http://phoenix:4317
     service_name: dial-stack-evidence
     traces:
       - evidence_ingestion
       - evidence_processing
       - evidence_analysis
       - chain_of_custody
   ```

---

## Deployment Options

### Option 1: PyPI Installation (Recommended for Development)

```bash
# Install
pip install mcp-contextforge-gateway

# Run with environment variables
BASIC_AUTH_PASSWORD=pass \
MCPGATEWAY_UI_ENABLED=true \
MCPGATEWAY_ADMIN_API_ENABLED=true \
PLATFORM_ADMIN_EMAIL=admin@example.com \
PLATFORM_ADMIN_PASSWORD=changeme \
uvx --from mcp-contextforge-gateway mcpgateway --host 0.0.0.0 --port 4444
```

### Option 2: Docker Compose (Recommended for Production)

```yaml
# docker-compose.yml excerpt
services:
  mcpgateway:
    image: ghcr.io/ibm/mcp-context-forge:1.0.0-RC-2
    ports:
      - "4444:4444"
    environment:
      - BASIC_AUTH_PASSWORD=pass
      - MCPGATEWAY_UI_ENABLED=true
      - MCPGATEWAY_ADMIN_API_ENABLED=true
    volumes:
      - ./mcp-catalog.yml:/app/mcp-catalog.yml
```

### Option 3: Kubernetes (Multi-Cluster)

- Redis-backed federation
- Multi-cluster service discovery
- Horizontal scaling

---

## Codebase Structure

```
mcp-context-forge/
├── mcpgateway/                    # Core gateway implementation
│   ├── main.py                    # FastAPI app (348KB)
│   ├── admin.py                   # Admin UI (809KB)
│   ├── db.py                      # Database layer (277KB)
│   ├── schemas.py                 # Pydantic models (323KB)
│   ├── config.py                  # Configuration (126KB)
│   ├── translate.py               # Protocol translation (100KB)
│   ├── translate_grpc.py          # gRPC-to-MCP translation (21KB)
│   ├── auth.py                    # Auth layer (62KB)
│   ├── observability.py           # OpenTelemetry (22KB)
│   ├── wrapper.py                 # stdio wrapper (25KB)
│   ├── services/                  # Business logic
│   ├── handlers/                  # Request handlers
│   ├── routers/                   # FastAPI routers
│   ├── transports/                # Transport implementations
│   ├── middleware/                # HTTP middleware
│   └── plugins/                   # Plugin infrastructure
├── plugins/                       # 40+ built-in plugins
│   ├── pii_filter/
│   ├── secrets_detection/
│   ├── content_moderation/
│   ├── rate_limiter/
│   ├── cached_tool_result/
│   └── ... (40+ more)
├── mcp-servers/                   # Example MCP servers
│   └── python/data_analysis_server/
├── tests/                         # Test suite (400+ tests)
├── docs/                           # Documentation
│   └── docs/                       # Published to GitHub Pages
├── charts/                        # Kubernetes Helm charts
├── mcp-catalog.yml                # Tool/server catalog
├── docker-compose.yml             # Full stack compose
└── Makefile                       # Build/dev commands
```

---

## Key Files for Evidence Platform

### 1. Plugin Pipeline (`plugins/config.yaml`)
**Purpose**: Configure plugin execution order
**Relevance**: Define forensics-specific plugin pipeline

```yaml
plugins:
  pipeline:
    - name: pii_filter
      priority: 100
    - name: secrets_detection
      priority: 90
    - name: content_moderation
      priority: 80
    - name: rate_limiter
      priority: 70
```

### 2. Tool Catalog (`mcp-catalog.yml`)
**Purpose**: Register MCP servers and tools
**Relevance**: Register all dial-stack tools

```yaml
servers:
  - name: evidence-tools
    description: Forensic evidence analysis tools
    tools:
      - dpk_hap_score
      - dpk_pii_redact
      - user_behavioral_detection
```

### 3. Observability (`mcpgateway/observability.py`)
**Purpose**: OpenTelemetry integration
**Relevance**: Chain-of-custody audit trail

### 4. Auth (`mcpgateway/auth.py`)
**Purpose**: Authentication/authorization
**Relevance**: Secure evidence platform access

### 5. Plugin Infrastructure (`mcpgateway/plugins/`)
**Purpose**: Plugin loading/execution
**Relevance**: Build custom forensic plugins

---

## Plugin Development Guide

### Creating a Custom Plugin

```python
# plugins/evidence_hash/plugin.py
from mcpgateway.plugins import Plugin, PluginContext

class EvidenceHashPlugin(Plugin):
    """Hash all evidence before/after processing."""
    
    name = "evidence_hash"
    priority = 50
    
    async def pre_invoke(self, context: PluginContext) -> PluginContext:
        # Hash input evidence
        context.metadata["input_hash"] = self._hash_evidence(context.input)
        return context
    
    async def post_invoke(self, context: PluginContext) -> PluginContext:
        # Hash output evidence
        context.metadata["output_hash"] = self._hash_evidence(context.output)
        return context
    
    def _hash_evidence(self, data: bytes) -> str:
        import hashlib
        return hashlib.sha256(data).hexdigest()
```

### Plugin Configuration

```yaml
# plugins/evidence_hash/config.yaml
name: evidence_hash
description: Hash evidence before/after processing
version: 1.0.0
priority: 50
hooks:
  - pre_invoke
  - post_invoke
config:
  algorithm: sha256
  store_in_metadata: true
```

---

## Comparison with Dial-Stack Architecture

| Aspect | Dial-Stack (Current) | ContextForge Integration |
|--------|----------------------|--------------------------|
| **Tool Gateway** | Direct MCP server | Federated MCP gateway |
| **Audit Trail** | Custom decorator | OpenTelemetry + plugins |
| **Plugin System** | Manual | Automated pipeline |
| **Transports** | stdio only | HTTP/WS/SSE/stdio/gRPC |
| **Auth** | Basic (optional) | Basic/JWT/OAuth/custom |
| **Observability** | Custom logging | OTLP + backends |
| **Caching** | None | Redis-backed |
| **Admin UI** | None | HTMX dashboard |

---

## Next Steps for Integration

### Phase 1: Research (Current)
- [x] Repository cloned and analyzed
- [x] Architecture documented
- [x] Plugin system understood
- [ ] Integration points identified
- [ ] Performance overhead measured

### Phase 2: POC
- [ ] Deploy ContextForge locally
- [ ] Wrap dial-stack MCP server
- [ ] Configure evidence hash plugin
- [ ] Test OpenTelemetry integration
- [ ] Benchmark performance

### Phase 3: Production
- [ ] Docker Compose configuration
- [ ] Kubernetes deployment (if needed)
- [ ] Redis federation setup
- [ ] Phoenix/Jaeger integration
- [ ] Admin UI customization

---

## Resources

- **Official Docs**: https://ibm.github.io/mcp-context-forge/
- **GitHub**: https://github.com/IBM/mcp-context-forge
- **PyPI**: https://pypi.org/project/mcp-contextforge-gateway/
- **Docker Hub**: ghcr.io/ibm/mcp-context-forge
- **Roadmap**: https://ibm.github.io/mcp-context-forge/architecture/roadmap/

---

## Questions to Resolve

1. **Performance Overhead**: What's the latency impact of the plugin pipeline?
2. **Plugin Customization**: Can we extend existing plugins or must we create new?
3. **Evidence Hash Plugin**: Does `cached_tool_result` suffice or do we need custom?
4. **MCP Version Support**: Does it support MCP protocol `2025-06-18`?
5. **Multi-Tenant**: Can we isolate evidence by case/user?
6. **Airgapped**: Does admin UI work without internet for Sensitive Compartmented Information Facilities (SCIF)?

---

## References

- (source: ContextForge README, GitHub repo analysis)
- (source: dial-stack AGENTS.md)
- (context: mem0)