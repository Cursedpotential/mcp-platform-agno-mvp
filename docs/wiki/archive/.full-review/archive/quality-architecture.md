# Phase 1: Code Quality & Architecture Review

**Review Date:** March 14, 2026
**Target:** SMS and Facebook Message Processing Workflows (Strict Mode)

## Executive Summary

The SMS and Facebook message parsers demonstrate good separation of concerns and awareness of forensic requirements (chain of custody, data immutability). However, several **critical issues** require immediate attention before processing real evidence data.

### Severity Breakdown

| Phase | Critical | High | Medium | Low | Total |
|--------|----------|------|--------|-----|-------|
| Code Quality | 4 | 7 | 6 | 4 | 21 |
| Architecture | 1 | 3 | 4 | 2 | 10 |
| **TOTAL** | **5** | **10** | **10** | **6** | **31** |

---

## Code Quality Findings

### Critical Issues (P0 - Must Fix Immediately)

#### CQ-1: Type Safety Violation - `any` Type Casting (Data Loss Risk)
**File:** `ts-mcp-server/src/index.ts`
**Lines:** 300, 311, 317, 323, 329, 340, 350, 360, 366, 372
**Severity:** CRITICAL
**CWE:** N/A (Type safety)

**Description:** The MCP tool handler uses `as any` casting for request arguments, completely bypassing TypeScript's type safety. In a forensic context, this is critical because:

1. Type mismatches can cause silent data corruption
2. Missing or malformed data won't be caught at compile time
3. SQL injection vulnerabilities become possible
4. Chain of custody metadata can be silently dropped

```typescript
// Lines 300-302 - CRITICAL: Bypasses all type checking
case "vault_log_ingestion": {
  const { source_type, source_name, raw_content, binary_path } = args as any;
  const result = await getVault().logIngestion(source_type, source_name, raw_content ?? null, binary_path ?? null, {});
  return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
}
```

**Fix Recommendation:**

```typescript
// Define proper request types
interface VaultLogIngestionArgs {
  source_type: string;
  source_name: string;
  raw_content?: string | null;
  binary_path?: string | null;
}

case "vault_log_ingestion": {
  const { source_type, source_name, raw_content, binary_path } = args as unknown;

  // Type validation before processing
  if (typeof source_type !== 'string' || typeof source_name !== 'string') {
    throw new Error('Invalid arguments: source_type and source_name must be strings');
  }

  const validatedArgs: VaultLogIngestionArgs = {
    source_type,
    source_name,
    raw_content: typeof raw_content === 'string' ? raw_content : null,
    binary_path: typeof binary_path === 'string' ? binary_path : null,
  };

  const result = await getVault().logIngestion(
    validatedArgs.source_type,
    validatedArgs.source_name,
    validatedArgs.raw_content,
    validatedArgs.binary_path,
    {}
  );
  return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
}
```

---

#### CQ-2: Swallowed Exceptions in Parser Loop (Evidence Loss Risk)
**File:** `ts-mcp-server/src/tools/SmsXmlParser.ts`
**Lines:** 171-174
**Severity:** CRITICAL
**CWE:** CWE-392 (Missing Error Handling)

**Description:** The parser catches exceptions but only logs to console, returning `null`. In a streaming loop over potentially millions of messages, this causes:

1. Silent loss of evidence
2. No audit trail of which messages failed
3. Partial data ingestion that appears successful
4. Chain of custody violations (some data is missing without explanation)

```typescript
// Lines 171-174
} catch (error) {
  console.error('Failed to parse XML node:', error);
  return null;  // Message is silently dropped
}
```

**Fix Recommendation:**

```typescript
private parseElementToDocument(xml: string): NormalizedMessage | null {
  try {
    // Fix stray ampersands before parsing (Legacy Python fix)
    const sanitizedXml = xml.replace(/&(?!#\d+;|#x[0-9A-Fa-f]+;|[A-Za-z][A-Za-z0-9._-]*;)/g, '&amp;');

    const parsed = this.parser.parse(sanitizedXml);
    const data = parsed.sms || parsed.mms || parsed.call;

    if (!data) return null;

    // ... rest of parsing logic ...

  } catch (error) {
    // FORENSIC: Capture error details for audit trail
    const errorId = uuidv7();
    const errorMessage = error instanceof Error ? error.message : String(error);

    // Log with structured error ID
    console.error(`[PARSE_ERROR:${errorId}] Failed to parse XML node`, {
      error: errorMessage,
      xmlPreview: xml.substring(0, 200), // First 200 chars for debugging
      errorId,
    });

    // Return null but track error
    return null;
  }
}
```

