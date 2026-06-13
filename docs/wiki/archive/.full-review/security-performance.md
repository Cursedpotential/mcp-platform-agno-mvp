# Phase 2: Security & Performance Review

## Security Findings

### Critical (4)

**Unrestricted SQL execution via `postgres_raw_query`**
`PostgresWriter.ts:51` — `client.unsafe(sql, params)`. The SQL string is fully caller-controlled. Any caller can execute `DROP TABLE`, `TRUNCATE`, `DELETE`, or `UPDATE` on any table. No allowlist, no read-only enforcement, no query logging. The MCP endpoint must sit behind DIAL Core's Keycloak JWT auth, but `docker-compose.yml` exposes port 8081 directly to the host, creating a bypass path.

**MCP server ports exposed directly to host, bypassing DIAL auth**
`docker-compose.yml:137,146` — Ports 8081 and 8082 are mapped to the host. DIAL Core (port 8080) handles JWT auth via Keycloak — that's the intended gateway. But direct host access to 8081/8082 skips it entirely. Fix: remove direct port exposure (internal Docker network only) or add defense-in-depth auth middleware on the MCP servers.

**Workflow analysis pipeline writable by any caller**
`workflow_tools.py:218-360` — `workflow_update_config`, `workflow_add_module`, `workflow_remove_module` write directly to `config/workflows.json` on disk. No caller identity check. The entire platform needs API-level token auth and GUI-level login auth (Keycloak). These tool endpoints should validate caller identity before allowing config mutations.

**`postgres_write_record` accepts any table name — needs validation**
`index.ts:323-326` + `PostgresWriter.ts:31-33` — `tableName` passed to `client(tableName)` with identifier quoting but no allowlist. Can write to Keycloak tables, inject fake evidence into `write_tracking`, or corrupt the HITL review queue. **Open question: Can Zod handle table allowlisting here, or do we need a different validation layer?** Evidence-handling tables need additional chain-of-custody validation (hash verification, audit logging) as a VIP-level concern.

---

### High (6)

**Hardcoded secrets in `docker-compose.yml`**
Lines 21, 24, 65-67, 175-181:
- `NEXTAUTH_SECRET: "secret"` — predictable JWT signing key
- `DIAL_API_KEY: "dial_api_key"` — master DIAL Core API key
- Default passwords for Keycloak admin, PostgreSQL, InfluxDB

**Open question: Secret storage approach.** Options: `.env` file (minimum), open-source vault solution (preferred), or encrypt at rest in DB for post-bootstrap secrets. Docker Compose secrets should at minimum use `${VAR}` references with no inline defaults.

**PII handling in redaction tool response**
`dpk_tools.py:252-259` — `detected_pii` list includes `"text": text[r.start:r.end]` — raw PII values in every response. **Per user direction: Auto-redaction is NOT the goal.** Redaction is a manual workflow step triggered when preparing evidence for court submission. However, the tool response still contains raw PII, and the audit logger captures tool responses — meaning PII gets written to audit logs during analysis runs. The tool should either omit raw text during analysis mode or require an explicit `include_raw_pii=true` flag (defaulting to false).

**fasttext model downloaded without integrity verification**
`dpk_tools.py:88-95` — `urllib.request.urlretrieve(url, model_path)` fetches 131MB from Meta CDN. No SHA-256 check, no timeout, fails silently in air-gapped environments. MITM or DNS compromise substitutes a malicious classifier.

**DuckDB hash architecture is incomplete — needs multi-level hashing**
`DuckDbService.ts:206` — `const contentToHash = rawContent || binaryPath || ''`. Currently hashes only one thing (raw content OR path string as fallback). **Per user direction: The intended design is multi-level hashing** — file-level hash, message-level hash, and potentially additional levels. Current approach is wrong: (1) path strings hashed instead of file bytes when `rawContent` is null, (2) no per-message hash for individual evidence items. Needs a dedicated spec module (MODULE_2_COORDINATOR) defining the full hash hierarchy.

**Python singletons are not thread-safe — CRITICAL for legal evidence**
All `_get_*` functions in `dpk_tools.py`, `workflow_tools.py`, and `server.py` use `global _var; if _var is None:` without locks. Concurrent first-calls can double-initialize, corrupt singleton state, or cause resource leaks. **Confirmed critical by user.**

**`review_approve`/`reject` accept unverified reviewer identity**
`index.ts:360-369` — `reviewed_by` is a free-text field with no authentication binding. An LLM agent can approve evidence claiming to be any human reviewer. **Should tie into Keycloak JWT claims** — reviewer identity must come from the token, not from tool call parameters.

---

### Medium (6)

**Dragonfly/Redis exposed on port 6379 with no password**
`docker-compose.yml:98-103` — Bound to `0.0.0.0`, no authentication. Any host process can flush cached sessions or inject data.

**Path traversal on all parser tools**
`index.ts:279-297` — `parse_sms_xml`, `parse_facebook_export`, `parse_imessage_pdf` accept `file_path` with no validation. A caller can specify `/etc/passwd` or any sensitive container file. Should restrict to a configured data directory.

