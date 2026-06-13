---
title: ContextForge Implementation Analysis for Dial-Stack
version: 1.0.0
created: 2026-03-16 17:00
modified: 2026-03-16 17:00
author: thinking@opencode
project: dial-stack
status: draft
---

# ContextForge Implementation Analysis for Dial-Stack

## Executive Summary

This document provides a comprehensive analysis of IBM ContextForge's features relevant to dial-stack's evidence analysis platform, with detailed implementation options for each capability.

---

## 1. Feature Relevance Matrix

| Feature Category | ContextForge Capability | Dial-Stack Relevance | Implementation Priority |
|-----------------|------------------------|---------------------|------------------------|
| **Abuse/Hate Detection** | `content_moderation`, `harmful_content_detector` | HIGH - Evidence analysis, custody disputes | P1 |
| **Entity Detection** | PII filter patterns, entity extraction | HIGH - Evidence processing | P1 |
| **Secrets Detection** | `secrets_detection` plugin | HIGH - Credential/PII redaction | P1 |
| **MCP Federation** | Gateway service, multi-server federation | HIGH - Tool unification | P1 |
| **gRPC-to-MCP** | Protocol translation layer | MEDIUM - Legacy service wrapping | P2 |
| **REST-to-MCP** | JSON Schema extraction, adapter | MEDIUM - API integration | P2 |
| **Policy Enforcement** | Cedar, OPA, unified PDP | MEDIUM - Governance | P2 |
| **Observability** | OpenTelemetry, Phoenix, Jaeger | HIGH - Audit trail | P1 |
| **Caching** | Redis-backed, prompt-based | MEDIUM - Performance | P2 |
| **Admin UI** | HTMX dashboard | LOW - Nice to have | P3 |

---

## 2. Abuse & Hate Detection

### 2.1 ContextForge Plugins

#### `content_moderation` Plugin
**Location**: `plugins/content_moderation/`

**Capabilities**:
- **Categories**: Hate, violence, sexual, self-harm, harassment, spam, profanity, toxic content
- **Providers**: IBM Watson, IBM Granite Guardian, OpenAI, Azure, AWS
- **Actions**: BLOCK, WARN, REDACT, TRANSFORM
- **Offline Mode**: Regex-based fallback when API unavailable

**Configuration**:
```yaml
plugins:
  - name: "ContentModerationPlugin"
    kind: "plugins.content_moderation.content_moderation.ContentModerationPlugin"
    hooks: ["prompt_pre_fetch", "tool_post_invoke"]
    mode: "enforce"
    priority: 60
    config:
      provider: "granite"  # or watson, openai, azure, aws
      categories:
        - hate
        - violence
        - harassment
        - self_harm
      action: "warn"  # block, warn, redact, transform
      threshold: 0.7
      offline_fallback: true
```

#### `harmful_content_detector` Plugin
**Location**: `plugins/harmful_content_detector/`

**Capabilities**:
- Keyword lexicons for self-harm, violence, hate speech
- Pattern-based detection (no API required)
- Customizable word lists

**Configuration**:
```yaml
plugins:
  - name: "HarmfulContentDetectorPlugin"
    kind: "plugins.harmful_content_detector.harmful_content_detector.HarmfulContentDetectorPlugin"
    hooks: ["tool_pre_invoke", "tool_post_invoke"]
    mode: "permissive"
    priority: 55
    config:
      lexicons:
        - self_harm
        - violence
        - hate
      custom_words: []
      action: "flag"
```

### 2.2 Dial-Stack Integration Options

#### Option A: Replace Current Detection (Full ContextForge)
**Approach**: Run all evidence through ContextForge gateway

**Pros**:
- Unified plugin pipeline
- Built-in caching
- Centralized governance

**Cons**:
- Additional latency
- New dependency
- Complex deployment

**Implementation**:
```yaml
# ContextForge config for dial-stack
servers:
  - name: evidence-tools
    transport: stdio
    command: uv run --directory ./mcp-servers/py-mcp-server mcp-server
    
plugins:
  - name: ContentModerationPlugin
    enabled: true
    config:
      provider: granite
      categories: [hate, violence, harassment]
```

