# Facebook HTML Parser — Skill Reference

## Overview
- **What**: Parses Facebook data download HTML exports into structured conversation data
- **Status**: 🟢 Implemented
- **Target Server**: TS MCP
- **Category**: parser
- **MCP Tool**: `parse_facebook_export`

## Legacy Reference
- **Source**: `MCP_Tool_Platform/utilities/FacebookHtmlReader.ts` and `facebook-parser.ts` (READ-ONLY)
- **Key patterns**: HTML DOM traversal, Facebook data schema, conversation threading

## Implementation Notes
- Extracts messages, metadata, participants from Facebook HTML exports
- Handles multiple conversation formats (Messenger, Page comments)
- Already integrated as TS MCP tool `parse_facebook_export`

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

## Testing Checklist
- [ ] Verify parsing with multiple Facebook data export formats
- [ ] Test group conversations with varying participant counts
- [ ] Validate media link extraction and preservation