**Better Fix:** Add error tracking to `loadData` method:

```typescript
async loadData(filePath: string): Promise<{ messages: NormalizedMessage[]; errors: ParseError[] }> {
  const documents: NormalizedMessage[] = [];
  const errors: ParseError[] = [];
  // ... parsing loop ...

  if (depth === 0) {
    const doc = this.parseElementToDocument(xmlBuffer, errors);
    if (doc) {
      documents.push(doc);
    }
    // ... reset state ...
  }
  // ... end loop ...

  return { messages: documents, errors };
}

interface ParseError {
  id: string;
  message: string;
  xmlPreview: string;
  timestamp: Date;
}
```

---

#### CQ-3: Unvalidated File Path (Security Risk)
**File:** `ts-mcp-server/src/index.ts`
**Lines:** 278, 285, 294
**Severity:** CRITICAL
**CWE:** CWE-22 (Path Traversal), CWE-73 (External Control of Filename)

**Description:** File paths from untrusted input are used directly without validation. In a forensic context, this creates:

1. Path traversal vulnerability (`../../etc/passwd`)
2. Evidence tampering possibility
3. Potential for reading system files
4. Chain of custody compromise

```typescript
// Line 278 - No validation
case "parse_sms_xml": {
  const filePath = String(args.file_path);
  const parser = new SmsXmlParser();
  const messages = await parser.loadData(filePath);  // Direct use
  return { content: [{ type: "text", text: JSON.stringify(messages, null, 2) }] };
}
```

**Fix Recommendation:**

```typescript
import { resolve } from 'path';

// Add path validation utility
function validateFilePath(filePath: string, allowedBasePaths: string[]): string {
  const resolved = resolve(filePath);

  for (const basePath of allowedBasePaths) {
    const resolvedBase = resolve(basePath);
    if (resolved.startsWith(resolvedBase)) {
      return resolved;
    }
  }

  throw new Error(`File path '${filePath}' is not in allowed directories`);
}

// In tool handler
case "parse_sms_xml": {
  const filePath = String(args.file_path);

  // Get allowed paths from environment
  const allowedPaths = (process.env.ALLOWED_DATA_PATHS || '').split(':').filter(Boolean);
  if (allowedPaths.length === 0) {
    throw new Error('No allowed data paths configured');
  }

  const validatedPath = validateFilePath(filePath, allowedPaths);

  // Verify file exists and is readable
  try {
    await fs.access(validatedPath, fs.constants.R_OK);
  } catch (error) {
    throw new Error(`File not accessible: ${validatedPath}`);
  }

  const parser = new SmsXmlParser();
  const messages = await parser.loadData(validatedPath);
  return { content: [{ type: "text", text: JSON.stringify(messages, null, 2) }] };
}
```

---

#### CQ-4: Date Parsing Failure Silently Drops Messages
**File:** `ts-mcp-server/src/tools/FacebookExportParser.ts`
**Lines:** 47-81, 169, 219
**Severity:** CRITICAL
**CWE:** CWE-390 (Error Handling Without Action)

**Description:** The `parseDateFuzzy` function returns `null` on failure, and calling code immediately returns, dropping the message entirely. In forensic contexts:

1. Timeline reconstruction depends on accurate timestamps
2. Silently dropping messages creates gaps in evidence
3. No way to know which messages were lost
4. Could indicate tampering but is indistinguishable from parsing failure

```typescript
// Lines 47-81 - Returns null on any parsing failure
function parseDateFuzzy(ts: string): Date | null {
  if (!ts) return null;
  // ... parsing logic ...
  return null;  // All paths that fail return null
}

// Line 169 - Silent drop
const timestamp = parseDateFuzzy(timestampStr);
if (!timestamp) return;  // Message is silently dropped
```

