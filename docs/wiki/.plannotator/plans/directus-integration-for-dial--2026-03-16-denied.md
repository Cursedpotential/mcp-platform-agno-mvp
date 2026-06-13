# Directus Integration for Dial-Stack Forensic Platform

## Executive Summary

Directus is an excellent fit for dial-stack. It provides:
- **Instant admin UI** for all PostgreSQL evidence tables (replaces port 3002 React dashboard)
- **Native MCP support** for AI tool integration
- **Flows automation** for workflow orchestration
- **GraphQL federation candidate** (with custom work)
- **Extension system** for custom panels, operations, and endpoints

**Recommendation**: Directus can replace the custom React+CopilotKit dashboard AND provide workflow orchestration via Flows. Wiki functionality requires external integration (Wiki.js recommended).

---

## Research Completed

### 1. Directus MCP Implementation ✓

**Native MCP Server** (v11.12+):
- Package: `@directus/content-mcp@latest`
- Configuration: `{ DIRECTUS_URL, DIRECTUS_TOKEN }` or email/password auth
- **Remote MCP Tools** (unified):
  - `items` - Single tool for all CRUD operations (vs. separate read/create/update/delete in local)
  - `files`, `folders`, `assets` - File management
  - `flows`, `trigger-flow` - Workflow automation
  - `schema`, `collections`, `fields`, `relations` - Schema introspection
  
- **Local MCP Tools** (granular):
  - `read-collections`, `read-items`, `create-item`, `update-item`, `delete-item`
  - `read-files`, `import-file`, `update-files`
  - `read-fields`, `read-field`, `create-field`, `update-field`
  - `read-flows`, `trigger-flow`
  - `users-me`, `system-prompt`
  - `markdown-tool`, `get-prompts`, `get-prompt`

**Security**:
- Respects existing RBAC and permissions
- Audit logging of all AI operations
- Can disable specific operations (e.g., schema modifications)
- Can make read-only

**For dial-stack**: MCP tools can directly manipulate evidence tables, trigger analysis flows, and query schema. Much simpler than building custom MCP tools.

---

### 2. Custom Operations for Flows ✓

**Architecture**:
- `app.js` - UI configuration for Data Studio
- `api.js` - Server-side logic (JS/TS)
- Can import npm packages (e.g., `lodash`)

**Example Operation** (lodash):
```javascript
// app.js
export default {
  id: 'lodash-camelcase',
  name: 'Lodash Camel Case',
  icon: 'electric_bolt',
  options: [
    {
      field: 'text',
      name: 'Text',
      type: 'string',
      meta: { interface: 'input', width: 'full' }
    }
  ]
};

// api.js
import { defineOperationApi } from '@directus/extensions-sdk';
import { camelCase } from 'lodash';

export default defineOperationApi({
  id: 'lodash-camelcase',
  handler: ({ text }) => ({
    text: camelCase(text)
  })
});
```

**For dial-stack**: Create custom operations for:
- Hash calculation with verification
- Chain-of-custody record creation
- Evidence metadata extraction
- Tool result aggregation

---

### 3. Custom Endpoint Extensions (API Proxying) ✓

**Architecture**:
```javascript
export default {
  id: 'mcp-proxy',
  handler: (router, { services, database, getSchema, env, logger, emitter }) => {
    // MCP tool proxy
    router.post('/tools/:toolName', async (req, res) => {
      const { toolName } = req.params;
      const user = req.accountability?.user;
      
      // Authenticate user
      const { ItemsService } = services;
      const users = new ItemsService('directus_users', { schema: await getSchema() });
      const authenticatedUser = await users.readOne(user);
      
      if (!authenticatedUser) {
        return res.status(403).json({ error: 'Forbidden' });
      }
      
      // Proxy to MCP tool servers
      const response = await fetch(`http://localhost:8081/${toolName}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(req.body)
      });
      
      res.json(await response.json());
    });
  }
};
```

**URL Pattern**: `https://your-directus.com/mcp-proxy/tools/calculate_hash`

**For dial-stack**: Proxy to TS/Python/JS MCP tools at ports 8081/8082/8083 while maintaining Directus auth.

