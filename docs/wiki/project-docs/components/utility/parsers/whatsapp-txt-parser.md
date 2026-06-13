# WhatsApp Text Parser — Skill Reference

## Overview
- **What**: Parses WhatsApp text chat exports into structured message data
- **Status**: 🔴 Pending Implementation
- **Target Server**: TS MCP
- **Category**: parser
- **MCP Tool**: Not yet implemented

## Legacy Reference
- **Source**: `MCP_Tool_Platform/utilities/WhatsAppTxtReader.ts` (READ-ONLY)
- **Key patterns**: Text pattern matching, timestamp parsing, message format variations

## Implementation Notes
- WhatsApp exports use a consistent text-based format with timestamps and sender names
- Need to extract: sender, timestamp, message content, media indicators
- Parser should handle different locale-specific timestamp formats
- Must account for system messages (joins, leaves, changed settings)

## Integration Points
- Input: WhatsApp `.txt` export files (from in-app export feature)
- Output: Structured JSON with messages, participants, metadata
- Used by: Evidence Analysis pipeline for messaging evidence
- Related: SMS parser, iMessage parser, Facebook parser

## Implementation Tasks
- [ ] Create TS MCP tool `parse_whatsapp_txt`
- [ ] Handle various timestamp formats (locale variants)
- [ ] Parse sender detection (especially in group chats)
- [ ] Implement media reference extraction
- [ ] Add integration test suite

## Testing Checklist
- [ ] Single and group conversation parsing
- [ ] Multiple timestamp format variants
- [ ] Media file references
- [ ] System messages (participant changes)
