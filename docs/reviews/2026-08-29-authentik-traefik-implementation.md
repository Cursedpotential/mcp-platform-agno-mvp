# Authentik and Traefik source implementation review

> **Byline:** Codex · GPT-5 · 2026-08-29
> **Status:** SOURCE IMPLEMENTED — NOT DEPLOYED, NOT LIVE-VERIFIED

## Result

`deploy/authentik.yaml` now follows the current Authentik 2026.8 deployment contract:

- Authentik server and worker use the official `2026.8.0` image pinned to the
  registry-reported OCI index digest.
- `server` and `worker` are explicit commands and both use the image-provided
  `ak healthcheck`.
- Configuration uses the documented `AUTHENTIK_POSTGRESQL__*` names.
- PostgreSQL password and `AUTHENTIK_SECRET_KEY` use Authentik's documented
  `file://` value-loader syntax against read-only host-mounted secret files.
- No application port is published. Authentik is reachable only through the
  HTTPS Traefik router.
- Authentik accepts proxy headers only from the exact `/32` or `/128` supplied
  as the non-secret `TRAEFIK_PROXY_CIDR` deployment value.
- There is no Docker socket mount. The embedded outpost/provider setup remains
  an explicit post-deploy administrator operation.
- The higher-priority Workbench-host `/outpost.goauthentik.io/` router required
  by single-application forward auth targets the embedded outpost.

## Corrections to the earlier draft

The initial source draft was not deployable and its claims were not accurate:

- Authentik 2025.10 removed Redis entirely. The obsolete Redis service and all
  `AUTHENTIK_REDIS__*` settings were removed instead of preserving a dead,
  separately authenticated datastore.
- `AUTHENTIK_POSTGRES__*`, `AUTHENTIK_SECRET_KEY_FILE`, and the other invented
  `*_FILE` Authentik settings were replaced with supported configuration names
  plus `file://` values.
- Authentik does not require `pgcrypto` or `uuid-ossp`. The custom extension
  image/mount and misleading extension healthcheck were removed; `pg_isready`
  is the database readiness gate.
- Broad proxy trust (`10.0.0.0/8`, `172.16.0.0/12`) was removed.
- The HTTP probe was replaced with Authentik's own `ak healthcheck` contract.

## Secret and configuration boundary

Only two secret files are required:

- `/data/agno/secrets/authentik/postgres-password`
- `/data/agno/secrets/authentik/secret-key`

They are mounted read-only. No secret value is committed or supplied as a
Coolify environment value. `TRAEFIK_PROXY_CIDR` is non-secret routing metadata
and must be the exact Coolify proxy socket address, not an address range chosen
for convenience.

## Source verification completed

- Official current Compose shape checked against the Authentik 2026.8 download.
- Authentik image digest independently resolved from GHCR for `2026.8.0`.
- PostgreSQL image digest independently resolved from Docker Hub for
  `postgres:18-alpine`.
- Offline YAML and source-contract tests cover both the Authentik provider and
  Workbench consumer manifests.

Official references:

- [Authentik Docker Compose installation](https://docs.goauthentik.io/install-config/install/docker-compose/)
- [Authentik configuration and file value loading](https://docs.goauthentik.io/install-config/configuration/)
- [Authentik 2025.10 Redis removal](https://docs.goauthentik.io/releases/2025.10/)
- [Authentik monitoring and `ak healthcheck`](https://docs.goauthentik.io/sys-mgmt/ops/monitoring)
- [Coolify: protect services with Authentik](https://next.coolify.io/docs/core/networking/proxy/traefik/protect-services-with-authentik)

## Live prerequisites and release gates

This source work does not establish production operation. Before deployment:

1. Create the two host secret files and persistent data directories documented
   in `deploy/authentik.yaml`.
2. Determine the exact Coolify Traefik address on the shared network and set
   `TRAEFIK_PROXY_CIDR` to that single-host CIDR.
3. Confirm the Coolify proxy, Authentik, and Workbench share a network on which
   `authentik-server:9000` resolves from Traefik.
4. Create the Authentik Proxy Provider/application for
   `workbench.int.mitechconsult.com` and bind it to the embedded outpost.
5. Deploy Authentik, then Workbench; prove unauthenticated denial, login redirect,
   authenticated return, identity headers, `/health`, and absence of a direct
   `:8020` listener.

Until all five are observed on the VPS, status remains **NOT DEPLOYED**.
