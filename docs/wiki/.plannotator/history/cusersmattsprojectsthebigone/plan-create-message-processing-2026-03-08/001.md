# Plan: Create Message Processing Blocking Elements Report

## Context
The MCP Tool Platform's message processing coordinator (`server/mcp/ingest/coordinator.ts`) has multiple blocking elements that prevent messages from being processed. This document will analyze and catalog all blocking points with code references, error conditions, and mitigation strategies.

## Files to Create

**New file:** `docs/MCP_MESSAGE_PROCESSING_BLOCKERS.md`

## Report Structure

The report will include the following sections:

### 1. Overview
- High-level description of the message processing pipeline
- Where blocking occurs in the flow
- Impact of each blocking element

### 2. Input Validation Blockers
- Schema definition (`validateInputMetadata`)
- Required fields and constraints
- Error conditions
- Code reference: `coordinator.ts:104-610`
- Mitigation strategies

### 3. Format Detection Blockers
- `detectFormat()` function analysis
- Supported file extensions
- Unknown format handling
- Code reference: `coordinator.ts:209-263, 673-688`
- Mitigation strategies

### 4. Parser Implementation Gaps
- Status of each parser (SmsXmlParser, WhatsAppTxtParser, FacebookHtmlParser, ChatgptJsonParser)
- Stub implementations that throw errors
- Code reference: `coordinator.ts:349-367`
- Mitigation strategies

### 5. Message Validation Blockers
- `validateParsedMessage` schema
- Required fields and constraints
- Invalid message handling (skip vs block)
- Code reference: `coordinator.ts:121-722, 698-722`
- Mitigation strategies

### 6. Deduplication Blockers
- File-level dedup logic
- Cross-device handling
- Exact duplicate skipping
- Code reference: `coordinator.ts:151-177, 634-668`
- Mitigation strategies

### 7. Error Handling
- Try-catch blocks
- Error response format
- Logging behavior
- Code reference: `coordinator.ts:726-738, 878-885`
- Mitigation strategies

### 8. Mitigation Strategies Summary
- Quick reference table of all blockers and their mitigations
- Priority ranking for addressing issues

## Critical Files Referenced

- `server/mcp/ingest/coordinator.ts` - Main coordinator implementation
- `server/mcp/ingest/readers/SmsXmlReader.ts` - SMS XML parser (implemented)
- `server/mcp/ingest/readers/WhatsAppTxtReader.ts` - WhatsApp TXT parser (implemented)
- `server/mcp/ingest/readers/FacebookHtmlReader.ts` - Facebook HTML parser (stub)
- `server/drizzle/message-schemas.ts` - Database schemas

## Verification

After creating the report:
1. Review for completeness - all blocking elements covered
2. Verify all code references are accurate (file:line format)
3. Ensure mitigation strategies are actionable
4. Check markdown formatting renders correctly
