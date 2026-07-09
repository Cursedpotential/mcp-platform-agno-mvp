# app/ — Progressive Disclosure Map

> Application entrypoint, model factory, and server configuration.

## Directory Map

```
app/
  __init__.py          <- Package marker (empty).
  main.py              <- AgentOS entrypoint: FastAPI app, lifespan, router assembly.
  settings.py          <- Provider-agnostic model factory (Ollama → NVIDIA → Kimi → …).
  config.yaml          <- AgentOS runtime config (quick prompts, team settings).
```

## How to Read This Directory

| You need to understand... | Read this |
|---|---|
| How the server starts and wires AgentOS | `main.py` |
| How models are selected and constructed | `settings.py` |
| Runtime prompts and AgentOS config | `config.yaml` |

## Key Conventions

- **Model selection** is credential-driven: the first provider with a valid key wins.
  Order: Ollama → NVIDIA → Kimi → OpenRouter → Anthropic → OpenAI → Google → Groq.
- **AgentOS wraps FastAPI** — custom routes are registered on the base app BEFORE
  wrapping, with `on_route_conflict="preserve_base_app"`.
- **NO uvicorn reload** — it breaks the MCP lifespan under AgentOS.