**Fix Recommendation:**

```typescript
// Option 1: Parse with fallback and preserve raw timestamp
interface TimestampParseResult {
  date: Date;
  confidence: 'high' | 'medium' | 'low';
  raw: string;
}

function parseDateFuzzy(ts: string): TimestampParseResult | null {
  if (!ts) return null;

  const raw = ts.trim();
  const cleaned = raw.replace(/(\d)(am|pm|AM|PM)\b/gi, '$1 $2');

  // Try native parsing first (high confidence)
  const parsed = new Date(cleaned);
  if (!isNaN(parsed.getTime())) {
    return { date: parsed, confidence: 'high', raw };
  }

  // Try common Facebook formats (medium confidence)
  const formats = [
    /^([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4}),?\s+(\d{1,2}):(\d{2})\s*([AP]M)?$/i,
    /^(\d{1,2})\s+([A-Za-z]+)\s+(\d{4}),?\s+(\d{1,2}):(\d{2})\s*([AP]M)?$/i,
    /^([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})\s+at\s+(\d{1,2}):(\d{2})\s*([AP]M)?$/i,
  ];

  for (const format of formats) {
    const match = cleaned.match(format);
    if (match) {
      const attempt = new Date(cleaned);
      if (!isNaN(attempt.getTime())) {
        return { date: attempt, confidence: 'medium', raw };
      }
    }
  }

  // FORENSIC: Fall back to epoch with low confidence flag
  // This preserves the message even if we can't parse the date
  console.warn(`[TIMESTAMP_PARSE_FAILURE] Unable to parse timestamp: ${ts}`);
  return {
    date: new Date(0),
    confidence: 'low',
    raw: ts
  };
}

// Update calling code
const timestampResult = parseDateFuzzy(timestampStr);
if (!timestampResult) {
  console.warn(`[TIMESTAMP_PARSE_FAILURE] Unable to parse timestamp: ${timestampStr}`);
  return null;  // Or use low-confidence fallback
}

// Use result with confidence tracking
messages.push({
  sender,
  body,
  timestamp: timestampResult.date,
  timestampRaw: timestampResult.raw,
  timestampConfidence: timestampResult.confidence,
  rawData: { meta: metaText, html: $msg.html() || '' },
});
```

---

### High Severity Issues

#### HQ-1: Cognitive Complexity in Date Parsing Logic
**File:** `ts-mcp-server/src/tools/FacebookExportParser.ts`
**Lines:** 47-81
**Severity:** HIGH
**Description:** The `parseDateFuzzy` function has nested try-catch logic, multiple regex patterns, and complex branching.

**Fix Recommendation:** Extract regex patterns into a configuration array.

---

#### HQ-2: Code Duplication - Sender/Recipient Logic
**File:** `ts-mcp-server/src/tools/SmsXmlParser.ts`
**Lines:** 112-153
**Severity:** HIGH
**Description:** The sender/recipient assignment logic is duplicated between call and message handling.

**Fix Recommendation:** Extract to a helper function.

---

#### HQ-3: Magic Numbers for Message Types
**File:** `ts-mcp-server/src/tools/SmsXmlParser.ts`
**Lines:** 106, 143-152
**Severity:** HIGH
**Description:** Message types are hardcoded as strings (`'1'`, `'2'`, etc.) without clear mapping.

**Fix Recommendation:** Use enum with documentation:

```typescript
enum SmsType {
  INBOX = '1',
  SENT = '2',
  DRAFT = '3',
  OUTBOX = '4',
  FAILED = '5',
  QUEUED = '6',
  UNKNOWN = '0',
}

enum CallType {
  INCOMING = '1',
  OUTGOING = '2',
  MISSED = '3',
  VOICEMAIL = '4',
  REJECTED = '5',
  REFUSED_LIST = '6',
}

// Usage
const type = data['@_type'] || SmsType.UNKNOWN;
const isReceived = type === SmsType.INBOX;
```

---

