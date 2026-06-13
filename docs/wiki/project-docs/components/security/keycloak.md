---
title: Keycloak
type: reference
status: active
created: 2026-03-30
updated: 2026-03-30
reviewed: 2026-03-30
tags:
  - dial-stack
  - wiki
  - security
  - keycloak
  - auth
summary: Reference note for Keycloak as the current identity provider in the dial-stack runtime and a likely bridge point for future ingress auth.
repo_usage_state: partial
repo_version: quay.io/keycloak/keycloak:24.0.2 in docker-compose.yml
upstream_version: Keycloak 26.5.6 release note reviewed 2026-03-30
official_docs:
  - https://www.keycloak.org/documentation
official_repo:
  - https://github.com/keycloak/keycloak
official_downloads:
  - https://www.keycloak.org/downloads
---

# Keycloak

## At a Glance

- **What it is**: OpenID Connect and identity/access management platform.
- **Current role in `dial-stack`**: Current runtime identity provider for DIAL-oriented auth flows.
- **Why it matters**: It is the existing auth surface in the composed stack and likely part of the bridge to future ingress auth decisions.

## How `dial-stack` Uses It

Current local anchors:

- [docker-compose.yml](C:/Users/matts/Projects/TheBigOne/dial-stack/docker-compose.yml)
- [infrastructure/settings/settings.json](C:/Users/matts/Projects/TheBigOne/dial-stack/infrastructure/settings/settings.json)
- [infrastructure/init/keycloak](C:/Users/matts/Projects/TheBigOne/dial-stack/infrastructure/init/keycloak)

Current responsibilities:

- realm and user auth for the current DIAL runtime
- JWKS endpoint for token verification
- auth-helper integration for the internal chat/application stack

## Repo Version vs Upstream Version

| Posture | Value | Notes |
|---|---|---|
| Repo image | `24.0.2` | Pinned in root compose |
| Upstream release reviewed | `26.5.6` | Official release note reviewed 2026-03-30 |
| Current risk | version drift | The repo is well behind current patch releases |

## How We Could Expand Its Use

- become the short-term identity bridge for ContextForge experiments
- formalize role mappings for analyst, reviewer, and admin surfaces
- add service-account and machine-to-machine patterns for tool gateways
- centralize realm exports and reproducible auth bootstrap

## What We Need to Watch

- repo version lag against current security fixes
- duplicated auth logic between DIAL-era and ContextForge-era boundaries
- realm config drift across environments
- accidental frontend leakage of secrets or internal-only assumptions

## Key Repo Files

- [docker-compose.yml](C:/Users/matts/Projects/TheBigOne/dial-stack/docker-compose.yml)
- [settings.json](C:/Users/matts/Projects/TheBigOne/dial-stack/infrastructure/settings/settings.json)
- [init/keycloak](C:/Users/matts/Projects/TheBigOne/dial-stack/infrastructure/init/keycloak)

## Official Sources

- [Keycloak Documentation](https://www.keycloak.org/documentation)
- [Keycloak Downloads](https://www.keycloak.org/downloads)
- [Keycloak GitHub](https://github.com/keycloak/keycloak)
- [Keycloak 26.5.6 Release Note](https://www.keycloak.org/2026/03/keycloak-2656-released)

## Related Notes

- [[skills/infrastructure/ai-dial-core|AI DIAL Core]]
- [[skills/orchestration/contextforge/INDEX|ContextForge Integration]]
- [[skills/infrastructure/docker-compose|Docker Compose]]
- [[INDEX|dial-stack Wiki Index]]