---

### 4. Insights Dashboards & Panels ✓

**Architecture**:
- Drag-and-drop canvas
- Multiple panels per dashboard
- Auto-refresh intervals
- Custom panel extensions

**Custom Panel Example** (weather API):
```javascript
// Bundle: directus-extension-bundle-weather
// 1. Endpoint extension - fetches external API
// 2. Panel extension - displays data in Dashboard
```

**For dial-stack**: Create custom panels for:
- Evidence chain visualization
- Tool execution status
- Analysis pipeline progress
- Storage tier statistics

---

### 5. Realtime/WebSockets ✓

**WebSocket Subscriptions**:
```javascript
import { createDirectus, staticToken, realtime } from '@directus/sdk';

const client = createDirectus('https://evidence.example.com')
  .with(staticToken('api_token'))
  .with(realtime());

await client.connect();

// Subscribe to evidence table changes
const { subscription } = await client.subscribe('evidence_items', {
  event: 'create', // or 'update', 'delete'
  query: { fields: ['id', 'hash', 'status', 'chain_of_custody'] }
});

for await (const item of subscription) {
  console.log('Evidence updated:', item);
}
```

**GraphQL Subscriptions**:
```gql
subscription {
  evidence_items_mutated(event: update) {
    key
    data { id hash status }
  }
}
```

**For dial-stack**: Realtime updates when evidence is processed, tool results arrive, or chain of custody changes.

---

### 6. GraphQL & Federation ✓

**Directus GraphQL**:
- Auto-generated from database schema
- `/graphql` for user collections
- `/graphql/system` for Directus metadata
- GraphQL Subscriptions via `graphql-ws`
- Deep query parameter for nested relations

**Federation Compatibility**:
- Directus GraphQL is NOT Apollo Federation compatible out-of-box
- Would require custom federation layer via endpoint extension
- Alternative: Use Directus REST → WunderGraph wrapper

**For dial-stack**: 
- **Option A**: Custom endpoint that exposes federation-compatible schema
- **Option B**: WunderGraph Cosmo introspects Directus REST + GraphQL separately
- **Recommendation**: Option B (simpler, no Directus modifications needed)

---

### 7. Authentication & Permissions ✓

**RBAC Layers**:
1. **Role-level**: Admin, Editor, Viewer roles
2. **Collection-level**: Read/Write to specific tables
3. **Field-level**: Access to specific columns
4. **Item-level**: Filter by `$CURRENT_USER`, custom conditions

**SSO Integration**:
- OAuth (GitHub, Google, etc.)
- OpenID Connect
- LDAP/Active Directory
- 2FA enforcement
- Custom password policies

**Environment Variables**:
```bash
AUTH_GOOGLE_ROLE_MAPPING='{"developers": "uuid-dev", "admins": "uuid-admin"}'
AUTH_OKTA_REDIRECT_ALLOW_LIST="https://app.example.com/callback"
```

**For dial-stack**: Create roles for forensic analysts, reviewers, admins with field-level permissions on sensitive case data.

---

### 8. Wiki/Documentation Management ⚠️

**Directus Has NO Native Wiki**

**Options for dial-stack**:

| Option | Pros | Cons | Effort |
|--------|------|------|--------|
| **Custom Module** | Integrated, single auth, custom UI | Build from scratch, no git history | HIGH |
| **Wiki.js** | Git-backed markdown, mature, flat files | Separate auth, sync complexity | MEDIUM |
| **MkDocs + SSG** | Static site, simple, fast | No live editing, build step | LOW |
| **BookStack** | Book/chapter/page hierarchy, WYSIWYG | Separate auth, not markdown-native | MEDIUM |

**Recommendation**: **Wiki.js** for flat markdown requirement:
- Git-backed storage (meets "flat markdown files" requirement)
- Mature wiki with full editing features
- Can integrate with Directus via webhooks
- Authentication sync via OAuth/OIDC

---

## Integration Patterns for Dial-Stack

### Pattern 1: Frontend Replacement