#### Option B: Side-by-Side (Hybrid)
**Approach**: Keep current tools, add ContextForge for specific workflows

**Pros**:
- Minimal disruption
- Gradual migration
- Can compare results

**Cons**:
- Duplicate infrastructure
- Complexity in routing

**Implementation**:
```python
# In dial-stack tool
@mcp.tool()
async def analyze_evidence_with_moderation(content: str) -> dict:
    """Analyze evidence with abuse/hate detection."""
    
    # Option 1: Use ContextForge API
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://contextforge:4444/tools/content_moderation",
            json={"content": content}
        )
        moderation_result = response.json()
    
    # Option 2: Use local detection (fallback)
    if not moderation_result:
        from plugins.content_moderation import ContentModerationPlugin
        plugin = ContentModerationPlugin()
        moderation_result = await plugin.detect(content)
    
    return {
        "evidence_analysis": await analyze_content(content),
        "moderation": moderation_result
    }
```

#### Option C: Extract Plugin Logic (Reuse Only)
**Approach**: Copy ContextForge plugin code into dial-stack

**Pros**:
- No new infrastructure
- Full control
- Simpler deployment

**Cons**:
- Manual updates
- No federation benefits
- Maintenance burden

**Implementation**:
```python
# Copy from ContextForge
# File: dial-stack/mcp-servers/py-mcp-server/src/plugins/content_moderation.py

# Adapted from ContextForge plugins/content_moderation/
class ContentModerationPlugin:
    """Abuse/hate detection for evidence."""
    
    CATEGORIES = {
        "hate": HATE_PATTERNS,
        "violence": VIOLENCE_PATTERNS,
        "harassment": HARASSMENT_PATTERNS,
        "self_harm": SELF_HARM_PATTERNS,
    }
    
    def detect(self, text: str) -> dict:
        """Detect abuse/hate in text."""
        results = {}
        for category, patterns in self.CATEGORIES.items():
            matches = self._match_patterns(text, patterns)
            if matches:
                results[category] = matches
        return results
```

### 2.3 Recommended Approach for Dial-Stack

**Recommendation**: **Option B (Hybrid)** for abuse/hate detection

**Rationale**:
1. Evidence analysis needs low latency - keep core tools direct
2. Moderation is optional/enhancement - can be added via ContextForge
3. Allows comparison between approaches
4. Can migrate to Option A if proven valuable

---

## 3. Entity Detection & Recognition

### 3.1 ContextForge PII Filter

**Location**: `plugins/pii_filter/pii_filter.py`

**Detection Patterns**:
```python
PATTERNS = {
    # US Identifiers
    "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
    "itin": r"\b9\d{2}-[7-8]\d-\d{4}\b",
    
    # Financial
    "credit_card_visa": r"\b4\d{12}(\d{3})?\b",
    "credit_card_mastercard": r"\b5[1-5]\d{14}\b",
    "credit_card_amex": r"\b3[47]\d{13}\b",
    
    # Contact
    "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
    "phone_us": r"\b(\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b",
    
    # Network
    "ip_v4": r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",
    "ip_v6": r"\b(?:[A-F0-9]{1,4}:){7}[A-F0-9]{1,4}\b",
    "mac_address": r"\b([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})\b",
    
    # Cloud Credentials
    "aws_access_key": r"\bAKIA[0-9A-Z]{16}\b",
    "aws_secret": r"(?i)aws.{0,20}(?:secret|access).{0,20}=\s*([A-Za-z0-9/+=]{40})",
    "google_api_key": r"\bAIza[0-9A-Za-z\-_]{35}\b",
    "azure_key": r"\b[a-zA-Z0-9]{8}-[a-zA-Z0-9]{4}-[a-zA-Z0-9]{4}-[a-zA-Z0-9]{4}-[a-zA-Z0-9]{12}\b",
    
    # Personal
    "drivers_license": r"\b[A-Z]{1,2}\d{6,8}\b",
    "passport_us": r"\b\d{9}\b",
    
    # Medical
    "medical_record": r"\b[A-Z]{2}\d{6,10}\b",
    "npi_number": r"\b\d{10}\b",
}
```