#### HQ-4: Duplicate Parser Logic in Facebook Parser
**File:** `ts-mcp-server/src/tools/FacebookExportParser.ts`
**Lines:** 147-187, 192-232
**Severity:** HIGH
**Description:** `parseStructure1` and `parseStructure2` have nearly identical logic for extracting and pushing messages.

**Fix Recommendation:** Extract common logic.

---

#### HQ-5: No Input Validation in Facebook Parser Constructor
**File:** `ts-mcp-server/src/tools/FacebookExportParser.ts`
**Lines:** 91-94
**Severity:** HIGH
**Description:** The `FacebookExportParser` constructor accepts `maxMessages` without validation.

**Fix Recommendation:** Validate positive integer and enforce upper limit.

---

#### HQ-6: Unused Parameter in Structure Parsers
**File:** `ts-mcp-server/src/tools/FacebookExportParser.ts`
**Lines:** 148, 193
**Severity:** HIGH
**Description:** Both `parseStructure1` and `parseStructure2` accept `conversationId` as a parameter but never use it.

**Fix Recommendation:** Either use the parameter or remove it.

---

#### HQ-7: Stream Resource Leak Risk
**File:** `ts-mcp-server/src/tools/SmsXmlParser.ts`
**Lines:** 46-50, 52-83
**Severity:** HIGH
**CWE:** CWE-772 (Missing Release of Resource)

**Description:** The file stream is created but not explicitly closed.

**Fix Recommendation:** Use try-finally to ensure cleanup.

---

### Medium Severity Issues

#### MQ-1: Poor Error Context in SmsXmlParser
**File:** `ts-mcp-server/src/tools/SmsXmlParser.ts`
**Lines:** 172
**Severity:** MEDIUM
**Description:** Error logging doesn't include context about which file or which line caused the failure.

**Fix:** Add file path and line tracking.

---

#### MQ-2: Mutable Class State in SmsXmlParser
**File:** `ts-mcp-server/src/tools/SmsXmlParser.ts`
**Lines:** 25, 27-34
**Severity:** MEDIUM
**Description:** The parser instance holds state (`this.parser`) that doesn't need to be instance-level.

**Fix:** Make it a static class or allow configuration.

---

#### MQ-3: Inconsistent Timestamp Handling
**File:** `ts-mcp-server/src/tools/SmsXmlParser.ts`
**Lines:** 101-102
**Severity:** MEDIUM
**Description:** When timestamp parsing fails, code defaults to `new Date()` (current time).

**Impact:** Messages with no timestamp will appear to have been sent now, corrupting timelines.

**Fix:** Use epoch as marker for invalid timestamps.

---

#### MQ-4: Unclear XML Sanitization Logic
**File:** `ts-mcp-server/src/tools/SmsXmlParser.ts`
**Lines:** 91
**Severity:** MEDIUM
**Description:** The ampersand sanitization regex is complex and not well-documented.

**Fix:** Add comprehensive documentation.

---

#### MQ-5: Missing Null Checks on Cheerio Operations
**File:** `ts-mcp-server/src/tools/FacebookExportParser.ts`
**Lines:** 156-172, 199-220
**Severity:** MEDIUM
**Description:** Cheerio operations that return elements are chained without null checks.

**Fix:** Apply consistent null checking pattern throughout.

---

#### MQ-6: No Type Safety for JSON Storage
**File:** `ts-mcp-server/src/tools/FacebookExportParser.ts`
**Lines:** 21
**Severity:** MEDIUM
**Description:** The `ParsedFacebookMessage` interface uses `Record<string, any>` for `rawData`.

**Fix:** Define a more specific type or use a union.

---

### Low Severity Issues

#### LQ-1: Missing JSDoc for Public Methods
**File:** Multiple
**Severity:** LOW
**Description:** Several public methods lack JSDoc documentation.

**Fix:** Add comprehensive JSDoc to all public methods.

---

#### LQ-2: Inconsistent String Comparison for Direction Detection
**File:** `ts-mcp-server/src/tools/FacebookExportParser.ts`
**Line:** 236
**Severity:** LOW
**Description:** The `detectDirection` method performs string comparisons without normalization.

