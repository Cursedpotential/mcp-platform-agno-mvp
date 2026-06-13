# ContextForge Integration Guide

## Overview

ContextForge (IBM) is a backend MCP Gateway that orchestrates AI tools through a plugin pipeline system.

## Wiki Pages

| Page | Description |
|------|-------------|
| [OVERVIEW.md](OVERVIEW.md) | ContextForge architecture and components |
| [PRELIMINARY_SCANNING.md](PRELIMINARY_SCANNING.md) | Initial codebase analysis |
| [PROPOSED_ARCHITECTURE.md](PROPOSED_ARCHITECTURE.md) | Integration architecture |
| [IMPLEMENTATION_ANALYSIS.md](IMPLEMENTATION_ANALYSIS.md) | Implementation details |

## Key Components

### Plugin Pipeline
```
Request → pre_invoke → Plugin Chain → post_invoke → Response
```

### Plugins (40+)
- `pii_filter` - PII detection and redaction
- `secrets_detection` - Credential/secret detection
- `content_moderation` - Content safety checks
- `rate_limiter` - Rate limiting per user/tenant
- `cached_tool_result` - Response caching

### Services
| Service | Purpose |
|---------|---------|
| `gateway_service.py` | Main MCP gateway |
| `a2a_service.py` | Agent-to-agent communication |
| `grpc_service.py` | gRPC protocol handling |
| `tool_service.py` | Tool registration and routing |
| `auth.py` | Authentication and authorization |

### OpenTelemetry Integration
- Chain-of-custody audit trails
- Request tracing across plugins
- Performance metrics

## Integration with Dial-Stack

### Use Cases
1. **MCP Gateway** - Route calls through ContextForge plugin pipeline
2. **PII Filtering** - Filter forensic evidence content before storage
3. **Rate Limiting** - Control API call volume
4. **Audit Logging** - OpenTelemetry spans for custody tracking

### Configuration
```yaml
# mcp-gateway-config.yaml
gateway:
  type: contextforge
  endpoint: http://contextforge:8080
  plugins:
    - pii_filter
    - secrets_detection
    - rate_limiter
  telemetry:
    enabled: true
    endpoint: http://otel-collector:4318
```

## Resources

- **GitHub**: https://github.com/IBM/contextforge
- **Docs**: https://contextforge.ibm.com/docs
- **OpenTelemetry**: https://opentelemetry.io/docs

## Related

- [MCP Protocol](../mcp-protocol.md) - Model Context Protocol
- [WunderGraph Cosmo](../wundergraph-cosmo.md) - GraphQL federation
- [Dial-Stack Architecture](../../../../docs/ARCHITECTURE.md) - System architecture