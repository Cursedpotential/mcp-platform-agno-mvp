# ChatGPT JSON Parser — Skill Reference

## Overview
- **What**: Parses ChatGPT conversation exports (JSON) into structured conversation data
- **Status**: 🔴 Pending Implementation
- **Target Server**: TS MCP (with Python utility)
- **Category**: parser
- **MCP Tool**: Not yet implemented

## Legacy Reference
- **Source**: `MCP_Tool_Platform/Evidence_Analysis/Scripts/chatgpt_parser.py` (READ-ONLY)
- **Key patterns**: JSON schema traversal, conversation threading, message hierarchy

## Implementation Notes
- ChatGPT exports are hierarchical JSON with conversation trees
- Need to flatten into linear message sequences for analysis
- Must preserve conversation branching (multiple chat paths)
- Requires extraction of: sender (user/assistant), timestamp, content, tokens used
- Original Python implementation should be ported to TypeScript for TS MCP

## Integration Points
- Input: ChatGPT conversation export JSON files (from settings/data export)
- Output: Structured JSON with linearized messages and metadata
- Used by: Evidence Analysis pipeline for AI conversation analysis
- Related: Text-based parsers, document analysis pipeline

## Implementation Tasks
- [ ] Port Python parser logic to TypeScript
- [ ] Create TS MCP tool `parse_chatgpt_json`
- [ ] Handle conversation branching/tree structure
- [ ] Extract token usage metadata
- [ ] Test with various ChatGPT export versions

## Testing Checklist
- [ ] Single and multi-turn conversations
- [ ] Conversation branching preservation
- [ ] Timestamp parsing and validation
- [ ] Token count extraction accuracy
