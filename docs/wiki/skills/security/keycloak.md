# Keycloak — Skill Reference

## Overview
- **What**: OpenID Connect (OIDC) identity provider. Central authentication and role management for dial-stack.
- **Version**: Latest stable
- **Category**: Security/Authentication
- **Installed In**: Docker container `keycloak` (port 8080)

## Configuration

### Docker Setup
```yaml
keycloak:
  image: keycloak/keycloak:latest
  environment:
    KEYCLOAK_ADMIN: ${KEYCLOAK_ADMIN}
    KEYCLOAK_ADMIN_PASSWORD: ${KEYCLOAK_ADMIN_PASSWORD}
    KC_DB: postgres
    KC_DB_URL: jdbc:postgresql://postgres:5432/keycloak
    KC_DB_USERNAME: ${KC_DB_USER}
    KC_DB_PASSWORD: ${KC_DB_PASSWORD}
  ports:
    - "8080:8080"
  volumes:
    - keycloak_data:/data
```

### Realm Configuration
```json
{
  "realm": "dialstack",
  "enabled": true,
  "accessTokenLifespan": 3600,
  "refreshTokenLifespan": 86400,
  "clients": [
    {
      "clientId": "dial-chat",
      "clientAuthenticatorType": "client-secret",
      "redirectUris": ["https://chat.example.com/*"],
      "webOrigins": ["https://chat.example.com"],
      "protocol": "openid-connect",
      "standardFlowEnabled": true
    }
  ]
}
```

## API Patterns

- **OIDC Token Endpoint**: `POST /realms/dialstack/protocol/openid-connect/token`
- **User Info**: `GET /realms/dialstack/protocol/openid-connect/userinfo` (Bearer token required)
- **Logout**: `POST /realms/dialstack/protocol/openid-connect/logout`
- **Token Introspection**: `POST /realms/dialstack/protocol/openid-connect/token/introspect`

## Integration Points

- **DIAL Chat UI**: Uses OIDC implicit flow for user login
- **Caddy**: Optional basic auth fallback when Keycloak unavailable
- **Backend Services**: Validate JWT tokens from Keycloak issuer
- **Role Mapping**: Analyst, reviewer, admin roles control access
- **Session Management**: Refresh tokens handle long-lived sessions

### JWT Structure
```json
{
  "sub": "user-uuid",
  "preferred_username": "analyst@example.com",
  "realm_access": { "roles": ["analyst", "reviewer"] },
  "resource_access": { "dial-chat": { "roles": ["user"] } },
  "iat": 1234567890,
  "exp": 1234571490
}
```

## Common Pitfalls

- **Client Secret Exposure**: Secrets must never be embedded in SPA; use backend-for-frontend pattern
- **Redirect URI Mismatch**: HTTPS required in production; localhost exceptions only for dev
- **Token Expiry**: JWT expiry enforced; refresh token flow required for long sessions
- **Realm Isolation**: Separate realms for staging/prod prevent credential leakage
- **CORS Configuration**: Keycloak CORS must allow frontend domain; misconfig breaks auth flow

## References
- [Keycloak Documentation](https://www.keycloak.org/documentation)
- [OpenID Connect Protocol](https://openid.net/connect/)
- [JWT Best Practices](https://tools.ietf.org/html/rfc8725)
- [Admin REST API](https://www.keycloak.org/docs/latest/admin_rest_api/)
