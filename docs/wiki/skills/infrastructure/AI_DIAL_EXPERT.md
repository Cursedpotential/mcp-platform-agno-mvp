---
name: ai-dial-expert
description: >
  Expert knowledge of the AI DIAL architecture, Docker Compose deployments,
  and dynamic configuration (core/config.json). Use this skill when deploying,
  configuring, or managing AI DIAL instances, adding LLM models, or wiring MCP toolsets.
---

# AI DIAL Expert Skill

You are an expert in configuring and deploying **EPAM's AI DIAL** (Deterministic Integrator of Applications and LLMs). AI DIAL is an API-first Enterprise AI Gateway and Orchestrator. 

## Key Architectural Concepts
1. **DIAL Core**: The headless message router. Exposes a single [Unified API](https://dialx.ai/dial_api) compatible with OpenAI's API.
2. **DIAL Chat**: The React-based frontend UI.
3. **Adapters**: Translate DIAL's Universal API into vendor-specific APIs (Azure, GCP, AWS Bedrock, Ollama). 
4. **Toolsets (MCP)**: DIAL natively supports the Model Context Protocol (MCP). It consumes MCP servers as toolsets via standard HTTP.

## Infrastructure Stack (VPS / Self-hosted)
For localized standalone deployments, the stack relies on:
- `docker-compose.yml` for service wiring.
- Cache: Redis or a drop-in replacement like **Dragonfly**.
- Object Storage: S3 or any S3-compatible Blob storage (e.g., **Cloudflare R2**).

## Configuration Methodology

### Environment Variables (Static)
The `docker-compose.yml` defines the static settings for images like `ai-dial-core` and `ai-dial-chat`.
Example Core Environment mapping for Storage:
```yaml
environment:
  'AIDIAL_SETTINGS': '/opt/settings/settings.json'
  'aidial.config.files': '["/opt/config/config.json"]'
  'aidial.storage.overrides': '{ "jclouds.provider": "s3", "jclouds.endpoint": "...", "jclouds.identity": "...", "jclouds.credential": "...", "jclouds.regions": "auto", "jclouds.s3.virtual-host-buckets": "false", "jclouds.filesystem.basedir": "..." }'
```

### JSON Configuration (Dynamic)
The dynamic configuration defines the models, applications, and routing. It is loaded from `core/config.json`.

**Schema Structure:**
```json
{
  "routes": {},
  "models": {
    "gpt-4": {
      "type": "chat",
      "displayName": "GPT-4",
      "endpoint": "http://adapter-openai:5000/openai/deployments/gpt-4/chat/completions",
      "upstreams": [
        {
          "endpoint": "http://upstream_host/openai...",
          "key": "API_KEY"
        }
      ]
    }
  },
  "applications": {
    "my-mcp-tool": {
      "displayName": "My Custom Context Tool",
      "description": "An atomic MCP server",
      "endpoint": "http://my-mcp-service:8080/mcp/chat/completions"
    }
  },
  "keys": {
    "dial_api_key": {
      "project": "default",
      "role": "default"
    }
  },
  "roles": {
    "default": {
      "limits": {
        "gpt-4": {}
      }
    }
  }
}
```

## Useful Links
- **API Documentation**: [dialx.ai/dial_api](https://dialx.ai/dial_api)

When updating DIAL deployments, modifying the `core/config.json` properties, or writing MCP HTTP wrappers meant for DIAL consumption, strictly adhere to these patterns.