**Rust Acceleration**:
```python
# ContextForge uses Rust for 5-100x speedup
try:
    from pii_filter_rust import scan_text as rust_scan
    USE_RUST = True
except ImportError:
    USE_RUST = False
```

### 3.2 Entity Types Relevant to Evidence Analysis

| Entity Type | Pattern | Use Case in Evidence |
|-------------|---------|---------------------|
| SSN | `\d{3}-\d{2}-\d{4}` | PII redaction, identity protection |
| Credit Card | `4\d{12,15}` | Financial evidence, fraud detection |
| Email | `[\w.]+@[\w.]+` | Communication analysis, contact mapping |
| Phone | `\+?1?\d{10}` | Call logs, contact analysis |
| IP Address | `\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}` | Digital forensics, geolocation |
| MAC Address | `([0-9A-Fa-f]{2}[:-]){5}...` | Device identification |
| AWS Key | `AKIA[0-9A-Z]{16}` | Credential exposure, security audit |
| Date | Various formats | Timeline construction |

### 3.3 Integration with Dial-Stack

#### Current State (Dial-Stack)
```python
# dial-stack/mcp-servers/py-mcp-server/src/tools/dpk_tools.py
@mcp.tool()
async def dpk_pii_redact(text: str) -> dict:
    """Redact PII from text using DPK."""
    # Uses IBM Data Prep Kit
```

#### Enhanced with ContextForge
```python
# Option 1: Use ContextForge PII filter (more patterns)
@mcp.tool()
async def dpk_pii_redact_enhanced(text: str) -> dict:
    """Redact PII using ContextForge patterns."""
    
    # ContextForge has 40+ patterns vs DPK's ~15
    from mcpgateway.plugins.pii_filter import PIIFilterPlugin
    
    plugin = PIIFilterPlugin()
    plugin.config.detect_ssn = True
    plugin.config.detect_credit_card = True
    plugin.config.detect_email = True
    plugin.config.detect_aws_keys = True  # Not in DPK
    
    result = await plugin.process(text)
    
    return {
        "redacted_text": result.redacted,
        "entities_found": result.entities,
        "entity_count": len(result.entities),
        "patterns_used": result.patterns_matched
    }
```

### 3.4 Custom Entity Patterns for Evidence

**Add forensic-specific patterns**:
```python
# Custom patterns for legal evidence
FORENSIC_PATTERNS = {
    # Case numbers (various formats)
    "case_number": r"\b\d{2}-\d{4}-\d{4,6}\b",  # e.g., 23-1234-567890
    "docket_number": r"\b[CV]\d{2,4}[A-Z]?\d{4,8}\b",  # e.g., CV2023ABC1234
    
    # Legal identifiers
    "bar_number": r"\b\d{6,8}\b",  # Attorney bar numbers
    "court_id": r"\b[A-Z]{2,4}\d{4,8}\b",  # Court identifiers
    
    # Evidence markers
    "exhibit_number": r"\b[Ee]xhibit\s*[A-Z]?\d+\b",
    "bates_number": r"\b[A-Z]{2,4}\d{6,8}\b",  # Bates numbering
    
    # Communication
    "phone_extension": r"\bext\.?\s*\d{3,6}\b",
    "fax_number": r"\b\d{3}-\d{3}-\d{4}\b",
}

# Register with ContextForge
class ForensicPIIPlugin(PIIFilterPlugin):
    """Extended PII detection for legal evidence."""
    
    def __init__(self):
        super().__init__()
        self.patterns.update(FORENSIC_PATTERNS)
```

---

## 4. MCP Federation & Tool Integration

### 4.1 Current Dial-Stack Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ AI DIAL Core (port 8080)                                    │
│   └── OpenAI-compatible API gateway                         │
└─────────────────────────────────────────────────────────────┘
                           │
         ┌─────────────────┼─────────────────┐
         ▼                 ▼                 ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ TS MCP      │    │ Python MCP  │    │ JS MCP      │
