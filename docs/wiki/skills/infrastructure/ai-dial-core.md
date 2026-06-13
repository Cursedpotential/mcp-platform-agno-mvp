# AI DIAL Stack — Comprehensive Reference

## Overview

AI DIAL is a **polyglot orchestration platform** combining OpenAI-compatible API gateway, web chat UI, identity management, and pluggable LLM/application backends. Our stack is fully containerized (see `/docker-compose.yml`) and integrates external LLMs (OpenRouter) with local MCP servers.

**Core Versions:**
- **AI DIAL Core** v0.25.1 (API gateway, port 8080)
- **AI DIAL Chat** v0.26.0 (web UI, port 3000)
- **AI DIAL Themes** v0.9.1 (theme server, port 3001)
- **AI DIAL Auth Helper** v0.6.2 (JWT bridge, port 8089)
- **Keycloak** 24.0.2 (identity provider, port 8080)

---

## Architecture: Core Gateway (v0.25.1)

### Config Structure
**File:** `core/config.json` (mounted at `/opt/config` in container)

Three top-level sections:

#### 1. Models
Routes to external LLMs or local Ollama. Each model is OpenAI-compatible.

```json
"models": {
  "openrouter-auto": {
    "endpoint": "${OPENROUTER_ENDPOINT}",
    "upstreams": [{"endpoint": "https://openrouter.ai/api/v1/chat/completions", "key": "${OPENROUTER_API_KEY}"}],
    "features": {"systemPrompt": true, "tools": true}
  },
  "claude-sonnet": {
    "endpoint": "${OPENROUTER_ENDPOINT}",
    "upstreams": [{"endpoint": "https://openrouter.ai/api/v1/chat/completions", "key": "${OPENROUTER_API_KEY}", "extraData": {"model": "anthropic/claude-3.5-sonnet"}}],
    "features": {"systemPrompt": true, "tools": true}
  },
  "ollama-local": {
    "endpoint": "http://ollama:11434/v1/chat/completions",
    "features": {"systemPrompt": true}
  }
}
```

**Pitfall**: `ollama-local` contradicts no-local-LLM policy and should be removed.

#### 2. Applications (Core Integration)
Registered MCP backends as HTTP endpoints. Four applications bridge DIAL requests to our MCP servers:

```json
"applications": {
  "evidence-ingestion-agent": {
    "endpoint": "http://core:8080/openai/deployments/claude-sonnet/chat/completions",
    "features": {"systemPrompt": true, "tools": true},
    "defaults": {"systemPrompt": "INGESTION_AGENT_PROMPT.md"}
  },
  "dial-ts-core": {
    "endpoint": "http://ts-mcp-server:8081/mcp/chat/completions",
    "features": {"tools": true},
    "tags": ["parser", "database", "ingestion", "ts-server"]
  },
  "dial-py-core": {
    "endpoint": "http://py-mcp-server:8000/mcp/chat/completions",
    "features": {"tools": true},
    "tags": ["ai", "nlp", "graph", "vector", "py-server"]
  },
  "dial-js-core": {
    "endpoint": "http://js-mcp-server:8083/mcp/chat/completions",
    "features": {"tools": true},
    "tags": ["legacy", "js-server"]
  }
}
```

**Critical Pitfall**: MCP servers run **stdio transport** (isolated process-stdin/stdout), but config endpoints expect **HTTP**. Servers must expose HTTP wrappers (e.g., `/mcp/chat/completions` routes stdio MCP to HTTP). Port mismatch breaks routing.

#### 3. Keys & Roles (RBAC)
Three static API keys map to three roles with granular model/application access:

```json
"keys": {
  "dial_admin_key": {"role": "admin"},
  "dial_api_key": {"role": "default"},
  "dial_readonly_key": {"role": "readonly"}
},
"roles": {
  "admin": {"limits": {"openrouter-auto": {}, "claude-sonnet": {}, "ollama-local": {}, "evidence-ingestion-agent": {}, "dial-ts-core": {}, "dial-py-core": {}, "dial-js-core": {}}},
  "default": {"limits": {"openrouter-auto": {}, "claude-sonnet": {}, "ollama-local": {}, "evidence-ingestion-agent": {}}},
  "readonly": {"limits": {"ollama-local": {}}}
}
```

Each role whitelists accessible models/apps; empty `limits` = no rate cap.

---

## Chat UI & Theming (v0.26.0 + v0.9.1)

**AI DIAL Chat** (port 3000) is a Next.js web UI that:
- Hits `POST /chat/completions` on Core (via `DIAL_API_HOST` env var)
- Authenticates with `DIAL_API_KEY` (static key from config)
- Loads themes from **AI DIAL Themes** (port 3001, `THEMES_CONFIG_HOST`)
- Provides admin console for user/model management

**Admin Interface Features:**
- User/team provisioning (syncs with Keycloak)
- Prompt templates and conversation sharing
- Custom application registration (Quick Apps, Marketplace)
- Rate limit & quota management

