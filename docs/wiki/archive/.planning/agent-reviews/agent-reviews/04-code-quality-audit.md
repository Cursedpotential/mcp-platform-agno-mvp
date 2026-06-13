# Code Quality Audit Report

**Agent:** Code Quality Audit
**Date:** February 28, 2026
**Project:** MCP_Tool_Platform

---

## Executive Summary

Based on comprehensive review of the codebase, **3 Critical + 7 Important issues** identified.

Focus areas: security vulnerabilities, bugs, performance, and code quality.

---

## Critical Issues (Must Fix)

### 1. SQL Injection in Pattern Search
**File:** `server/api/routers/patterns.ts` (Lines 44-50)

**Issue:** User input interpolated into SQL LIKE clauses:
```typescript
if (input.search) {
  conditions.push(
    or(
      like(behavioralPatterns.name, `%${input.search}%`),
      like(behavioralPatterns.description, `%${input.search}%`)
    )
  );
}
```

**Fix:** Escape SQL wildcard characters (`%`, `_`) before constructing LIKE pattern.

---

### 2. Hardcoded Neo4j Credentials
**File:** `server/mcp/plugins/graph-db.ts` (Lines 33-36)

**Issue:** Default credentials as fallbacks:
```typescript
url: process.env.NEO4J_URL || "bolt://localhost:7687",
username: process.env.NEO4J_USERNAME || "neo4j",
password: process.env.NEO4J_PASSWORD || "password",
```

**Fix:** Remove defaults and throw error if env vars missing:
```typescript
const password = process.env.NEO4J_PASSWORD;
if (!password) {
  throw new Error("NEO4J_PASSWORD environment variable is required");
}
```

---

### 3. Path Traversal in Evidence Hasher
**File:** `server/mcp/plugins/evidence-hasher.ts` (Lines 96-103)

**Issue:** User-provided file path read without validation:
```typescript
async function createChainOfCustody(filePath: string, ...): Promise<ChainOfCustody> {
  const stats = await fs.stat(filePath);
  const hash = await hashFile(filePath);
```

**Fix:** Validate paths against allowed directory:
```typescript
const resolvedPath = path.resolve(filePath);
const allowedDir = path.resolve(process.env.EVIDENCE_DIR || './evidence');
if (!resolvedPath.startsWith(allowedDir)) {
  throw new Error("File path outside of allowed directory");
}
```

---

## Important Issues (Should Fix)

### 4. Unvalidated Dynamic Regex (ReDoS Risk)
**File:** `server/api/routers/patterns.ts` (Lines 290-303)

User-provided regex patterns executed without validation. Malicious patterns like `(a+)+$` can cause denial of service.

**Fix:** Implement regex timeout protection.

---

### 5. Insecure Temporary File Storage
**File:** `server/mcp/forensics/chain-custody.ts` (Line 37)

Chain of custody data stored without checking permissions. On multi-user systems, other users could read forensic evidence.

**Fix:** Set restrictive file permissions (0o600).

---

### 6. Python Bridge Race Condition
**File:** `server/mcp/python-bridge.ts` (Lines 24-84)

If process errors before `close` event, promise may never resolve. Promise could resolve twice if both events fire.

**Fix:** Use Promise.race with timeout and ensure single resolution.

---

### 7. Unvalidated JSON Parsing
**File:** `server/mcp/loaders/sms-loader.ts` (Lines 135-148)

JSON parsing not wrapped in try-catch.

**Fix:** Add validation and error handling.

---

### 8. Missing Auth Check in TRPC
**File:** `server/core/trpc.ts` (Lines 13-28)

Middleware checks for `ctx.user` but doesn't verify if user is active/enabled.

**Fix:** Add active status check.

---

### 9. Potential Memory Leak in XML Parser
**File:** `server/mcp/loaders/xml-sms-parser.ts` (Lines 34-73)

Parser accumulates all messages in memory before returning. For multi-gigabyte XML files, this causes memory exhaustion.

**Fix:** Implement generator-based API or callback pattern.

---

### 10. Insecure Environment Defaults
**File:** `server/core/env.ts` (Lines 1-11)

Empty string fallbacks can cause silent failures:
```typescript
cookieSecret: process.env.JWT_SECRET ?? "",
```

**Fix:** Validate required environment variables at startup.

---

## Summary

| Severity | Count | Categories |
|----------|-------|------------|
| Critical | 3 | Security vulnerabilities |
| Important | 7 | Input validation, error handling, performance |

**Recommendations:**
1. Implement centralized input validation using Zod schemas
2. Add security linting (eslint-plugin-security) to CI
3. Review all environment variable fallbacks
4. Add rate limiting to pattern testing endpoints
5. Implement file path sandboxing
6. Add error handling to async operations