│ (port 8081) │    │ (port 8082) │    │ (port 8083) │
└─────────────┘    └─────────────┘    └─────────────┘
```

### 4.2 ContextForge Federation Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ ContextForge Gateway (port 4444)                            │
│   ├── Plugin Pipeline (PII → Moderation → Cache)            │
│   ├── Protocol Translation (REST/gRPC → MCP)                │
│   └── Observability (OpenTelemetry)                         │
└─────────────────────────────────────────────────────────────┘
                           │
         ┌─────────────────┼─────────────────┐
         ▼                 ▼                 ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ TS MCP      │    │ Python MCP  │    │ External    │
│ (stdio)     │    │ (stdio)     │    │ gRPC/REST   │
└─────────────┘    └─────────────┘    └─────────────┘
```

### 4.3 Integration Options

#### Option A: ContextForge as Primary Gateway
```yaml
# ContextForge wraps all dial-stack MCP servers
servers:
  - name: ts-tools
    transport: stdio
    command: node /dial-stack/mcp-servers/ts-mcp-server/dist/index.js
    tools:
      - "*Parser*"
      - "*Writer*"
      
  - name: py-tools
    transport: stdio
    command: uv run --directory /dial-stack/mcp-servers/py-mcp-server mcp-server
    tools:
      - dpk_*
      - user_*
      - fingerprint_*
      
  - name: js-tools
    transport: stdio
    command: node /dial-stack/mcp-servers/js-mcp-server/dist/index.js
    tools:
      - docling_*
      - pandoc_*
```

**DIAL Configuration**:
```json
{
  "dial": {
    "core": {
      "mcp_gateway_url": "http://contextforge:4444"
    }
  }
}
```

#### Option B: Parallel Gateways
```yaml
# DIAL connects to both direct MCP servers AND ContextForge
# Use ContextForge for specific workflows (evidence processing)
# Use direct MCP for low-latency operations (queries)

dial:
  endpoints:
    - name: direct
      url: "http://localhost:8081"  # TS MCP
      tools: ["query*", "list*"]
      
    - name: evidence-processing
      url: "http://contextforge:4444"
      tools: ["dpk_*", "analyze*", "redact*"]
```

#### Option C: ContextForge as Plugin Layer Only
```python
# Use ContextForge plugins WITHOUT the gateway
# Import plugin logic directly into dial-stack

from mcpgateway.plugins.pii_filter import PIIFilterPlugin
from mcpgateway.plugins.content_moderation import ContentModerationPlugin
from mcpgateway.plugins.secrets_detection import SecretsDetectionPlugin

# Apply as middleware in dial-stack MCP server
class EvidenceProcessingMiddleware:
    def __init__(self):
        self.pii_filter = PIIFilterPlugin()
        self.moderation = ContentModerationPlugin()
        self.secrets = SecretsDetectionPlugin()
    
    async def process(self, tool_name: str, args: dict) -> dict:
        # Pre-processing
        if "content" in args:
            args["content"] = await self.pii_filter.redact(args["content"])
            args["content"] = await self.secrets.scan(args["content"])
        
        # Execute tool
        result = await execute_tool(tool_name, args)
        
        # Post-processing
        if result.get("output"):
            moderation = await self.moderation.detect(result["output"])
            if moderation.get("flags"):
                result["moderation_flags"] = moderation["flags"]
        
        return result
```

---

## 5. gRPC & REST Integration

### 5.1 gRPC-to-MCP Translation

**ContextForge Capability**: Wrap gRPC services as MCP tools

**Use Case**: Connect existing gRPC-based forensic services

**Architecture**:
```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│ ContextForge     │────▶│ gRPC Service     │────▶│ Forensic Tool    │
│ Gateway          │     │ (translation)    │     │ (any language)   │
└──────────────────┘     └──────────────────┘     └──────────────────┘
         │                                                │
         └──────────────── MCP Tool Interface ◀───────────┘
```

