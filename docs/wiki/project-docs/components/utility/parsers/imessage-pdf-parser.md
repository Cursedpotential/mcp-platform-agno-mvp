# iMessage PDF Parser — Skill Reference

## Overview
- **What**: Extracts iMessage conversations from PDF exports
- **Status**: 🟢 Implemented
- **Target Server**: TS MCP
- **Category**: parser
- **MCP Tool**: `parse_imessage_pdf`

## Legacy Reference
- **Source**: `MCP_Tool_Platform/utilities/pdf-imessage-parser.ts` (READ-ONLY)
- **Key patterns**: PDF text extraction, message pattern matching, participant identification

## Implementation Notes
- Converts PDF-exported iMessage transcripts to structured message format
- Handles both individual and group conversations
- Preserves message timestamps and read receipts where available
- Already integrated as TS MCP tool `parse_imessage_pdf`

## Integration Points
- Input: iMessage PDF exports (from Messages app export or third-party tools)
- Output: Structured JSON with messages, participants, metadata
- Used by: Evidence Analysis pipeline for Apple messaging evidence
- Related: SMS parser, Facebook parser, WhatsApp parser

## Data Preserved
- Sender identification
- Timestamp (when available in export)
- Message content and attachments
- Read receipts/delivery status

## Testing Checklist
- [ ] Test with various PDF export tools (different formatting)
- [ ] Verify group conversation parsing accuracy
- [ ] Validate timestamp consistency across exports
