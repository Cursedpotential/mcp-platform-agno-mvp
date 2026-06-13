# Docker Compose & Podman — Skill Reference

## Overview
- **What**: Orchestration of dial-stack microservices via Docker or Podman
- **Version**: Compose v2+
- **Category**: Infrastructure/Orchestration
- **Installed In**: Local development and deployment environments

## Configuration

### Key Services in docker-compose.yml
```yaml
services:
  dial-core:
    image: epam/dial-core:0.25.1
    ports: ["8080:8080"]

  postgres:
    image: pgvector/pgvector:pg15
    environment:
      POSTGRES_PASSWORD: ${PG_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data

  neo4j:
    image: neo4j:5.13
    environment:
      NEO4J_AUTH: neo4j/${NEO4J_PASSWORD}
    ports: ["7687:7687", "7474:7474"]

  duckdb:
    image: duckdb/duckdb:latest
    # DuckDB typically runs as embedded library

  lancedb:
    build: ./services/lancedb
    environment:
      LANCEDB_DATA_DIR=/data

  dragonfly:
    image: docker.dragonflydb.io/dragonfly:latest
    ports: ["6379:6379"]

  keycloak:
    image: keycloak/keycloak:latest
    environment:
      KEYCLOAK_ADMIN: ${KEYCLOAK_ADMIN}
      KEYCLOAK_ADMIN_PASSWORD: ${KEYCLOAK_ADMIN_PASSWORD}
```

### Networking
```yaml
networks:
  dial-network:
    driver: bridge
```

All services connect to `dial-network` for inter-service communication.

### Volumes
```yaml
volumes:
  postgres_data:
  neo4j_data:
  keycloak_data:
```

## API Patterns

- **Service Discovery**: Services reference each other by hostname (e.g., `http://postgres:5432`)
- **Port Exposure**: Only frontend-facing services expose ports
- **Health Checks**: Add `healthcheck` blocks for critical services
- **Environment Variables**: Load from `.env` file

## Integration Points

- **Scaling**: Use `docker-compose up -d --scale <service>=N` for horizontal scaling
- **Networking**: All services on `dial-network` can communicate by service name
- **Volume Mounts**: Bind local code to containers for development
- **Depends On**: Use `depends_on` for startup ordering (not a guarantee of readiness)

## Common Pitfalls

- **Timing**: `depends_on` doesn't wait for service readiness, only startup. Use health checks.
- **Environment Variables**: Not interpolated in non-compose files; use `.env` or export
- **Podman vs Docker**: Podman rootless mode requires different volume permission handling
- **Port Conflicts**: Ensure all exposed ports are available before `up`
- **Data Persistence**: Volumes survive `docker-compose down` but not `down -v`

## References
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Podman Compose](https://github.com/containers/podman-compose)
- [Health Checks](https://docs.docker.com/compose/compose-file/compose-file-v3/#healthcheck)