**Enabled Features** (`docker-compose.yml` line 25): conversations, prompts, model settings, file attachments, link embedding, custom logo, applications catalog, code apps, templates, marketplace.

---

## Identity & Authentication

### Keycloak (v24.0.2)
- **JWKS URL**: `http://keycloak:8080/realms/dial/protocol/openid-connect/certs`
- **Realm config**: `init/keycloak/` (imported on startup)
- **Credentials**: `KEYCLOAK_ADMIN` / `KEYCLOAK_ADMIN_PASSWORD`
- Stores roles in JWT `realm_access.roles` claim

### Settings (Identity Provider Config)
**File:** `settings/settings.json`

```json
{
  "identityProviders": {
    "keycloak": {
      "jwksUrl": "http://keycloak:8080/realms/dial/protocol/openid-connect/certs",
      "issuerPattern": "^http://localhost:8080/realms/dial$",
      "rolePath": "realm_access.roles",
      "disableJwtVerification": false
    }
  }
}
```

Core validates incoming JWTs against JWKS, extracts roles from `realm_access.roles`, maps to config roles (admin/default/readonly).

### Auth Helper (v0.6.2)
Bridge service (port 8089) for frontend OAuth flows:
- Exchanges auth codes for JWTs from Keycloak
- Passes JWKS URL and issuer to Chat UI
- Handles multi-tenant identity isolation

---

## Retrieval & MCP Integration

### Dual Retrieval Pattern

**1. DIAL Native Tool Calls** (ad-hoc queries)
- Chat sends structured tool requests to applications
- Applications respond via MCP protocol
- No predetermined schema; tools are dynamically discovered

**2. WunderGraph (deterministic queries)**
- Pre-registered query graphs for common operations (evidence lookup, graph traversal)
- Type-safe, pre-compiled endpoints
- Lower latency for repeated queries

### MCP Servers (HTTP-wrapped)
Three backends handle tool invocation:

| Service | Port | Transport | Capabilities |
|---------|------|-----------|---|
| **dial-ts-core** | 8081 | HTTP (`/mcp/chat/completions`) | SMS/Facebook/iMessage/WhatsApp parsers; DuckDB & PostgreSQL tools |
| **dial-py-core** | 8000 | HTTP (`/mcp/chat/completions`) | NER, temporal facts, conflict detection; LanceDB vectors, Neo4j graphs |
| **dial-js-core** | 8083 | HTTP (`/mcp/chat/completions`) | Legacy JS tools, Docling, Pandoc |

Each server:
- Receives `POST /mcp/chat/completions` with tool manifest request
- Returns list of available tools (parsers, graph queries, vector ops)
- Chat client selects tools; servers execute via stdio MCP internally

---

## Core API Endpoints

- **POST /openai/deployments/{model}/chat/completions** — Chat completion with streaming
- **GET /models** — List available models (filtered by user role)
- **GET /applications** — List registered applications
- **POST /auth/token** — Exchange credentials for JWT (if auth enabled)

OpenAI-compatible; supports `messages`, `system`, `tools`, `stream`.

---

## Configuration Pitfalls & Solutions

| Pitfall | Cause | Fix |
|---------|-------|-----|
| **HTTP/Stdio mismatch** | MCP servers use stdio; Core expects HTTP endpoints | Wrap MCP in HTTP layer (e.g., `/mcp/chat/completions` proxy) |
| **Port mismatch** | Config specifies wrong port (e.g., 8000 vs 8082 for py-server) | Verify `docker-compose.yml` port mappings match config endpoints |
| **Config hot-reload** | Core reads config only at startup | Restart Core container after `core/config.json` changes |
| **Ollama contradiction** | Config includes `ollama-local` but no-local-LLM policy | Remove `ollama-local` model & readonly role from config |
| **CORS for Chat** | Browser requests blocked from http://localhost:3000 to http://core:8080 | Core sets Access-Control-Allow-Origin in responses |
| **Timeout on long chains** | Evidence ingestion chains exceed default 30s timeout | Increase Core timeout or optimize agent prompts |

---

## File Reference

| Path | Purpose |
|------|---------|
| `core/config.json` | Models, applications, keys, roles |
| `settings/settings.json` | Keycloak JWKS, JWT validation, encryption |
| `docker-compose.yml` | All service definitions & environment variables |
| `init/keycloak/` | Realm config, role definitions, client setup |
| `INGESTION_AGENT_PROMPT.md` | System prompt for evidence-ingestion-agent app |

---

## References
- [AI DIAL Docs](https://epam-ai-dial.readthedocs.io/)
- [Keycloak OpenID Connect](https://www.keycloak.org/docs/latest/server_admin/#_client_saml_configuration)
- [OpenRouter API](https://openrouter.ai/docs/api/intro)
- [MCP Spec](https://modelcontextprotocol.io/)
