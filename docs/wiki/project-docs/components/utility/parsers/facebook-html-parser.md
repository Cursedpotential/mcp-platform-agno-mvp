# Facebook HTML Parser — Skill Reference

## Overview
- **What**: Parses Facebook data download HTML exports into structured conversation data
- **Status**: 🟢 Implemented
- **Target Server**: TS MCP
- **Category**: parser
- **MCP Tool**: `parse_facebook_export`
- **Priority**: Secondary export path; MVP priority is Facebook JSON through the same parser surface

## Legacy Reference
- **Source**: `MCP_Tool_Platform/utilities/FacebookHtmlReader.ts` and `facebook-parser.ts` (READ-ONLY)
- **Key patterns**: HTML DOM traversal, Facebook data schema, conversation threading

## Implementation Notes
- Extracts messages, metadata, participants from Facebook HTML exports
- Handles multiple conversation formats (Messenger, Page comments)
- Shares the same TS MCP tool surface as Facebook JSON parsing: `parse_facebook_export`
- Keep this page focused on HTML-specific handling. Use `facebook-json-parser.md` for the current MVP path.

## Integration Points
- Input: Facebook data download HTML files (from facebook.com/dyi)
- Output: Structured JSON with messages, participants, timestamps
- Used by: Evidence Analysis pipeline for social media messaging
- Related: WhatsApp parser, SMS parser (messaging evidence types)

## Supported Formats
- Messenger conversations
- Group chats
- Message reactions/edits
- Media references (photos, links)

## Related

- [Facebook JSON Parser](facebook-json-parser.md)
- [SMS XML Parser](sms-xml-parser.md)

## Testing Checklist
- [ ] Verify parsing with multiple Facebook data export formats
- [ ] Test group conversations with varying participant counts
- [ ] Validate media link extraction and preservation
