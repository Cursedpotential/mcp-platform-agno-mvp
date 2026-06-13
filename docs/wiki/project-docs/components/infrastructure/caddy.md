---
title: Caddy
type: reference
status: active
created: 2026-03-30
updated: 2026-03-30
reviewed: 2026-03-30
tags:
  - dial-stack
  - wiki
  - infrastructure
  - caddy
  - proxy
summary: Reference note for Caddy as the current reverse proxy and TLS layer in the root dial-stack runtime.
repo_usage_state: partial
repo_version: caddy:latest in docker-compose.yml
upstream_version: Caddy 2.10.2 latest stable release reviewed 2026-03-30
official_docs:
  - https://caddyserver.com/docs/
  - https://caddyserver.com/docs/install
official_repo:
  - https://github.com/caddyserver/caddy
official_downloads:
  - https://caddyserver.com/download
  - https://github.com/caddyserver/caddy/releases
---

# Caddy

## At a Glance

- **What it is**: Reverse proxy and web server with automatic HTTPS and flexible config options.
- **Current role in `dial-stack`**: Root proxy/TLS layer in the current compose stack.
- **Why it matters**: It is the natural place to terminate HTTP traffic and route requests without hardcoding proxy behavior into application services.

## How `dial-stack` Uses It

Current local anchors:

- [docker-compose.yml](C:/Users/matts/Projects/TheBigOne/dial-stack/docker-compose.yml)
- [infrastructure/Caddyfile](C:/Users/matts/Projects/TheBigOne/dial-stack/infrastructure/Caddyfile)

Current responsibilities:

- reverse proxy for the current runtime
- TLS and external port exposure
- a thin boundary in front of the current core service

## Repo Version vs Upstream Version

| Posture | Value | Notes |
|---|---|---|
| Repo image | `caddy:latest` | Currently unpinned; drift risk |
| Upstream latest reviewed | `2.10.2` | Latest stable release reviewed 2026-03-30 |
| Current risk | unpinned runtime image | Behavior can change without intentional review |

## How We Could Expand Its Use

- standardize ingress routing around ContextForge once the gateway boundary is live
- use a cleaner proxy layer for internal vs external surfaces
- tighten TLS and proxy policy handling around operator tooling
- keep it as a stable runtime boundary without turning it into business logic

## What We Need to Watch

- `latest` tags are a documentation and deployment smell
- proxy rules should not hide evidence-routing semantics
- WebSocket and streaming behavior need to be verified for tool and chat surfaces
- ingress changes should stay aligned with ContextForge plans

## Key Repo Files

- [docker-compose.yml](C:/Users/matts/Projects/TheBigOne/dial-stack/docker-compose.yml)
- [Caddyfile](C:/Users/matts/Projects/TheBigOne/dial-stack/infrastructure/Caddyfile)

## Official Sources

- [Caddy Documentation](https://caddyserver.com/docs/)
- [Caddy Install Docs](https://caddyserver.com/docs/install)
- [Caddy Download Page](https://caddyserver.com/download)
- [Caddy GitHub](https://github.com/caddyserver/caddy)

## Related Notes

- [[skills/infrastructure/docker-compose|Docker Compose]]
- [[skills/orchestration/contextforge/INDEX|ContextForge Integration]]
- [[skills/infrastructure/ai-dial-core|AI DIAL Core]]
- [[INDEX|dial-stack Wiki Index]]
