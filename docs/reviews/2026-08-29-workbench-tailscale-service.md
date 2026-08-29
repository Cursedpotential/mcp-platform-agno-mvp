# Workbench stable Tailscale Service receipt

> _Byline: Codex · GPT-5 · 2026-08-29._

## Result

The private Workbench identity is now a tailnet-level Tailscale Service instead of a VPS
identity:

| Property | Live value |
|---|---|
| Service | `svc:workbench` |
| Stable URL | `https://workbench.tilapia-skilift.ts.net` |
| TailVIP (IPv4) | `100.105.91.39` |
| TailVIP (IPv6) | `fd7a:115c:a1e0::ef29:5b28` |
| Published endpoint | `tcp:443` with Tailscale-terminated HTTPS |
| Service identity tag | `tag:docker` |
| Current service host | `ovh-app` / node `nVQkyDBWHQ11CNTRL` |
| Exposure | Tailnet only; no Funnel |

The name and TailVIP belong to `svc:workbench`, not `ovh-app`, its `100.72.169.40`
address, a Coolify container name, or a Docker hostname. A future VPS move therefore keeps
the URL: configure and approve the new tagged service host, verify it, drain the old host,
then remove the old host configuration.

Tailscale documents this as the intended Services model: a stable MagicDNS name and TailVIP
route to one or more approved hosts. See [Tailscale Services](https://tailscale.com/docs/features/tailscale-services)
and the [`tailscale serve` command](https://tailscale.com/docs/reference/tailscale-cli/serve).

## Implemented configuration

1. Defined `svc:workbench` through the Tailscale API with `tcp:443` and `tag:docker`.
2. Configured `ovh-app` (Tailscale `1.102.2`) as the service host:

   ```sh
   tailscale serve --yes --service=svc:workbench --https=443 http://127.0.0.1:18080
   ```

3. Approved only node `nVQkyDBWHQ11CNTRL` for this service through the Tailscale Services
   API. The observed host state was `approvalLevel=approved:manual` and
   `configured=ready`.
4. Added the source-controlled service-host configuration at
   `deploy/tailscale/workbench-serve.hujson`.
5. The Service proxies directly to the Workbench port published only at host loopback
   `127.0.0.1:18080` (mapped to container port `8020`). Traefik is not in the Tailscale
   Service request path. Tailscale
   terminates HTTPS, removes spoofed inbound Tailscale identity headers, and adds the
   authenticated tailnet identity headers before reaching the loopback backend.
6. Separately corrected the normal Authentik Traefik route's `traefik.docker.network` from
   the shared `agno` network to Coolify's stable
   Workbench project network `xjbuo6drbwjfby75lalk8bk7`. Live inspection proved that
   `coolify-proxy` was not attached to `agno`: it timed out dialing Workbench at
   `172.26.0.4:8020`, while its shared project-network address `192.168.48.3:8020` returned
   `/health` 200 immediately. This was the cause of the private routers accepting connections
   but returning no bytes.

Tailscale Serve strips inbound spoofed Tailscale identity headers and adds authenticated
identity headers for tailnet user traffic. The Workbench remains reachable only through a
proxy boundary it explicitly trusts; this receipt does not authorize a direct container port,
a broad trusted-proxy range, a shared password, or synthetic identity headers.

## Verification receipts

Live observations on 2026-08-29:

- `ovh-app` is online, tagged `tag:docker`, and its node identity is independent of the
  Workbench service identity.
- The initial `tailscale serve status --json` on `ovh-app` reported `svc:workbench`, HTTPS on
  `443`, and proxy target `http://127.0.0.1:80`; this was the diagnostic Traefik path. The
  owner then corrected the final topology to direct loopback Workbench
  `http://127.0.0.1:18080`. Final live proof below must show the corrected target.
- `tailscale serve get-config --service=svc:workbench` reports
  `tcp:443 -> http://127.0.0.1:18080` after final reconfiguration.
- MagicDNS resolves `workbench.tilapia-skilift.ts.net` to `100.105.91.39`.
- `tailscale ping 100.105.91.39` reaches `ovh-app`.
- A tailnet client completed TCP and TLS to `100.105.91.39:443`.
- The Docker loopback mapping makes the Serve proxy's actual Workbench socket peer
  `172.26.0.1`. The first deployment trusted stale `172.17.0.1/32` and correctly failed closed
  with HTTP 403. The corrected Coolify environment trusts only `172.26.0.1/32` for
  `TRUSTED_TAILSCALE_SERVE_PROXY_CIDRS`; a subsequent request proved that Serve supplied the
  validated `Tailscale-User-Login` identity header required by Workbench.
- Final live request:
  `GET https://workbench.tilapia-skilift.ts.net/evidence/preview` returned HTTP `200`,
  `Content-Type: text/html; charset=utf-8`, 29,531 response bytes, and title
  `The Platform — Evidence &amp; Legal Operations`.
- The live healthy Coolify container published only
  `127.0.0.1:18080->8020/tcp`; there was no tailnet-wide or public host-port bind.

This is application proof for the rendered preview route, not proof that every downstream
Workbench operation, UIW workflow, object-store connection, or evidence action is healthy.

## End-user reachability diagnosis

After the owner reported that a browser could not reach the stable URL, a second live audit
found no server-side or policy failure:

- `svc:workbench` remained `approved:manual` and `configured=ready` on `ovh-app`.
- The tailnet policy's effective broad grant was `src: ["*"]`, `dst: ["*"]`, `ip: ["*"]`;
  no Service-specific grant denied the owner.
- MagicDNS still resolved the stable name to `100.105.91.39` and a tailnet-connected Windows
  client returned HTTP 200 from `/evidence/preview`.
- Workbench logs contained successful Serve-proxied requests from `172.26.0.1`, but no rejected
  or incomplete request corresponding to the reported browser attempt.
- All three owner Android devices were offline in the tailnet. The newest had last been seen
  17 hours earlier; the others had been offline for 10 and 97 days.

The failed browser attempt therefore did not reach the Tailscale Service. The most likely cause
is that the browser device was not connected to Tailscale. On mobile, connect the Tailscale app
before opening the private URL. If reproducing on the Windows host where the CLI and `curl` are
already successful, the remaining boundary is browser-local secure DNS, VPN, or proxy routing;
test without that browser-specific routing. Making the URL work while the client is outside the
tailnet would require public exposure, which is explicitly outside this private-Service design.

The Windows browser incident was subsequently confirmed as Chrome secure DNS configured in
`secure` mode with Cloudflare, bypassing MagicDNS. Opening the exact private URL in Edge reached
Workbench: the document, Next.js assets, fonts, and favicon all returned HTTP 200.

## Fixed-case dependency incident

The reachable UI then displayed `Fixed case unavailable`. Live tracing established the exact
failure:

- Browser request `GET /api/matters?limit=50&offset=0` returned HTTP 503 with
  `Platform API bearer secret is unavailable or invalid`.
- Workbench failed before calling Platform `/v1/matters`; this was not a database, matter-data,
  or Tailscale failure.
- `/run/secrets/platform-api-bearer` was a directory because its host bind source
  `/data/agno/secrets/platform/api-bearer` was also an empty directory.
- The nearby `/data/agno/secrets/knowledge-workbench/agentos-api-token` was not a credential. It
  was a 135-byte UTF-8/CRLF prose fragment; the live AgentOS `OS_SECURITY_KEY` was 66 bytes.

The safe operational correction is to quarantine the mistaken empty directory, create
`/data/agno/secrets/platform/api-bearer` as a mode-0400 regular file containing the exact live
AgentOS `OS_SECURITY_KEY` with no CR/LF, then redeploy Workbench so Docker remounts a regular
read-only file. No Workbench code change is indicated by this failure.

## Move procedure

On the replacement tagged VPS, after the loopback-published Workbench health is proven:

```sh
tailscale serve set-config --service=svc:workbench workbench-serve.hujson
tailscale serve advertise svc:workbench
tailscale serve status --json
```

Approve the new service host if the tailnet does not auto-approve it. Verify the stable URL
through the new host. Only then, on the former host:

```sh
tailscale serve drain svc:workbench
tailscale serve clear svc:workbench
```

Draining preserves established connections while directing new connections to another approved
host. Never run `tailscale funnel` for Workbench.

## Rollback

If the private Service route must be withdrawn without touching the Workbench container or
Coolify application:

```sh
tailscale serve drain svc:workbench
tailscale serve clear svc:workbench
```

The Tailscale Service definition and stable name can remain allocated for a later approved host.
Deleting the service definition is intentionally outside this rollback and remains an owner-only
decision.
