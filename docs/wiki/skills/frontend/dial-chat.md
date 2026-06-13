# AI DIAL Chat — Skill Reference

## Overview
- **What**: Production-grade chat UI for multi-model conversations. Admin interface for model/app management.
- **Version**: v0.26.0
- **Category**: Frontend/UI
- **Installed In**: Node.js/React SPA, served via Caddy or static hosting

## Configuration

### Environment Variables
```bash
REACT_APP_DIAL_API_URL=https://api.example.com
REACT_APP_DIAL_API_KEY=${DIAL_API_KEY}
REACT_APP_AUTH_URL=https://auth.example.com
REACT_APP_THEME=light|dark
```

### Theme Configuration
```json
{
  "primaryColor": "#0066cc",
  "secondaryColor": "#ffffff",
  "logoUrl": "https://...",
  "supportedModels": ["gpt-4", "gpt-3.5-turbo"],
  "applicationIds": ["semantica-rag", "summarizer"]
}
```

## API Patterns

- **Chat Endpoint**: `POST /chat/completions` (OpenAI-compatible streaming)
- **Model List**: `GET /models` (available models and capabilities)
- **Application List**: `GET /applications` (registered RAG chains)
- **Conversation History**: `GET /conversations/{id}` (persisted sessions)
- **Rate Limiting**: Enforced by Caddy reverse proxy

## Integration Points

- **DIAL Core**: Routes requests via `/chat/completions`
- **Keycloak**: OIDC login for multi-user deployments
- **Semantica**: Application endpoint for RAG pipelines
- **Admin Panel**: Model configuration and rate limit management
- **CopilotKit**: Embedded into analyst dashboard for multi-step workflows

## Common Pitfalls

- **API Endpoint Path**: Ensure `/chat/completions` not `/v1/chat/completions` unless DIAL Core is configured
- **CORS Headers**: DIAL Core must return correct `Access-Control-Allow-*` headers
- **Streaming Timeout**: Long-running Semantica chains may timeout; increase client-side timeout
- **Theme Persistence**: Theme settings cached in browser; clear localStorage if changes don't apply
- **Token Expiry**: JWT tokens may expire mid-session; refresh token logic required

## References
- [DIAL Chat GitHub](https://github.com/epam-ai-dial/dial-chat)
- [Admin Interface Guide](https://epam-ai-dial.readthedocs.io/en/latest/admin/)
- [Customization](https://epam-ai-dial.readthedocs.io/en/latest/customization/)
