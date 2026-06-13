# Remediation #1: Remove Direct Port Exposure on MCP Servers

## Context

Security review found that `docker-compose.yml` exposes MCP server ports (8081, 8082) directly to the host, bypassing DIAL Core's Keycloak JWT auth. DIAL Core on port 8080 is the intended auth gateway. Direct access to MCP servers lets anyone call `postgres_raw_query` without authentication.

## Change

In `docker-compose.yml`, change the port mappings for `ts-mcp-server` and `py-mcp-server` from host-exposed to internal-only:

**ts-mcp-server (line 137):**
```yaml
# BEFORE:
ports:
  - "8081:8081"

# AFTER:
expose:
  - "8081"
```

**py-mcp-server (line 146):**
```yaml
# BEFORE:
ports:
  - "8082:8000"

# AFTER:
expose:
  - "8000"
```

`expose` makes the port available to other Docker services (DIAL Core can still route to them) but NOT to the host machine.

## Files Modified
- `dial-stack/docker-compose.yml` — 2 port mapping changes

## Verification
- `docker compose config` shows no host port bindings for ts-mcp-server or py-mcp-server
- DIAL Core can still reach both servers via internal Docker DNS (`ts-mcp-server:8081`, `py-mcp-server:8000`)
- Direct `curl localhost:8081/mcp` from the host should fail (connection refused)
- `curl localhost:8080` (DIAL Core) still works and routes to MCP servers through auth

## Also: Secrets question for user

Before tackling remediation #2, need to resolve the secrets approach. Presenting as a question alongside this plan.