**Configuration**:
```yaml
# Register gRPC service as MCP tools
grpc:
  - name: forensic-analyzer
    endpoint: localhost:50051
    tls:
      enabled: true
      cert: /path/to/cert.pem
    
    # Auto-discover via reflection
    reflection: true
    
    # Or manually specify
    services:
      - name: EvidenceAnalyzer
        methods:
          - name: AnalyzeDocument
            mcp_tool_name: analyze_document
            mcp_tool_description: "Analyze evidence document"
```

### 5.2 REST-to-MCP Translation

**ContextForge Capability**: Adapt REST APIs as MCP tools

**Use Case**: Integrate external evidence APIs (court records, public databases)

**Configuration**:
```yaml
rest:
  - name: court-records-api
    base_url: https://api.courts.example.com
    auth:
      type: bearer
      token: ${COURT_API_TOKEN}
    
    endpoints:
      - path: /cases/{case_id}
        method: GET
        mcp_tool:
          name: get_case_record
          description: "Retrieve court case by ID"
          parameters:
            case_id:
              type: string
              description: "Case identifier"
              required: true
      
      - path: /search
        method: POST
        mcp_tool:
          name: search_cases
          description: "Search court records"
          parameters:
            query:
              type: object
              properties:
                party_name: string
                date_range: object
```

### 5.3 Integration with Dial-Stack

**Scenario**: Add Michigan court records API

```yaml
# ContextForge config
rest:
  - name: mi-courts
    base_url: https://api.courts.michigan.gov/v1
    auth:
      type: api_key
      header: X-API-Key
      key: ${MI_COURTS_API_KEY}
    
    endpoints:
      - path: /cases/{case_number}
        mcp_tool:
          name: mi_get_case
          description: "Get Michigan court case"
      
      - path: /filings/search
        mcp_tool:
          name: mi_search_filings
          description: "Search Michigan court filings"
```

**Dial-Stack Usage**:
```python
# Tool automatically available through ContextForge
@mcp.tool()
async def get_court_document(case_number: str) -> dict:
    """Retrieve court document from Michigan courts."""
    # This becomes an MCP tool via ContextForge REST adapter
    # No Python code needed - configured via YAML
```

---

## 6. Policy Enforcement (Cedar & OPA)

### 6.1 Cedar Policy Engine

**Location**: `plugins/external/cedar/`

**Purpose**: Fine-grained authorization for evidence access

**Example Policy**:
```cedar
// Evidence access policy
permit(
  principal == User::"analyst",
  action == Action::"read",
  resource == Evidence::"case_123"
) when {
  principal.department == resource.department &&
  principal.clearance_level >= resource.sensitivity_level
};

// Redaction policy for PII
permit(
  principal == User::"external_reviewer",
  action == Action::"read",
  resource == Evidence::"case_123"
) when {
  resource.has_pii == true
} unless {
  context.redacted == false
};
```

**Configuration**:
```yaml
plugins:
  - name: CedarEnginePlugin
    kind: "plugins.external.cedarpolicyplugin.CedarEnginePlugin"
    hooks: ["tool_pre_invoke"]
    mode: "enforce"
    priority: 10  # Run first
    config:
      policies: /app/policies/evidence.cedar
      entities: /app/policies/entities.json
```

### 6.2 Open Policy Agent (OPA)

**Location**: `plugins/external/opa/`

**Purpose**: Policy-as-code for evidence governance

**Example Policy (Rego)**:
```rego
package evidence.access

# Allow analysts to read non-sensitive evidence
allow {
    input.user.role == "analyst"
    input.evidence.sensitivity == "low"
}

# Require supervisor approval for sensitive evidence
allow {
    input.user.role == "analyst"
    input.evidence.sensitivity == "high"
    input.context.has_supervisor_approval == true
}

# Deny access to sealed records
deny {
    input.evidence.status == "sealed"
    input.user.role != "judge"
}
```

### 6.3 Integration with Dial-Stack

**Use Case**: Control access to evidence based on case assignment