```
┌─────────────────────────────────────────────────────┐
│                     Directus                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │
│  │ Data Studio │  │   Insights  │  │   Flows     │ │
│  │  (Admin UI) │  │ (Dashboards)│  │(Workflows)  │ │
│  └─────────────┘  └─────────────┘  └─────────────┘ │
│         │                │                │         │
│         └────────────────┴────────────────┘         │
│                          │                           │
│                  ┌───────┴───────┐                   │
│                  │  REST / GQL   │                   │
│                  │  / MCP API    │                   │
│                  └───────┬───────┘                   │
└──────────────────────────┼───────────────────────────┘
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                 │
    ┌────┴────┐      ┌─────┴─────┐     ┌────┴────┐
    │PostgreSQL│      │    S3    │     │  Wiki.js│
    │ Evidence │      │  Storage │     │  (Docs) │
    │  Tables  │      │          │     │         │
    └──────────┘      └──────────┘     └─────────┘
```

**Replaces**: Port 3002 React+CopilotKit dashboard

---

### Pattern 2: Workflow Orchestration

```
┌─────────────────────────────────────────┐
│         Directus Flows                  │
│  ┌───────────┐     ┌───────────────┐   │
│  │  Trigger  │────▶│   Operations  │   │
│  │ (Event/) │     │ • Run Script  │   │
│  │ (Webhook)│     │ • Webhook      │   │
│  │ (Manual) │     │ • Create/Read  │   │
│  │ (CRON)   │     │ • Trigger Flow │   │
│  └───────────┘     └───────┬───────┘   │
└────────────────────────────┼───────────┘
                             │
              ┌──────────────┴──────────────┐
              │         HTTP/HTTPS           │
              └──────────────┬──────────────┘
                            │
    ┌───────────────────────┼───────────────────────┐
    │                       │                       │
┌───┴────┐           ┌─────┴─────┐          ┌──────┴─────┐
│ TS MCP │           │Python MCP│          │  JS MCP    │
│ Server │           │  Server   │          │  Server    │
│ :8081  │           │  :8082   │          │  :8083     │
└────────┘           └───────────┘          └────────────┘
```

**Flows Operations for dial-stack**:
1. **Event Hook** - Trigger on evidence upload (Filter mode for validation)
2. **Webhook** - Call tool servers
3. **Run Script** - Transform data, validate hashes
4. **Trigger Flow** - Chain workflows

---

### Pattern 3: Tool Calling Architecture

```
┌───────────────────────────────────────────────┐
│                    Directus                    │
│  ┌─────────────┐     ┌────────────────────┐   │
│  │  MCP Server │────▶│ Evidence Tables    │   │
│  │(Native MCP) │     │ • evidence_items  │   │
│  │             │     │ • tool_results     │   │
│  │             │     │ • chain_of_custody │   │
│  └─────────────┘     └────────────────────┘   │
│         │                                      │
│         ▼                                      │
│  ┌──────────────────┐                         │
│  │ Custom Endpoint  │                         │
│  │  /mcp-proxy/*    │                         │
│  └────────┬─────────┘                         │
└───────────┼─────────────────────────────────────┘
            │
            ▼
┌───────────────────────────────────┐
│      MCP Tool Servers              │
│  • TS Server (port 8081)           │
│  • Python Server (port 8082)       │
│  • JS Server (port 8083)           │
└───────────────────────────────────┘
```

**Claude Desktop → Directus MCP → Native operations OR proxy to tool servers**

---

### Pattern 4: WunderGraph Integration

```
┌────────────────────────────────────────────────┐
│              WunderGraph Cosmo                 │
│  ┌───────────┐  ┌───────────────┐  ┌────────┐ │
│  │ Subgraph 1│  │  Subgraph 2   │  │Subgraph│ │
│  │ (Directus │  │(Other Sources)│  │  N     │ │
│  │  REST)   │  │               │  │        │ │
│  └───────────┘  └───────────────┘  └────────┘ │
│        │                                     │
│        ▼                                     │
│  ┌─────────────────────────────────────┐      │
│  │         Federated Schema            │      │
│  └─────────────────────────────────────┘      │
│                      │                        │
│                      ▼                        │
│            ┌─────────────────┐                │
│            │   Router        │                 │
│            │   :4000         │                 │
│            └─────────────────┘                 │
└────────────────────────────────────────────────┘
                      │
                      ▼
               ┌────────────┐
               │  Clients    │
               │  (AI DIAL)  │
               └────────────┘
```

