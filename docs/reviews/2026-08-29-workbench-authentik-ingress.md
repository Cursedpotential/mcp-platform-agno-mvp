# Workbench Authentik ingress source review

> **Byline:** Codex · GPT-5 · 2026-08-29
> **Status:** SOURCE IMPLEMENTED — NOT DEPLOYED, NOT LIVE-VERIFIED

## Implemented boundary

`deploy/workbench.yaml` now routes all browser access through Traefik and the
Authentik forward-auth middleware:

- the host `:8020` publication was removed, including the former tailnet bypass;
- the HTTPS Workbench router is active in source, not a commented scaffold;
- `workbench-authentik` calls the embedded Authentik outpost over the shared
  network at
  `http://authentik-server:9000/outpost.goauthentik.io/auth/traefik`;
- the higher-priority `/outpost.goauthentik.io/` route on the Workbench host is
  owned by the Authentik service, as single-application forward auth requires;
- the middleware is attached through Coolify's documented
  `coolify.traefik.middlewares` Compose label;
- Authentik UID and username response headers are copied to Workbench;
- `TRUSTED_AUTH_PROXY_CIDRS` is required in the consumer manifest and receives
  the same exact `TRAEFIK_PROXY_CIDR` deployment value as Authentik;
- Basic Auth and the Workbench shared-password environment contract were
  removed from this manifest.

The API middleware remains fail-closed. Only exact `/health` is public. Every
other path requires an exact trusted socket peer plus non-blank, bounded,
control-character-free `X-authentik-uid` and `X-authentik-username` values.
Forwarded client-address headers never establish trust.

## Test isolation correction

`workbench/api/tests/test_auth.py` no longer mutates the process-wide settings
object and depends on callers remembering to close a wrapper. Each test client
now has an isolated settings instance patched only for the duration of its own
request. This prevents one CIDR case from leaking into later tests.

## Verification boundary

Source checks cover middleware definition and attachment, exact proxy-boundary
configuration, removal of the direct host port, absence of Basic Auth, identity
header validation, and provider/consumer YAML parsing.

This is not proof of a working login. Live completion still requires:

1. exact Traefik proxy address discovery and `TRAEFIK_PROXY_CIDR` configuration;
2. Authentik Proxy Provider/application/outpost binding;
3. DNS and TLS for `auth.int.mitechconsult.com` and
   `workbench.int.mitechconsult.com`;
4. Coolify deployment of both manifests;
5. browser and HTTP proof for denial, redirect, successful login, identity
   propagation, public health, and no direct `100.72.169.40:8020` listener.

Official references:

- [Coolify Authentik protection guide](https://next.coolify.io/docs/core/networking/proxy/traefik/protect-services-with-authentik)
- [Coolify custom middleware attachment](https://coolify.io/docs/knowledge-base/proxy/traefik/custom-middlewares)
- [Traefik ForwardAuth](https://doc.traefik.io/traefik/reference/routing-configuration/http/middlewares/forwardauth/)
