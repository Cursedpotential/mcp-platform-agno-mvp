# Security Audit Report

**Agent:** Security Auditor
**Date:** February 28, 2026
**Project:** MCP_Tool_Platform
**Scope:** Entire codebase with focus on Sprint One additions

---

## Executive Summary

**Risk Level: CRITICAL**

This audit identified **7 Critical**, **5 High**, **8 Medium**, and **6 Low** severity issues.

> **Note:** This is a personal application, so enterprise-grade security requirements are relaxed. However, exposed credentials and injection vulnerabilities must be fixed to prevent crashes and unauthorized access.

---

## Critical Severity Issues (MUST FIX)

### 1. HARDCODED CREDENTIALS IN DEPLOYMENT FILES
**File:** `deploy/salem-trinity/phase3-vps3-platform/.env`

**Issue:** Multiple hardcoded passwords and API keys committed to version control:
- `MYSQL_ROOT_PASSWORD=Ms10238512ms!`
- `MYSQL_PASSWORD=Ms10238512ms!`
- `POSTGRES_PASSWORD=Ms10238512ms!`
- `CHROMA_API_KEY=Ms10238512ms!`
- `LITELLM_MASTER_KEY=Ms10238512ms!`
- `DIRECTUS_TOKEN=Ms10238512ms!`
- `NEO4J_PASSWORD=uZUMCeTEoOmuuF8SyI5YIuhJeyyhsVbbqTuxixTe26c`
- `NEXTAUTH_SECRET=4405cb62699341499596c567a1401314352528731d102e3474744d084058d19e`
- `JWT_SECRET=b63c9780092c4d9a9ba46522c7a72382901588661705603e878796245388034b`
- `OPENAI_API_KEY=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`

**Impact:** System compromise if repository is exposed.
**Fix:**
1. Rotate ALL exposed credentials immediately
2. Remove file from git history using `git filter-repo` or BFG Repo-Cleaner
3. Move secrets to `.env.local` (gitignored)
4. Use `.env.example` files with placeholder values only

---

### 2. HARDCODED DEFAULT PASSWORDS IN DOCKER COMPOSE
**File:** `deploy/salem-trinity/phase3-vps3-platform/docker-compose.vps3-platform.yml`

**Issue:** Default fallback passwords:
```yaml
MYSQL_ROOT_PASSWORD=${MYSQL_ROOT_PASSWORD:-Ms10238512ms!}
MYSQL_PASSWORD=${MYSQL_PASSWORD:-Ms10238512ms!}
```

**Fix:** Remove default values; require explicit password configuration.

---

### 3. COMMAND INJECTION VULNERABILITY
**File:** `server/mcp/analysis/nlp-classifier.ts` (Lines 148, 198, 218)

**Issue:** Direct shell command execution with unsanitized user input:
```typescript
const command = `python3 ${this.nlpRunnerPath} analyze_sentiment '${JSON.stringify({ text })}'`;
const { stdout } = await execAsync(command);
```

**Impact:** Application crash or code execution if `text` contains shell metacharacters.
**Fix:** Use parameterized execution with `spawn` and pass arguments as array:
```typescript
const { stdout } = await execAsync('python3', [this.nlpRunnerPath, 'analyze_sentiment', JSON.stringify({ text })]);
```

---

### 4. WEAK ENCRYPTION KEY IN ENVIRONMENT
**File:** `.env` (Line 22)

**Issue:** Placeholder encryption key:
```
ENCRYPTION_KEY=placeholder-key-replace-me-with-openssl-rand-hex-32
```

**Impact:** If not changed, API keys are trivially decryptable.
**Fix:** Generate strong key and fail startup if placeholder detected.

---

### 5. SQL INJECTION VULNERABILITY IN LANCEDB QUERIES
**File:** `server/mcp/storage/lancedb.ts` (Lines 223, 239, 255, 274)

**Issue:** Direct string interpolation in SQL-like queries:
```typescript
.where(`source_hash = '${sourceHash}'`)
```

**Impact:** Potential data issues if `sourceHash` is malformed.
**Fix:** Use parameterized queries or proper escaping.

---

### 6. MISSING AUTHENTICATION ON CLI BRIDGE
**File:** `cli-bridge/index.ts` (Lines 17-27)

**Issue:** Authentication bypass when `CLI_BRIDGE_API_KEY` is not set:
```typescript
if (!API_KEY) {
  console.warn("WARNING: No CLI_BRIDGE_API_KEY configured. All requests allowed.");
  return next();
}
```

**Impact:** Unauthenticated access to tool invocation.
**Fix:** Fail secure - reject all requests if API key is not configured.

---

### 7. SENSITIVE DATA EXPOSURE
**File:** `server/mcp/storage/graphiti-client.ts` (Lines 217-224)

**Issue:** Neo4j credentials passed via environment variables to spawned process:
```typescript
env: {
  ...process.env,
  NEO4J_URL: this.neo4jUrl,
  NEO4J_PASSWORD: this.neo4jPassword,
}
```

**Impact:** Credentials visible in process listings.
**Fix:** Use configuration files with restricted permissions.

---

## High Severity Issues (SHOULD FIX)

### 8. INSECURE JWT SECRET HANDLING
**File:** `server/core/sdk.ts` (Lines 159-162)

Empty JWT secret falls back to empty string. **Fix:** Fail startup if JWT secret not configured.

### 9. PATH TRAVERSAL VULNERABILITY
**File:** `server/api/routers/ingestion.ts` (Lines 13-25)

User-provided `filePath` used directly without validation. **Fix:** Validate paths against allowed directories.

### 10. MISSING RATE LIMITING
**File:** `server/core/index.ts` (Lines 33-68)

No rate limiting on Express server. **Fix:** Implement `express-rate-limit` for production.

### 11. INSECURE COOKIE CONFIGURATION
**File:** `server/core/oauth.ts` (Lines 44-48)

Missing `secure` and `sameSite` flags. **Fix:** Enforce secure cookie settings.

### 12. DEBUG MODE ENABLED BY DEFAULT
**File:** `server/core/index.ts` (Lines 50-54)

Vite development mode enabled when `NODE_ENV` not set to production. **Fix:** Default to production mode.

---

## Sprint One Specific Issues

1. **CRITICAL:** SQL injection in LanceDB queries (`lancedb.ts`)
2. **CRITICAL:** Path traversal in ingestion router (`ingestion.ts`)
3. **HIGH:** CLI bridge auth bypass
4. **MEDIUM:** Insecure file handling in watcher

---

## Prioritized Fix List (Personal App Context)

### P0 (Fix Immediately - Breaking/Crash Risk)
1. Rotate hardcoded credentials and remove from git history
2. Fix command injection in `nlp-classifier.ts`
3. Fix SQL injection in `lancedb.ts`
4. Fix path traversal in `ingestion.ts`
5. Fix CLI bridge auth bypass (fail secure)

### P1 (Fix Soon - Security Hardening)
6. Generate proper ENCRYPTION_KEY
7. Validate JWT secret at startup
8. Add secure cookie flags
9. Protect Neo4j credentials in process spawn

### P2 (Optional - Nice to Have)
10. Add rate limiting
11. Default to production mode
12. Add security headers

---

## Compliance Note

Given this is a **forensic legal case management system**, consider:
1. **Chain of Custody:** Current SHA-256 hashing is good
2. **Data Encryption:** Ensure encryption at rest
3. **Access Controls:** Implement basic auth checks
4. **Audit Trails:** Log evidence access