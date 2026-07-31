# app/ — Progressive Disclosure Map

> Application entrypoint, model factory, and server configuration.

## Directory Map

```
app/
  __init__.py          <- Package marker (empty).
  main.py              <- AgentOS entrypoint: FastAPI app, lifespan, router assembly.
  settings.py          <- Provider-agnostic model factory (Ollama → NVIDIA → Kimi → …).
  config.yaml          <- AgentOS runtime config (quick prompts, team settings).
  mcp_main.py           <- DEPRECATED 2026-07-23 (retired, kept for historical
                           reference — see its header). Do not deploy.
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
- **MCP surface: the mounted `/mcp` on `main.py`'s AgentOS app (port 8000) is now
  canonical.** Fixed upstream in agno 2.8.0 (previously the mounted sub-app's
  StreamableHTTP session-manager didn't survive being mounted — 0/5 workarounds
  succeeded pre-2.8.0). The standalone `agentos-mcp` service that worked around
  this (`mcp_main.py`, its own uvicorn process on :8001) is **retired** as of
  2026-07-23 — do not resurrect it; use `:8000/mcp` for all MCP clients. See
  `mcp_main.py`'s header and `C:\Users\matts\OneDrive\AI Space\agno-upgrade-result.md`
  for the verification trail.