```python
# In dial-stack tool
@mcp.tool()
async def get_evidence(evidence_id: str, user: dict) -> dict:
    """Retrieve evidence with policy enforcement."""
    
    # Policy check happens in ContextForge plugin
    # If policy denies, tool never executes
    
    # Policy context:
    # - user.role
    # - user.assigned_cases
    # - evidence.sensitivity
    # - evidence.case_id
    
    return await db.get_evidence(evidence_id)
```

**Policy Configuration**:
```yaml
# ContextForge config
plugins:
  - name: CedarEnginePlugin
    config:
      policies: |
        permit(principal, action, resource)
        when { principal.assigned_cases.contains(resource.case_id) };
```

---

## 7. Observability & Audit Trail

### 7.1 OpenTelemetry Integration

**ContextForge Configuration**:
```yaml
observability:
  enabled: true
  service_name: dial-stack-evidence
  
  # Export to Phoenix (LLM-focused)
  exporter: otlp
  endpoint: http://phoenix:4317
  
  # Or Jaeger
  # exporter: jaeger
  # endpoint: http://jaeger:14268/api/traces
  
  # Or Zipkin
  # exporter: zipkin
  # endpoint: http://zipkin:9411/api/v2/spans
```

### 7.2 Trace Structure for Evidence

```python
# Evidence processing trace
span = tracer.start_span("evidence_processing")
span.set_attribute("evidence.id", evidence_id)
span.set_attribute("evidence.hash", sha256_hash)
span.set_attribute("tool.name", tool_name)
span.set_attribute("user.id", user_id)
span.set_attribute("case.id", case_id)

# Child spans for each step
with tracer.start_as_current_span("pii_detection") as pii_span:
    pii_result = detect_pii(content)
    pii_span.set_attribute("entities_found", len(pii_result))

with tracer.start_as_current_span("content_analysis") as analysis_span:
    analysis_result = analyze_content(content)
    analysis_span.set_attribute("sentiment", analysis_result.sentiment)

span.end()
```

### 7.3 Chain of Custody Integration

**Current Dial-Stack** (manual audit decorator):
```python
@audit_log
@mcp.tool()
async def dpk_hap_score(text: str) -> dict:
    """Calculate HAP score."""
```

**With ContextForge** (automatic via OpenTelemetry):
```python
@mcp.tool()
async def dpk_hap_score(text: str) -> dict:
    """Calculate HAP score."""
    # OpenTelemetry automatically captures:
    # - Tool name
    # - Input/output (configurable)
    # - Timestamp
    # - Duration
    # - User context
    # - Correlation ID
```

### 7.4 Phoenix Integration

**Arize Phoenix** is LLM-focused observability:
```yaml
# docker-compose.yml
services:
  phoenix:
    image: arizephoenix/phoenix:latest
    ports:
      - "6006:6006"
    environment:
      - PHOENIX_ENABLE_AUTH=true
      - PHOENIX_SECRET_KEY=${PHOENIX_SECRET}
```

**View evidence processing traces**:
- Tool invocation timeline
- Token usage per tool
- Latency breakdown
- Error tracking
- Evidence lineage

---

## 8. Caching & Performance

### 8.1 ContextForge Caching Plugins

#### `cached_tool_result`
```yaml
plugins:
  - name: CachedToolResultPlugin
    kind: "plugins.cached_tool_result.cached_tool_result.CachedToolResultPlugin"
    hooks: ["tool_post_invoke"]
    mode: "permissive"
    priority: 90
    config:
      backend: redis
      ttl: 3600  # 1 hour
      key_template: "{tool_name}:{input_hash}"
```

#### `response_cache_by_prompt`
```yaml
plugins:
  - name: ResponseCacheByPromptPlugin
    config:
      semantic_matching: true  # Cache similar prompts
      similarity_threshold: 0.95
```

### 8.2 Evidence-Specific Caching

