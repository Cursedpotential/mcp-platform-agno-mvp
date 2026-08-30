# server/api/ — Progressive Disclosure Map

> Framework-neutral HTTP composition root and platform-owned routes.

## Directory Map

```
server/api/
  main.py              <- Plain FastAPI composition root and lifespan.
  platform_auth.py     <- Runtime-mounted, request-time owner bearer checks.
  runtime_support.py   <- Neutral R2 and native Weaviate startup helpers.
  *_routes.py          <- Platform-owned HTTP capabilities.
  mcp_main.py          <- Retired AgentOS-era historical module. Do not deploy.
```

## How to Read This Directory

| You need to understand... | Read this |
|---|---|
| How the server starts | `main.py` |
| How owner bearer rotation works | `platform_auth.py` |
| Which platform HTTP capability is exposed | the relevant `*_routes.py` |

## Key Conventions

- The production host imports no Agno modules. Bounded atomic-agent adapters run only
  from explicit Temporal activities; they are never mounted here.
- Temporal owns durable execution, ContextForge owns MCP publication, and Portkey owns
  model routing.
- All ordinary routes use the runtime-mounted Platform API bearer. Purpose-specific
  signed-walk and operator evidence routes enforce their exact local credentials.
- There is no Platform API `/mcp`, `/agents`, `/teams`, `/workflows`, or model picker.

> _Byline: Codex · GPT-5.6-Sol · 2026-08-29 (AgentOS host retirement true-up)._
