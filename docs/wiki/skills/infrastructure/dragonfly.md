# Dragonfly — Skill Reference

## Overview
- **What**: Redis-compatible in-memory cache and datastore optimized for modern CPUs. Drop-in Redis replacement.
- **Version**: Latest stable
- **Category**: Infrastructure/Cache
- **Installed In**: Docker container `dragonfly` (port 6379)

## Configuration

### Docker Compose Service
```yaml
dragonfly:
  image: docker.dragonflydb.io/dragonfly:latest
  ports: ["6379:6379"]
  environment:
    DFLY_MAXMEMORY: 2gb
    DFLY_MAXMEMORY_POLICY: allkeys-lru
  volumes:
    - dragonfly_data:/data
  command: dragonfly --port 6379 --save_dir /data
```

### Key Commands
```bash
# Connection (Redis CLI compatible)
redis-cli -h localhost -p 6379

# Memory inspection
INFO memory

# Key expiry for sessions
SET session:uuid:abc {...} EX 3600
```

## API Patterns

- **Session Storage**: Cache user sessions with `EX` (expire seconds) flag
- **Embedding Cache**: Store vectorized embeddings for fast retrieval
- **Rate Limit Counters**: Atomic increment for API throttling
- **Pub/Sub**: Optional real-time event distribution
- **Stream Aggregation**: `XADD`, `XREAD` for event logs

## Integration Points

- **DIAL Core**: Cache authentication tokens and model routing metadata
- **Semantica NLP**: Store intermediate embeddings and processing state
- **PostgreSQL**: Secondary cache layer (faster than disk reads)
- **Frontend Sessions**: CopilotKit and DIAL Chat store user state

## Common Pitfalls

- **Memory Limits**: Set `MAXMEMORY` and eviction policy explicitly to prevent OOM
- **Persistence**: By default Dragonfly persists to disk; disable with `--nobackup` if ephemeral
- **Redis Compatibility**: Most commands work, but some niche features differ; check docs
- **Connection Pooling**: Many clients need connection pooling for concurrent access
- **Data Type Mismatches**: String/List/Hash boundaries matter; wrong type = operation failure

## References
- [Dragonfly Documentation](https://www.dragonflydb.io/docs)
- [Redis Commands](https://redis.io/docs/latest/commands/)
- [Memory Management](https://www.dragonflydb.io/docs/managing-memory)
