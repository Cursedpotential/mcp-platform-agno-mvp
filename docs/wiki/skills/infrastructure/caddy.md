# Caddy — Skill Reference

## Overview
- **What**: Lightweight reverse proxy with automatic HTTPS (Let's Encrypt) and extensible middleware
- **Version**: v2.7+
- **Category**: Infrastructure/Gateway
- **Installed In**: Docker container `caddy`

## Configuration

### Caddyfile Pattern
```
example.com {
  reverse_proxy localhost:8080

  # Basic auth fallback for DIAL Core
  basic_auth /api/* {
    ${AUTH_USER} ${AUTH_PASS_BCRYPT}
  }

  # Auto-TLS via Let's Encrypt
  tls {
    on_demand
  }
}

:6379 {
  # Dragonfly (Redis) proxy
  reverse_proxy localhost:6379
}
```

### Environment Variables
```bash
CADDY_EMAIL=admin@example.com        # For Let's Encrypt certificate registration
CADDY_ACME_STAGING=false             # Set to true for testing
CADDY_LOG_LEVEL=info
```

## API Patterns

- **Transparent Proxying**: All requests routed transparently to backend services
- **Header Manipulation**: Add/remove headers for backend compatibility
- **Path Rewriting**: Can rewrite paths before forwarding (e.g., `/chat` → `/v1/chat`)
- **Rate Limiting**: Use `rate_limit` directive for API throttling

```
dial.example.com {
  rate_limit /chat/* 10r/s
  reverse_proxy localhost:8080
}
```

## Integration Points

- **DIAL Chat UI**: Frontend requests → Caddy → DIAL Core `:8080`
- **PostgreSQL**: Optional TCP proxy for remote connections
- **Keycloak**: Can protect endpoints with OIDC middleware
- **TLS**: Automatic certificate renewal without manual intervention

## Common Pitfalls

- **Let's Encrypt Rate Limits**: Staging environment recommended for testing (50 fails/3 hours)
- **CORS Headers**: DIAL Core must handle CORS; Caddy doesn't add them automatically
- **WebSocket Upgrades**: Use `reverse_proxy ... {websocket}` for real-time connections
- **DNS Propagation**: Ensure DNS is correct before requesting certificate
- **Basic Auth Encoding**: Passwords must be bcrypt-hashed; use `caddy hash-password`

## References
- [Caddy Documentation](https://caddyserver.com/docs/)
- [Automatic HTTPS](https://caddyserver.com/docs/automatic-https)
- [Reverse Proxy Directive](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy)
