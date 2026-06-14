# Platform Infrastructure & Deployment Topology — SANITIZED TEMPLATE

> **This is a sanitized structural copy committed for backup.**
> Real credential values live in the gitignored `docs/INFRASTRUCTURE.md` and `Secrets/` directory.
> Never commit those files. Restore real values from your local copy or your secure credential store.
>
> _Byline: Claude Code · Opus 4.8 · 2026-06-14_

---

## 1. Topology at a glance

```
                 ┌─────────────────────────────┐
   Internet ───▶ │  Cloudflare DNS              │  mitechconsult.com
                 │  zone <CLOUDFLARE_ZONE_ID>   │  (A records → workers' PUBLIC IPs, DNS-only)
                 └──────────────┬──────────────┘
                                │ public 80/443 (Let's Encrypt HTTP-01)
        ┌───────────────────────┼────────────────────────┐
        ▼                       ▼                         ▼
┌───────────────┐       ┌───────────────┐        ┌───────────────┐
│  IONOS         │  SSH  │  OVH-1         │        │  OVH-2         │
│  Coolify CP    │──────▶│  agno box      │        │  worker        │
│  (control)     │ tailnet│ (Agno rebuild) │        │ (n8n + Milvus) │
└───────────────┘       └───────────────┘        └───────────────┘
   Coolify 4.1.2          Traefik proxy            Traefik proxy
   manages ▶ both OVH workers over TAILSCALE IPs (SSH never public)
```

- **Control plane = Coolify on IONOS.** Apps deploy to the OVH workers; the control plane stays light.
- **Coolify → workers** over **Tailscale** (private SSH, user `root`). SSH is never exposed publicly.
- **Public app ingress** = each worker's own **Traefik** proxy on its **public** IP, with **Let's Encrypt auto-TLS**.
  TLS and Tailscale are independent planes — no conflict.

## 2. Hosts

| Role                                 | Host  | SSH                  | Public IP     | Tailnet IP     | Specs                          |
| ------------------------------------ | ----- | -------------------- | ------------- | -------------- | ------------------------------ |
| Coolify control plane (+ old n8n)    | IONOS | `ssh ionos` (debian) | 74.208.130.34 | 100.98.98.38   | Ubuntu 24.04 · 2 vCPU / 3.8 GB |
| Agno box (rebuild — **other agent**) | OVH-1 | `ssh ovh1` (debian)  | 40.160.5.19   | 100.72.169.40  | Docker host                    |
| Worker: n8n + Milvus                 | OVH-2 | `ssh ovh2` (ubuntu)  | 51.81.83.191  | 100.91.190.107 | Ubuntu 26.04 · 4 vCPU / 7.6 GB |

- SSH key for all three: `~/.ssh/ovh` (ed25519). Aliases in `~/.ssh/config`: `ionos` / `ovh1` / `ovh2` (+ `-ts` tailnet variants).
- Tailnet: `tilapia-skilift.ts.net`.

## 3. Coolify control plane

- **Version:** 4.1.2 (healthy)
- **Dashboard:** `http://74.208.130.34:8000` · tailnet `http://100.98.98.38:8000` · FQDN `https://coolify.mitechconsult.com` (DNS created; instance-FQDN TLS not yet enabled)
- **API base (external):** use **tailnet** `http://100.98.98.38:8000/api/v1` — public `:8000` is **firewalled**. From the IONOS box itself, `http://localhost:8000/api/v1` works.
- **Registered servers:** `localhost` (Ionos) · `ovh1-agno` (uuid `<COOLIFY_SERVER_UUID_OVH1>`) · `ovh2-worker` (uuid `<COOLIFY_SERVER_UUID_OVH2>`). Shared SSH key uuid `<COOLIFY_SSH_KEY_UUID>`. Both OVH servers reachable + usable.

## 4. Workload split (two agents, one Coolify)

| Owner           | Scope                                                                            |
| --------------- | -------------------------------------------------------------------------------- |
| **This agent**  | Coolify control plane, server registration, Cloudflare DNS/TLS, **n8n** on OVH-2 |
| **Other agent** | **Agno** rebuild on OVH-1 (Coolify-friendly), **Milvus** stack on OVH-2          |

- **OVH-2 is shared** (n8n + Milvus). Keep n8n's footprint small + memory-limited so it doesn't starve Milvus.
- **Volumes: always bind-mount host dirs, never named volumes** (owner backs up via host dirs).

## 5. Ingress / DNS conventions

- App subdomains under `mitechconsult.com`, e.g. `coolify.` `n8n.` `agno.` `app-*.`
- Each record: **A → the worker's PUBLIC IP**, **DNS-only (grey cloud)** so Let's Encrypt HTTP-01 reaches the origin.
- Created so far: `coolify.mitechconsult.com → 74.208.130.34` (DNS-only).

## 6. n8n — fresh deploy on OVH-2 (NOT a migration)

The old n8n on IONOS was a throwaway deploy (never logged in, no workflows/credentials). **Discard it** — no data to carry over. Stand up a clean n8n on OVH-2 via Coolify. Config decisions tracked in §8 / discussion. After OVH-2 n8n is verified, **decommission the IONOS n8n** (`/home/debian/n8n` compose, containers `n8n` + `n8n-db`).

## 7. Known gotchas

- **OVH-1 :8080 collision (resolved).** Old Agno `platform-tools` published host 8080; Coolify's Traefik also wants 8080 → proxy failed. Other agent tore down old Agno (freed 8080); proxy came up healthy. ovh1 Coolify proxy flag was toggled to NONE then **left as-is ("let it ride")** per owner — revisit when finalizing OVH-1 ingress.
- **Public `:8000` firewalled** — drive the Coolify API via tailnet or from the IONOS box.
- **OVH-1 root login** required stripping the Debian cloud-image forced-command guard from `/root/.ssh/authorized_keys` (`.bak` kept) so Coolify can connect as root.

## 8. Open decisions / next steps

- [ ] n8n on OVH-2: database (Postgres vs SQLite), deploy method (Coolify template vs compose), version pinning, queue mode, explicit encryption key — **see discussion**.
- [ ] Enable Coolify instance FQDN + dashboard TLS (`coolify.mitechconsult.com`).
- [ ] Decommission IONOS n8n after OVH-2 n8n verified.
- [ ] Revoke the one-time Tailscale auth key; rotate the Cloudflare token (passed through chat).
- [ ] Finalize OVH-1 proxy strategy with the other agent once Agno rebuild lands.

## Credential stores

- **`<repo>/Secrets/infra-access.md`** — gitignored; canonical infra creds (Coolify token, host passwords, SSH). Maintained jointly.
- **`~/.secrets/`** — `PLATFORM_ACCESS.md` (master), `coolify-ionos-api.env`, `coolify-ionos.env` (instance .env backup), `cloudflare.env`.
- **`<repo>/Agno-MCP-Platform/.env`** — gitignored; Tailscale API key, etc.
- **Never** commit secrets or ingest them into Knowledge.
