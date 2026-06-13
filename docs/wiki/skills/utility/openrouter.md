# OpenRouter — Skill Reference

## Overview
- **What**: Multi-model LLM API router. Unified interface to 100+ models (OpenAI, Claude, Mistral, Llama, etc.).
- **Version**: API v1
- **Category**: Utility/LLM
- **Installed In**: External service; integrated via DIAL Core routing

## Configuration

### DIAL Core Integration
```json
{
  "models": [
    {
      "id": "gpt-4",
      "endpoint": "https://openrouter.io/api/v1/chat/completions",
      "authHeader": "Authorization: Bearer sk-or-...",
      "type": "chat"
    },
    {
      "id": "claude-3-opus",
      "endpoint": "https://openrouter.io/api/v1/chat/completions",
      "parameters": {
        "model": "anthropic/claude-3-opus"
      }
    }
  ]
}
```

### Environment Variables
```bash
OPENROUTER_API_KEY=sk-or-...
OPENROUTER_REFERER=https://dialstack.example.com
```

## API Patterns

- **POST /api/v1/chat/completions** — OpenAI-compatible chat endpoint
- **GET /api/v1/models** — List available models
- **Cost Tracking**: Response headers include `X-Total-Cost` for billing
- **Model Parameters**: Pass `model` field to select specific provider
- **Rate Limits**: Per-account limits enforced; cascade fallbacks available

```bash
curl https://openrouter.io/api/v1/chat/completions \
  -H "Authorization: Bearer ${OPENROUTER_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "anthropic/claude-3-opus",
    "messages": [{"role": "user", "content": "..."}]
  }'
```

## Integration Points

- **DIAL Core**: Routes model requests to OpenRouter endpoints
- **Model Selection**: Frontend chooses model; DIAL Core maps to OpenRouter `model` parameter
- **Fallback Strategy**: Semantica RAG can fall back to cheaper models if rate-limited
- **Cost Monitoring**: Track usage via OpenRouter dashboard or API
- **Custom Models**: Self-hosted models not directly supported; use direct DIAL Core routing instead

## Common Pitfalls

- **API Key Exposure**: Keep API key in server-side .env; never expose to frontend
- **Model Naming**: OpenRouter uses namespace format (e.g., `anthropic/claude-3-opus`); map carefully
- **Rate Limits**: Usage-based quotas; monitor cost headers to avoid overages
- **Timeout Tuning**: Some models slower than others; adjust per-model in DIAL Core config
- **Fallback Logic**: OpenRouter doesn't auto-fallback; implement in DIAL Core layer

## References
- [OpenRouter Documentation](https://openrouter.ai/docs)
- [Available Models](https://openrouter.ai/docs/models)
- [Pricing Information](https://openrouter.ai/docs/pricing)
- [API Reference](https://openrouter.ai/docs/api/v1)
