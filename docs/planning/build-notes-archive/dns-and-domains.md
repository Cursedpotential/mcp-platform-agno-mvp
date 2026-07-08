# DNS + Traefik Base-Domain Plan — mitechconsult.com

> _Byline: Claude Code · Opus 4.8 · 2026-06-14_
> Status: **DRAFT / authoring only.** No DNS records created or modified by this document.
> Apply via `create-dns.mjs` (dry-run by default).

## 1. Design summary

Dual-hostname convention for every service:

| Tier | Pattern | Target | Proxy | Reachability | TLS |
|------|---------|--------|-------|--------------|-----|
| **PRIVATE** (always-on) | `<svc>.int.mitechconsult.com` | box **tailnet** IP | `proxied:false` (DNS-only / grey) | tailnet members only | Traefik + Cloudflare **DNS-01** |
| **PUBLIC TWIN** (staged) | `<svc>.mitechconsult.com` | box **public** IP | `proxied:true` (orange) | gateable/blockable at CF edge | Cloudflare edge cert (orange) + origin Traefik |

- Zone: `mitechconsult.com` — Cloudflare zone `d543c96e4bb7fad63e5f1925dce79640`.
- Public twins exist for **only** `api`, `chat`, `mcp`. They are created **orange-clouded so they can be gated/blocked at the edge** and are **treated as default-blocked** until explicitly opened.
- Private `.int` records are DNS-only because they resolve to RFC-tailnet (CGNAT 100.64/10) addresses that Cloudflare cannot proxy anyway; valid TLS comes from DNS-01 (below).

### Boxes
| Box | Role | Tailnet IP | Public IP |
|-----|------|-----------|-----------|
| OVH-1 | exec | `100.72.169.40` | `40.160.5.19` |
| OVH-3 | data | `100.119.96.29` | `147.135.79.183` |
| OVH-2 | (legacy, being vacated) | — | `51.81.83.191` |

## 2. Full record table

### 2a. PRIVATE `.int` A records (created/updated by default run)

| Name | Type | Target IP | Proxied | Box | Service |
|------|------|-----------|---------|-----|---------|
| `api.int.mitechconsult.com` | A | `100.72.169.40` | false | OVH-1 | agentos-api |
| `chat.int.mitechconsult.com` | A | `100.72.169.40` | false | OVH-1 | agent-ui |
| `mcp.int.mitechconsult.com` | A | `100.72.169.40` | false | OVH-1 | ContextForge |
| `tools.int.mitechconsult.com` | A | `100.72.169.40` | false | OVH-1 | SBV |
| `desktop.int.mitechconsult.com` | A | `100.72.169.40` | false | OVH-1 | Kasm |
| `gw.int.mitechconsult.com` | A | `100.72.169.40` | false | OVH-1 | LiteLLM gateway |
| `neo4j.int.mitechconsult.com` | A | `100.119.96.29` | false | OVH-3 | neo4j browser |
| `milvus.int.mitechconsult.com` | A | `100.119.96.29` | false | OVH-3 | Milvus |
| `attu.int.mitechconsult.com` | A | `100.119.96.29` | false | OVH-3 | Attu |

**Total private records: 9** (6 on OVH-1, 3 on OVH-3).

### 2b. PUBLIC TWIN A records (only with `--include-public`)

| Name | Type | Target IP | Proxied | Box | Service | Posture |
|------|------|-----------|---------|-----|---------|---------|
| `api.mitechconsult.com` | A | `40.160.5.19` | **true** | OVH-1 | agentos-api | default-blocked |
| `chat.mitechconsult.com` | A | `40.160.5.19` | **true** | OVH-1 | agent-ui | default-blocked |
| `mcp.mitechconsult.com` | A | `40.160.5.19` | **true** | OVH-1 | ContextForge | default-blocked |

**Total public twins: 3.** Orange-clouded so each can be gated/blocked at the Cloudflare edge (WAF rule / "Block" custom rule / Access policy). Treat as **default-blocked** at creation; open per-service deliberately.

