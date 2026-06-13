# Directus Integration for Dial-Stack

## Overview

Directus is a headless CMS that provides a real-time API and no-code dashboard for SQL database content. It will serve as the file upload interface and workflow automation engine for Dial-Stack.

## Key Capabilities

| Feature | Description |
|---------|-------------|
| **File Upload** | Web UI for importing files via URL or upload |
| **PostgreSQL Native** | Direct table access with Knex.js |
| **Webhooks** | Trigger processing pipeline after upload |
| **Flows** | Visual workflow automation |
| **Custom Endpoints** | Extend API for external services |
| **MCP Server** | `@directus/content-mcp@latest` for AI integration |

## Installation

```bash
# npm
npm install directus

# Docker
docker run -p 8055:8055 directus/directus
```

## Configuration for Dial-Stack

### Database Connection
```yaml
# docker-compose.yml
services:
  directus:
    image: directus/directus:latest
    ports:
      - "8055:8055"
    environment:
      DB_CLIENT: pg
      DB_HOST: postgres
      DB_PORT: 5432
      DB_DATABASE: evidence_db
      DB_USER: directus
      DB_PASSWORD: ${DB_PASSWORD}
      KEY: ${DIRECTUS_KEY}
      SECRET: ${DIRECTUS_SECRET}
      ADMIN_EMAIL: admin@example.com
      ADMIN_PASSWORD: ${ADMIN_PASSWORD}
    volumes:
      - ./extensions:/directus/extensions
      - ./uploads:/directus/uploads
```

### Required Extensions
```sql
-- PostgreSQL extensions for Dial-Stack
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_duckdb;
```

## Processing Pipeline Integration

### Webhook Configuration
```javascript
// Directus Flow Trigger: files.upload
// Operation: Webhook / Request URL

{
  "method": "POST",
  "url": "http://evidence-processor:3000/api/process",
  "body": {
    "file_id": "{{payload.id}}",
    "file_path": "{{payload.filename_disk}}",
    "storage": "{{payload.storage}}",
    "uploaded_by": "{{payload.uploaded_by}}"
  }
}
```

### Custom Endpoint for MCP
```javascript
// extensions/endpoints/custom/api.js
export default ({ services, database }) => ({
  '/mcp-tools/ingest': async (req, res) => {
    const { FilesService } = services;
    const filesService = new FilesService({ knex: database, schema: req.schema });
    
    // Trigger DuckDB processing
    const result = await fetch('http://duckdb-processor:4001/process', {
      method: 'POST',
      body: JSON.stringify({ file_id: req.body.id })
    });
    
    res.json({ status: 'processing', file_id: req.body.id });
  }
});
```

## MCP Server Integration

### Installation
```bash
npm install @directus/content-mcp@latest
```

### Available Tools
| Tool | Description |
|------|-------------|
| `items` | CRUD operations on collections |
| `files` | File upload and management |
| `folders` | Folder organization |
| `flows` | Trigger automated workflows |
| `trigger-flow` | Execute flows programmatically |
| `schema` | Inspect database schema |
| `collections` | Collection management |
| `fields` | Field configuration |

### Usage Example
```javascript
// MCP tool call
{
  "name": "items",
  "arguments": {
    "collection": "evidence",
    "action": "create",
    "data": {
      "file_path": "/evidence/2024/03/file.pdf",
      "platform": "imessage",
      "participant": "sender@example.com"
    }
  }
}
```

## PostGIS Integration

Directus supports PostGIS columns for geospatial data:

```javascript
// Collection schema with PostGIS
{
  "fields": [
    {
      "field": "location",
      "type": "geometry",
      "meta": {
        "interface": "map",
        "options": {
          "geometryType": "Point"
        }
      }
    }
  ]
}
```

## pg_vector Integration

Directus supports vector columns for embeddings:

```javascript
// Collection schema with vector field
{
  "fields": [
    {
      "field": "embedding",
      "type": "vector",
      "meta": {
        "special": ["cast-numeric"]
      }
    }
  ]
}
```

## Flows (Workflow Automation)

### Evidence Processing Flow
```yaml
# .directus/flows/evidence-processing.yaml
name: Evidence Processing Pipeline
trigger: files.upload
operations:
  - type: webhook
    url: http://hash-service:4002/hash
    method: POST
  - type: condition
    condition: "{{payload.file_hash != null}}"
  - type: webhook
    url: http://postgres-service:5432/api/normalize
    method: POST
  - type: webhook
    url: http://lancedb-service:4003/embed
    method: POST
  - type: webhook
    url: http://semantica-service:4004/extract
    method: POST
```

## Resources

- **Official Docs**: https://docs.directus.io/
- **GitHub**: https://github.com/directus/directus
- **MCP Server**: https://www.npmjs.com/package/@directus/content-mcp
- **PostgreSQL Extensions**: https://docs.directus.io/configuration/config-options.html#database

## Related

- [pg_duckdb](../database/extensions/PG_DUCKDB.md) - DuckDB in PostgreSQL
- [PostGIS](../database/extensions/PostGIS.md) - Geospatial queries
- [pg_vector](../database/extensions/PG_VECTOR.md) - Vector similarity
- [WunderGraph Cosmo](../orchestration/wundergraph-cosmo.md) - GraphQL federation