**Hash-based caching for evidence**:
```python
# Evidence processing is deterministic
# Same input → Same output → Cacheable

@mcp.tool()
async def analyze_evidence(content_hash: str, content: str) -> dict:
    """Analyze evidence with caching."""
    
    # ContextForge automatically caches based on:
    # - Tool name: analyze_evidence
    # - Input hash: sha256(content)
    
    # Cache hit → Return cached result (no re-processing)
    # Cache miss → Process and cache result
    
    return await process_content(content)
```

### 8.3 Redis Configuration

```yaml
# ContextForge Redis setup
cache:
  backend: redis
  redis:
    host: dragonfly  # Dial-Stack uses Dragonfly (Redis-compatible)
    port: 6379
    db: 0
    password: ${REDIS_PASSWORD}
    
    # Evidence-specific settings
    key_prefix: "evidence:"
    ttl: 86400  # 24 hours for evidence
```

---

## 9. Authentication & Authorization

### 9.1 ContextForge Auth Methods

| Method | Use Case | Dial-Stack Fit |
|--------|----------|----------------|
| Basic Auth | Development | ✓ Current setup |
| JWT | Production APIs | ✓ Keycloak integration |
| OAuth | Third-party access | ✓ External reviewers |
| API Keys | Service accounts | ✓ Tool-to-tool |
| Custom | Specialized auth | ✓ Custom evidence auth |

### 9.2 Keycloak Integration

**Current Dial-Stack**: Keycloak provides OIDC/JWT

**ContextForge Configuration**:
```yaml
auth:
  type: jwt
  jwt:
    issuer: http://keycloak:8180/realms/dial-stack
    audience: dial-stack-api
    jwks_uri: http://keycloak:8180/realms/dial-stack/protocol/openid-connect/certs
    
    # Role extraction
    roles_claim: realm_access.roles
    admin_roles: ["admin"]
    readonly_roles: ["readonly"]
```

### 9.3 Multi-Tenant Evidence Access

```yaml
# Tenant isolation for evidence
tenants:
  - id: case_123
    name: "Smith v. Jones"
    admins: ["attorney_1", "attorney_2"]
    members: ["analyst_1", "analyst_2"]
    
  - id: case_456
    name: "Doe v. Roe"
    admins: ["attorney_3"]
    members: ["analyst_3"]

# Policy enforcement
plugins:
  - name: TenantIsolationPlugin
    config:
      enforce: true
      audit: true
```

---

## 10. Admin UI & Monitoring

### 10.1 ContextForge Admin UI

**Features**:
- Real-time log viewer
- Tool invocation history
- Plugin management
- Server health monitoring
- User activity audit

**Access**: `http://localhost:4444/admin`

### 10.2 Evidence Dashboard Integration

**Customize for evidence analysis**:
```yaml
ui:
  branding:
    title: "Dial-Stack Evidence Gateway"
    logo: /static/evidence-logo.png
    
  dashboard:
    widgets:
      - type: chart
        title: "Evidence Processed"
        metric: tool_invocations
        group_by: evidence_type
        
      - type: table
        title: "Recent Evidence"
        query: "SELECT * FROM evidence ORDER BY created_at DESC LIMIT 10"
        
      - type: gauge
        title: "PII Redaction Rate"
        metric: pii_entities_detected
```

---

## 11. Deployment Options

### 11.1 Docker Compose (Recommended for Dial-Stack)

```yaml
# Add to dial-stack docker-compose.yml
services:
  contextforge:
    image: ghcr.io/ibm/mcp-context-forge:1.0.0-RC-2
    ports:
      - "4444:4444"
    environment:
      - BASIC_AUTH_PASSWORD=${CONTEXTFORGE_PASSWORD}
      - MCPGATEWAY_UI_ENABLED=true
      - MCPGATEWAY_ADMIN_API_ENABLED=true
      - OTEL_ENABLE_OBSERVABILITY=true
      - OTEL_TRACES_EXPORTER=otlp
      - OTEL_EXPORTER_OTLP_ENDPOINT=http://phoenix:4317
    volumes:
      - ./config/contextforge.yaml:/app/config.yaml
      - ./plugins:/app/plugins/custom
    depends_on:
      - dragonfly
      - phoenix
```