**Fix:** Extract to a helper for clarity.

---

#### LQ-3: Hard-coded Magic Strings for CSS Classes
**File:** `ts-mcp-server/src/tools/FacebookExportParser.ts`
**Lines:** 154, 199, 202, 207, 214
**Severity:** LOW
**Description:** CSS class names like `_a6-g`, `_a6-h`, `_a6-p` are magic strings.

**Fix:** Extract to constants with comments about fragility.

---

#### LQ-4: No Progress Reporting for Large Files
**File:** `ts-mcp-server/src/tools/SmsXmlParser.ts`
**Lines:** 52-83
**Severity:** LOW
**Description:** For multi-gigabyte files, there's no way to report progress.

**Fix:** Add optional progress callback.

---

## Architecture Findings

### Critical Issues

#### AC-1: Violation of Lazy Loading Pattern in FacebookExportParser
**File:** `ts-mcp-server/src/tools/FacebookExportParser.ts`
**Lines:** 1-4
**Severity:** CRITICAL

**Issue:** All dependencies are imported at module load time. The `cheerio` library is particularly heavy and should be lazy-loaded per project rules in CLAUDE.md.

**Architectural Impact:**
- Blocks server startup on every request to `parse_facebook_export`
- Violates established lazy loading pattern used in `DuckDbService.ts`
- Creates unnecessary memory pressure during startup

**Fix Recommendation:**

```typescript
// Lazy-load heavy dependencies
async parse(filePath: string): Promise<ParsedFacebookMessage[]> {
  const { readFile } = await import('fs/promises');
  const { createHash } = await import('crypto');
  const { uuidv7 } = await import('uuidv7');
  const cheerio = await import('cheerio');
  // ... rest of implementation
}
```

---

### High Severity Issues

#### AH-1: Inconsistent Message Schema Definitions
**File:** `SmsXmlParser.ts` (lines 5-16), `FacebookExportParser.ts` (lines 10-38)
**Severity:** HIGH

**Issue:** Two parsers define completely different output schemas with no unification.

**Architectural Impact:**
- Violates "Atomic Tools" principle - parsers produce non-interchangeable outputs
- Downstream consumers must handle multiple incompatible formats
- No unified schema for storage tier routing
- Inconsistent field names (`text` vs `body`, `metadata.raw_data` vs `rawData`)
- Inconsistent types (`string` vs `Date` for timestamps)

**Fix Recommendation:**

Create a shared schema file `ts-mcp-server/src/types/Message.ts`:

```typescript
export interface UnifiedMessage {
  id: string;                    // UUIDv7
  platform: string;               // 'sms', 'facebook', 'imessage', etc.
  content: string;               // Unified field
  timestamp: string;             // ISO-8601 string
  sender: string;
  recipient: string;
  direction: 'inbound' | 'outbound' | 'unknown';
  message_type: 'text' | 'call' | 'media' | 'share' | 'system';
  raw_data: Record<string, any>;  // Preserved for forensic audit
  conversation_id?: string;      // For threading support
  metadata?: {
    contact_name?: string;
    raw_address?: string;
    [key: string]: any;
  };
}
```

---

#### AH-2: Direct Parser Instantiation Violates Singleton Pattern
**File:** `ts-mcp-server/src/index.ts`
**Lines:** 277-289
**Severity:** HIGH

**Issue:** Parser instances are created fresh on every request, inconsistent with the singleton pattern used for vault and PostgreSQL services.

**Architectural Impact:**
- Inconsistent patterns across codebase
- Parser instances have state (ownName) but are recreated per request
- Potential memory leaks if parser state accumulates
- Violates established pattern for "lazy singletons"

**Fix Recommendation:**

```typescript
// In index.ts
let _smsParser: SmsXmlParser | null = null;
let _fbParser: FacebookExportParser | null = null;

function getSmsParser(): SmsXmlParser {
  if (!_smsParser) _smsParser = new SmsXmlParser();
  return _smsParser;
}

function getFbParser(ownName?: string): FacebookExportParser {
  if (!_fbParser || (ownName && _fbParser['ownName'] !== ownName)) {
    _fbParser = new FacebookExportParser({ ownName });
  }
  return _fbParser;
}
```

