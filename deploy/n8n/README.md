# n8n deploy (box 2 — IONOS `74.208.130.34`)

Standalone n8n + Postgres, separate from the agno-mvp platform stack (ADR-0007/0009).

## First deploy (on the host)
```bash
cd ~/n8n
# Generate secrets ONCE (rotating N8N_ENCRYPTION_KEY later breaks stored credentials):
[ -f .env ] || cat > .env <<EOF
POSTGRES_USER=n8n
POSTGRES_DB=n8n
POSTGRES_PASSWORD=$(openssl rand -hex 24)
N8N_ENCRYPTION_KEY=$(openssl rand -hex 32)
N8N_USER_MANAGEMENT_JWT_SECRET=$(openssl rand -hex 32)
TIMEZONE=America/Detroit
EOF
docker compose up -d
```

- UI: http://74.208.130.34:5678 — create the **owner account** on first visit.
- `.env` holds secrets and is **never committed** (host-only).
- `WEBHOOK_URL` / `N8N_HOST` are set to the public IP; change them if you put a domain/HTTPS proxy in front.

## Notes
- Plain HTTP on a public IP → `N8N_SECURE_COOKIE=false` so login works. Add a reverse proxy + TLS for production.
- n8n can drive the agno-mvp platform via its REST API (box 1) — see ADR-0007.
- Optional later: mount the Cloudflare R2 volume here if workflows need shared blob storage.
