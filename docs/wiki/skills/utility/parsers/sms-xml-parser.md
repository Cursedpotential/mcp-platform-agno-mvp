# SMS XML Parser — Skill Reference

## Overview
- **What**: Parses Android SMS backup XML files into structured message data
- **Status**: 🟢 Implemented
- **Target Server**: TS MCP
- **Category**: parser
- **MCP Tool**: `parse_sms_xml`

## Legacy Reference
- **Source**: `MCP_Tool_Platform/utilities/SmsXmlReader.ts` (READ-ONLY)
- **Key patterns**: XML schema mapping, SMS metadata extraction, timestamp normalization

## Implementation Notes
- Converts raw Android SMS XML exports to structured JSON format
- Handles multiple message types (SMS, MMS) and metadata fields
- Already integrated as TS MCP tool `parse_sms_xml`

## Integration Points
- Input: Android SMS backup XML files (exported from phone or backup service)
- Output: Structured JSON with conversations, metadata, timestamps
- Used by: Evidence Analysis pipeline for messaging evidence
- Related: WhatsApp parser, iMessage parser (similar document types)

## Usage Example
```
MCP call: parse_sms_xml(filepath: string)
Returns: { conversations: [], metadata: {...} }
```

## Testing Checklist
- [ ] Verify XML schema compatibility with various Android versions
- [ ] Test with mixed SMS/MMS files
- [ ] Validate timestamp parsing across timezones