### 2c. Existing records (do NOT duplicate)
| Name | Target | Proxied | Note |
|------|--------|---------|------|
| `coolify.mitechconsult.com` | `74.208.130.34` | false | leave as-is |
| `n8n.mitechconsult.com` | `74.208.130.34` | false | leave as-is |
| `milvus.mitechconsult.com` | `51.81.83.191` | false | **REPOINT — see §3** |
| `attu.mitechconsult.com` | `51.81.83.191` | false | **REPOINT — see §3** |

## 3. milvus / attu repoint (OVH-2 → OVH-3) — FLAGGED, not auto-applied

There are **existing bare** records `milvus.mitechconsult.com` and `attu.mitechconsult.com`
pointing at `51.81.83.191` (**OVH-2**). Milvus and Attu are moving to **OVH-3**.

- These are **separate** from the new `.int` private records in §2a. The `.int` twins are
  fresh creates; these bare hostnames are the legacy public names.
- The script **flags** these as explicit UPDATE operations but will **not** change them on a
  normal `--apply`. They require the extra `--apply-repoints` flag (and human confirmation),
  because they touch live, pre-existing records.

| Name | From (OVH-2) | To (OVH-3) | Proxied | Action |
|------|--------------|-----------|---------|--------|
| `milvus.mitechconsult.com` | `51.81.83.191` | `147.135.79.183` | false | UPDATE (confirm) |
| `attu.mitechconsult.com` | `51.81.83.191` | `147.135.79.183` | false | UPDATE (confirm) |

> Decision still open: keep these legacy **bare** public names at all, or retire them in favor
> of `milvus.int.` / `attu.int.` private-only. Flagged for owner sign-off before any change.

## 4. Script behavior (`create-dns.mjs`)

| Flag | Effect |
|------|--------|
| _(none)_ | **DRY-RUN**, private `.int` only. Lists existing, prints create/update/no-op plan + repoint flags. No writes. |
| `--apply` | Applies private `.int` creates/updates. |
| `--include-public` | Adds the 3 public twins to the plan (combine with `--apply` to write them). |
| `--apply-repoints` | Additionally applies the milvus/attu OVH-2→OVH-3 updates. |
| `--env <path>` | Override token file (default `C:\Users\matts\.secrets\cloudflare.env`). |

Idempotency: lists all zone A records first, keys by FQDN; **creates** if absent, **updates**
only if `content`/`proxied`/`type` differ, otherwise **no-op**. Re-running is safe. Token is
read from the env file and never printed. Required token scope: `Zone.DNS:Edit`.

## 5. Traefik base-domain + DNS-01 conventions (Coolify)

Goal: route `<svc>.int.mitechconsult.com` → the service container with **valid public TLS**,
even though the name resolves to a tailnet IP that no public ACME HTTP-01 challenge can reach.
Solution: **Cloudflare DNS-01** challenge — the cert is proved by writing a TXT record in the
zone, so the host's reachability is irrelevant. Works for private/tailnet IPs.

### 5a. Traefik static config — Cloudflare DNS-01 resolver

```yaml
# traefik static (Coolify: add to the proxy's traefik.yml / dynamic env)
entryPoints:
  web:        { address: ":80" }
  websecure:  { address: ":443" }
  # NOTE: host port 8080 deliberately left FREE (no entrypoint, no dashboard bind).

certificatesResolvers:
  cloudflare:
    acme:
      email: matt.salem85@gmail.com
      storage: /letsencrypt/acme.json
      dnsChallenge:
        provider: cloudflare
        resolvers: ["1.1.1.1:53", "8.8.8.8:53"]
```

```bash
# Proxy container env — scoped CF token with Zone.DNS:Edit on mitechconsult.com.
# Use the modern API-token vars (NOT the legacy global-key CF_API_EMAIL/CF_API_KEY):
CF_DNS_API_TOKEN=<token from cloudflare.env>
```

### 5b. Per-service router labels (the convention)

Every service container carries labels in this shape (swap `<svc>`):

