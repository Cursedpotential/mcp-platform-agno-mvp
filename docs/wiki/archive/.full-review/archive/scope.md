# Review Scope

## Target

**SMS and Facebook Message Processing Workflows** (Strict Mode)

This review focuses on the message ingestion and processing capabilities required for forensic evidence analysis, specifically:
- SMS/Call XML backup parsing (from "SMS Backup & Restore" apps)
- Facebook Messenger HTML/JSON export parsing
- Integration with DIAL MCP architecture

**Strict Mode Enabled**: Any critical findings must be addressed before proceeding to deployment.

## Files

### Core Parser Files (TS MCP Server)
- `ts-mcp-server/src/tools/SmsXmlParser.ts` - SMS XML stream parser for multi-gigabyte files
- `ts-mcp-server/src/tools/FacebookExportParser.ts` - Facebook Messenger HTML parser
- `ts-mcp-server/src/index.ts` - Main MCP server exposing parser tools

### Documentation
- `docs/wiki/skills/utility/parsers/sms-xml-parser.md`
- `docs/wiki/skills/utility/parsers/facebook-html-parser.md`

### Related Schema
- `utilities/apps/utilities/Chunker/schemas/facebook_messages.json`

## Flags

- **Security Focus**: Yes (forensic chain of custody, input validation, path traversal)
- **Performance Critical**: No
- **Strict Mode**: Yes - halt on critical findings
- **Framework**: TypeScript + Node.js + FastMCP

## Review Phases

1. **Code Quality & Architecture** - Maintainability, technical debt, SOLID principles
2. **Security & Performance** - OWASP Top 10, input validation, forensic chain of custody
3. **Testing & Documentation** - Test coverage, inline docs, API documentation
4. **Best Practices & Standards** - TypeScript idioms, framework patterns, CI/CD
5. **Consolidated Report** - Final prioritized findings

## Strict Mode Criteria

In strict mode, the following are considered **CRITICAL** and must halt progress:
- Any OWASP Top 10 vulnerability (CWE)
- Broken chain of custody or evidence tampering risks
- Missing input validation on external file paths
- Unhandled exceptions that could lose evidence data
- Hardcoded credentials or secrets
- Unsafe XML parsing (XXE risks)
- Path traversal vulnerabilities