### 11.2 Kubernetes (Production)

```yaml
# Helm values for ContextForge
replicaCount: 2

image:
  repository: ghcr.io/ibm/mcp-context-forge
  tag: 1.0.0-RC-2

service:
  type: ClusterIP
  port: 4444

ingress:
  enabled: true
  hosts:
    - host: contextforge.dial-stack.local
      paths: [/]

resources:
  limits:
    cpu: 2000m
    memory: 4Gi
  requests:
    cpu: 500m
    memory: 1Gi

redis:
  enabled: true
  # Or use existing Dragonfly
  externalRedis:
    host: dragonfly
    port: 6379
```

---

## 12. Implementation Roadmap

### Phase 1: Foundation (Week 1-2)
- [ ] Deploy ContextForge locally via Docker
- [ ] Configure basic auth (Keycloak integration)
- [ ] Register dial-stack MCP servers
- [ ] Enable OpenTelemetry to Phoenix

### Phase 2: Security Plugins (Week 3-4)
- [ ] Enable `pii_filter` plugin
- [ ] Enable `secrets_detection` plugin
- [ ] Configure `content_moderation` for abuse/hate
- [ ] Add forensic-specific entity patterns

### Phase 3: Policy Enforcement (Week 5-6)
- [ ] Configure Cedar policies for evidence access
- [ ] Set up OPA for governance rules
- [ ] Test multi-tenant isolation

### Phase 4: Performance (Week 7-8)
- [ ] Enable caching plugins
- [ ] Configure Redis (Dragonfly) backend
- [ ] Benchmark latency impact
- [ ] Optimize plugin order

### Phase 5: Integration (Week 9-10)
- [ ] Add REST adapters for court APIs
- [ ] Configure gRPC for external services
- [ ] Build custom forensic plugins
- [ ] Create evidence dashboard

---

## 13. Decision Matrix

| Factor | Full ContextForge | Hybrid | Plugin Extract Only |
|--------|------------------|--------|---------------------|
| **Latency** | +20-50ms overhead | Minimal | None |
| **Complexity** | High | Medium | Low |
| **Features** | Full | Partial | Limited |
| **Maintenance** | IBM/community | Shared | Self |
| **Risk** | New dependency | Balanced | Manual updates |
| **Audit Trail** | Automatic | Partial | Manual |
| **Policy Engine** | Built-in | Configurable | Custom build |

### Recommendation

**For Dial-Stack**: Start with **Hybrid** approach

**Rationale**:
1. Evidence analysis needs low latency - keep core tools direct
2. Add ContextForge for specific workflows (PII, moderation)
3. Gradually migrate proven features
4. Maintain option to go full ContextForge later

---

## 14. Appendix: Plugin Reference

### Security Plugins

| Plugin | Purpose | Priority | Mode |
|--------|---------|----------|------|
| `pii_filter` | PII detection/redaction | 50 | enforce |
| `secrets_detection` | Credential scanning | 45 | enforce |
| `content_moderation` | Abuse/hate detection | 60 | permissive |
| `code_safety_linter` | Code analysis | 70 | permissive |
| `sql_sanitizer` | SQL injection prevention | 30 | enforce |

### Performance Plugins

| Plugin | Purpose | Priority | Mode |
|--------|---------|----------|------|
| `cached_tool_result` | Result caching | 90 | permissive |
| `rate_limiter` | Rate limiting | 20 | enforce |
| `circuit_breaker` | Fault tolerance | 25 | enforce |
| `retry_with_backoff` | Retry logic | 80 | permissive |

### Policy Plugins

| Plugin | Purpose | Priority | Mode |
|--------|---------|----------|------|
| `cedar_engine` | Cedar policies | 10 | enforce |
| `opa_engine` | OPA policies | 10 | enforce |
| `schema_guard` | Schema validation | 40 | enforce |

---

## References

- (source: ContextForge GitHub repository analysis)
- (source: dial-stack CLAUDE.md)
- (source: dial-stack TOOL_CATALOG.md)
- (context: mem0 - prior ContextForge research)