**Keycloak running HTTP-only with strict hostname disabled**
`docker-compose.yml:70-71` — `KC_HTTP_ENABLED: "true"`, `KC_HOSTNAME_STRICT: "false"`. Tokens issued over plain HTTP. Acceptable for local dev, not for network-facing deployment.

**No input size limits on text processing tools**
`dpk_tools.py` — all functions accept unbounded `text`. `dpk_hap_score` with a 50MB string exhausts memory during tokenization. No server-side content-length limit.

**InfluxDB token duplicated across two services**
Lines 181 and 192 — same literal token in two places. Rotation requires changing both, and the token is in version control.

**Error messages expose internal schema details**
`PostgresWriter.ts:38` — PostgreSQL error messages including column names, constraint names, and table structure returned directly to MCP callers.

---

### Low (3)

**No rate limiting on any endpoint** — Express server has no rate limiting middleware.

**`js-mcp-server` is a `depends_on` target for `core` but has no real functionality** — Only `ping_js_server` tool. Unhealthy container blocks core startup.

**Keycloak tokens flow over plaintext within Docker network** — Other compromised containers can intercept via bridge network.

---

### Reclassified: Ollama

**Previously flagged as Rule 3 violation — RECLASSIFIED as intentional architecture.**
`docker-compose.yml:121-127` — Ollama serves as a proxy to Ollama Cloud for services expecting local inference + the 2GB GPU handles basic classification, embedding, entity resolution. Rule 3 applies to heavy inference workloads, not lightweight proxy/classification use.

---

## Performance Findings

### Critical (1)

**Parser output dumps unbounded JSON into a single MCP message**
`index.ts:282` — `JSON.stringify(messages, null, 2)` for a 10,000-message file produces >10MB. MCP has no chunking. The LLM context window can't process it. No pagination, no streaming, no count-first option. This is the single biggest blocker to end-to-end message processing.

---

### High (3)

**HAP model batches all sentences in one forward pass**
`dpk_tools.py:160-165` — `tokenizer(sentences, ...)` batches ALL sentences together. A 500-message conversation = ~10,000 tokens in one batch. On CPU this OOMs. The `batch_size: 128` config in HAPTransform is ignored because `transform()` is bypassed in favor of direct model access.

**Duplicate PostgreSQL connection pools to same database**
`PostgresWriter` (max 10) and `ReviewQueue` (max 5) create separate pools to the same instance. Under load the database sees 15 connections from what should be one client.

**Facebook parser reads entire file into memory**
`FacebookExportParser.ts:105` — `readFile(filePath, 'utf-8')` + `cheerio.load(html)`. Peak memory = file_size x 3. SMS parser uses streaming SAX — Facebook parser does not.

---

### Medium (3)

**Language ID blocks on 131MB download during first call**
`dpk_tools.py:92-95` — No async download, no timeout, no progress indicator. First caller gets a timeout.

**New MCP Server instance created per HTTP request**
`index.ts:399-400` — `createMcpServer()` inside the request handler. The server is stateless and could be a singleton.

**`workflow_run` uses O(n^2) string concatenation**
`workflow_tools.py:195` — `context +=` in a loop. Should use list + `join()`.

---

## Summary

| Severity | Security | Performance | Total |
|----------|----------|-------------|-------|
| Critical | 4 | 1 | 5 |
| High | 6 | 3 | 9 |
| Medium | 6 | 3 | 9 |
| Low | 3 | 0 | 3 |
| **Total** | **19** | **7** | **26** |

---

## Open Design Questions

These need answers before remediation specs can be written:

1. **Table validation approach** — Zod enum for table allowlist, or separate validation layer? Evidence tables need chain-of-custody validation beyond allowlisting.
2. **Secret storage** — `.env` (minimum), open-source vault solution (preferred), or DB encryption for post-bootstrap secrets?
3. **Multi-level hash spec** — File hash + message hash + what else? Needs MODULE_2_COORDINATOR spec.
4. **PII tool behavior** — Default to NOT returning raw PII text. Add `include_raw_pii` flag for court-prep workflows only.
5. **Reviewer identity** — Bind `reviewed_by` to Keycloak JWT claims.

---

## Top 5 Remediation Priorities

1. **Remove direct port exposure on MCP servers** — Internal Docker network only. DIAL Core is the auth gateway. One-line fix per service, closes biggest attack surface.
2. **Add Zod table allowlist to `postgres_write_record`** — Restrict to known tables. Add chain-of-custody validation for evidence tables.
3. **Fix DuckDB hash to multi-level** — Read file bytes for file-level hash, compute per-message hashes. Requires MODULE_2_COORDINATOR spec first.
4. **Add threading locks to Python singletons** — `threading.Lock()` around all `_get_*` functions. Small change, high impact for determinism.
5. **Add pagination to parser output** — Return count + page mechanism instead of full JSON dump. Prerequisite for end-to-end message processing.