```yaml
labels:
  - "traefik.enable=true"
  # ---- PRIVATE router: <svc>.int.mitechconsult.com over TLS via DNS-01 ----
  - "traefik.http.routers.<svc>-int.rule=Host(`<svc>.int.mitechconsult.com`)"
  - "traefik.http.routers.<svc>-int.entrypoints=websecure"
  - "traefik.http.routers.<svc>-int.tls=true"
  - "traefik.http.routers.<svc>-int.tls.certresolver=cloudflare"
  # request the cert explicitly so it issues even before first hit:
  - "traefik.http.routers.<svc>-int.tls.domains[0].main=<svc>.int.mitechconsult.com"
  # internal container port the app actually listens on:
  - "traefik.http.services.<svc>.loadbalancer.server.port=<container_port>"
```

Optional **public twin** router (api/chat/mcp only) — distinct router name, same service,
public Host, kept default-blocked at the CF edge:

```yaml
  - "traefik.http.routers.<svc>-pub.rule=Host(`<svc>.mitechconsult.com`)"
  - "traefik.http.routers.<svc>-pub.entrypoints=websecure"
  - "traefik.http.routers.<svc>-pub.tls=true"
  - "traefik.http.routers.<svc>-pub.tls.certresolver=cloudflare"
```

> With Coolify you usually set the service **FQDN** to `https://<svc>.int.mitechconsult.com`
> and Coolify generates equivalent labels; the static `certificatesResolvers.cloudflare`
> block + `CF_DNS_API_TOKEN` is the one piece you add manually. Confirm Coolify isn't also
> binding port 8080 for its own proxy dashboard — keep 8080 free.

### 5c. Sample fully-labeled service — `api` (agentos-api, OVH-1, container port 8000)

```yaml
services:
  agentos-api:
    image: ghcr.io/your-org/agentos-api:latest
    labels:
      - "traefik.enable=true"
      # PRIVATE
      - "traefik.http.routers.api-int.rule=Host(`api.int.mitechconsult.com`)"
      - "traefik.http.routers.api-int.entrypoints=websecure"
      - "traefik.http.routers.api-int.tls=true"
      - "traefik.http.routers.api-int.tls.certresolver=cloudflare"
      - "traefik.http.routers.api-int.tls.domains[0].main=api.int.mitechconsult.com"
      - "traefik.http.services.api.loadbalancer.server.port=8000"
      # PUBLIC TWIN (default-blocked at CF edge)
      - "traefik.http.routers.api-pub.rule=Host(`api.mitechconsult.com`)"
      - "traefik.http.routers.api-pub.entrypoints=websecure"
      - "traefik.http.routers.api-pub.tls=true"
      - "traefik.http.routers.api-pub.tls.certresolver=cloudflare"
    networks: [coolify]
```

### 5d. Per-service router naming (apply the §5b template to each)

| Service | Private router | Host | Public router | Container port (verify) |
|---------|----------------|------|---------------|------------------------|
| api | `api-int` | `api.int.…` | `api-pub` | 8000 |
| chat | `chat-int` | `chat.int.…` | `chat-pub` | 3000 |
| mcp | `mcp-int` | `mcp.int.…` | `mcp-pub` | 8811 |
| tools | `tools-int` | `tools.int.…` | — | — |
| desktop | `desktop-int` | `desktop.int.…` | — | 6901 |
| gw | `gw-int` | `gw.int.…` | — | 4000 |
| neo4j | `neo4j-int` | `neo4j.int.…` | — | 7474 |
| milvus | `milvus-int` | `milvus.int.…` | — | 9091 |
| attu | `attu-int` | `attu.int.…` | — | 3000 |

> Container ports above are typical defaults and must be **verified per image** before applying.

## 6. Open items / confirmations needed
1. milvus/attu repoint (OVH-2→OVH-3): apply update vs. retire bare names — owner sign-off.
2. Confirm Coolify proxy does not claim host port **8080**.
3. Verify each service's real container port (§5d) before generating labels.
4. Decide edge-gating mechanism for public twins (CF WAF custom rule vs. Cloudflare Access).