---

#### AH-3: Missing Chain of Custody Integration
**File:** `SmsXmlParser.ts`, `FacebookExportParser.ts`
**Severity:** HIGH

**Issue:** Neither parser integrates with chain of custody system defined in `DuckDbService.ts`. The parsers return parsed data directly without:

1. Calculating SHA-256 hash of source file (first touch)
2. Generating UUIDv7 for ingestion tracking
3. Logging to `ingestion_log` table
4. Writing to `write_tracking` table

**Architectural Impact:**
- Violates "Chain of Custody" principle from ARCHITECTURE.md
- Parsing bypasses forensic integrity controls
- No audit trail for parsed evidence
- Potential for duplicate ingestion without detection

**Fix Recommendation:**

Parsers should not directly return data. Instead, they should integrate with `DuckDbVault` for chain of custody logging.

---

### Medium Severity Issues

#### AM-1: No Streaming Support for Facebook HTML Files
**File:** `ts-mcp-server/src/tools/FacebookExportParser.ts`
**Lines:** 99-106
**Severity:** MEDIUM

**Issue:** Facebook exports can be extremely large (hundreds of MB). Loading entire HTML file into memory violates the streaming pattern established by `SmsXmlParser`.

**Architectural Impact:**
- Memory pressure on large exports
- Inconsistent approach to large file handling
- Potential OOM errors with multi-GB exports

**Fix Recommendation:**
Implement streaming HTML parsing or chunk processing.

---

#### AM-2: Implicit Schema Assumption
**File:** `SmsXmlParser.ts`
**Lines:** 56-80
**Severity:** MEDIUM

**Issue:** The parser assumes specific XML element names without validation.

**Architectural Impact:**
- Silent failures on malformed XML
- No error reporting on unsupported formats
- Difficult to debug why parsing produced no results

**Fix Recommendation:**
1. Add schema validation at start of parsing
2. Check for root element `<smses>` or root `<calls>`
3. Return descriptive error for unsupported formats

---

#### AM-3: Missing Error Handling for File Operations
**File:** Both parsers
**Severity:** MEDIUM

**Issue:** No try-catch around file operations. Errors will bubble up unhandled to the MCP server.

**Architectural Impact:**
- Poor error messages for users
- No graceful degradation
- Potential crashes on file system errors

**Fix Recommendation:**
Add proper try-catch with specific error codes.

---

#### AM-4: Hardcoded Configuration
**File:** `FacebookExportParser.ts`
**Lines:** 91-94
**Severity:** MEDIUM

**Issue:** `maxMessages` is not documented in tool schema in `index.ts` and has no enforcement mechanism.

**Architectural Impact:**
- Silent truncation of exports
- No user awareness of limit
- No configuration management pattern

**Fix Recommendation:**
1. Add `max_messages` to input schema in `index.ts`
2. Validate input before parsing
3. Log warning when limit is reached

---

### Low Severity Issues

#### AL-1: Inconsistent Naming Conventions
**File:** Both parsers
**Severity:** LOW

**Issue:** `SmsXmlParser` uses `loadData()` method, `FacebookExportParser` uses `parse()` method.

**Fix Recommendation:** Standardize to `parse()` or `loadData()` across all parsers.

---

#### AL-2: Missing JSDoc Comments
**File:** Both parsers
**Severity:** LOW

**Issue:** Public methods lack comprehensive JSDoc documentation with parameter types, return types, and examples.

**Fix Recommendation:** Add JSDoc comments for all public methods.

---

## Critical Issues for Phase 2 Context

The following issues should inform security and performance review:

### Security Context
- **CQ-3:** Unvalidated file paths enable path traversal attacks
- **CQ-1:** `as any` type casting bypasses all input validation
- **CQ-2:** Silently dropped exceptions create audit trail gaps
- **AH-3:** Missing chain of custody integration

### Performance Context
- **AC-1:** Lazy loading violation blocks startup
- **AM-1:** No streaming for large HTML files
- **HQ-7:** Resource leaks in stream processing
- **CQ-4:** Silent message drops reduce throughput