**Approach**: WunderGraph introspects Directus REST API (not GraphQL) for federation simplicity.

---

## Implementation Roadmap

### Phase 1: Core Migration (Week 1-2)

**Deliverables**:
1. ✅ Deploy Directus instance
2. ✅ Connect to existing PostgreSQL (dial-stack database)
3. ✅ Configure RBAC roles (analyst, reviewer, admin)
4. ✅ Create custom field interfaces for evidence types
5. ✅ Build evidence dashboard with Insights panels

**Effort**: Medium (Directus introspects existing DB)

---

### Phase 2: Workflow Automation (Week 3-4)

**Deliverables**:
1. ✅ Create Flows for evidence processing pipeline
2. ✅ Add Webhook operations to call MCP tool servers
3. ✅ Implement Run Script operations for hash validation
4. ✅ Build Trigger Flow chains for multi-step analysis
5. ✅ Add manual triggers for ad-hoc analysis

**Effort**: Medium

---

### Phase 3: MCP Integration (Week 5-6)

**Deliverables**:
1. ✅ Enable Directus MCP server
2. ✅ Create dedicated MCP user role
3. ✅ Test Claude Desktop → Directus MCP workflow
4. ✅ Build custom `/mcp-proxy/*` endpoint for tool servers
5. ✅ Document AI assistant usage patterns

**Effort**: Low (native MCP support)

---

### Phase 4: Advanced Features (Week 7-8)

**Deliverables**:
1. ✅ Realtime WebSocket subscriptions for live updates
2. ✅ Custom panel extensions for evidence visualization
3. ✅ GraphQL federation layer (optional)
4. ✅ Wiki.js integration for documentation
5. ✅ SSO configuration for existing auth system

**Effort**: Medium-High

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Directus performance at scale | Medium | High | Connection pooling, caching, read replicas |
| Custom extension complexity | Low | Medium | Start simple, iterate |
| MCP rate limiting | Medium | Medium | Queue non-urgent operations in Flows |
| Wiki synchronization | Medium | Low | Webhooks for 2-way sync |
| Existing data migration | Low | High | Directus introspects existing DB (no migration needed) |

---

## Open Questions

1. **Port Conflicts**: What port should Directus run on? (3000 default may conflict)
2. **Auth Integration**: Connect to existing Keycloak or use Directus auth?
3. **Wiki Location**: Where should Wiki.js be deployed? (Same server? Separate?)
4. **GraphQL Federation Priority**: Required for phase 1, or can wait?
5. **Custom Panels**: Any specific visualizations needed beyond standard charts?

---

## References

### Directus Documentation
- MCP Server: `/guides/ai/mcp`
- Extensions SDK: `/guides/extensions/overview`
- Flows Operations: `/guides/automate/operations`
- Realtime: `/guides/realtime/subscriptions`
- Custom Endpoints: `/tutorials/extensions/proxy-an-external-api`
- Custom Operations: `/tutorials/extensions/use-npm-packages-in-custom-operations`

### Background Research Completed
- IBM ContextForge wiki created at `docs/wiki/IBM_CONTEXTFORGE.md`
- Directus feature inventory complete (see above)
- Integration patterns documented (see above)

---

# Plan Feedback

I've reviewed this plan and have 2 pieces of feedback:

## 1. General feedback about the plan
> Would it be able to interact with Lance DB and Duckdb natively Could we store our data in there when it gets when we imported into the CMS can we drop it into the duckdb Uh layer where it's supposed to be ingested I don't want multiple copies

## 2. General feedback about the plan
> Also check out the IBM context forge documentation because that's gonna play a big part in the architecture going forward See how that affects things It's mostly a back end feature Dial is going to be kind of sitting in the middle as just an orchestrator really

---
