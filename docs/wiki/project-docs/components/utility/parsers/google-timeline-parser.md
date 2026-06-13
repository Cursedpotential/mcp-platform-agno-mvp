# Google Timeline Parser — Skill Reference

## Overview
- **What**: Parses Google Takeout Timeline/Location History exports into geographic data
- **Status**: 🔴 Pending Implementation
- **Target Server**: TS MCP (with Python utility)
- **Category**: parser
- **MCP Tool**: Not yet implemented

## Legacy Reference
- **Source**: `MCP_Tool_Platform/Evidence_Analysis/Scripts/parser.py` (READ-ONLY)
- **Source**: `MCP_Tool_Platform/utilities/TakeoutsTimelining` (utility app)
- **Key patterns**: JSON timeline traversal, location clustering, timeline reconstruction

## Implementation Notes
- Google Takeout exports location history as hierarchical JSON with activity records
- Need to extract: coordinates, timestamps, activity types, confidence levels
- Parser should handle semantic locations (places) vs raw coordinates
- Original Python implementation should be ported to TypeScript for TS MCP
- Utility app shows existing location analysis and visualization patterns

## Integration Points
- Input: Google Takeout Timeline JSON exports (from takeout.google.com)
- Output: Structured JSON with locations, activities, timestamps
- Used by: Evidence Analysis pipeline for location/timeline evidence
- Related: Document processors (for spatial data visualization)

## Implementation Tasks
- [ ] Port Python parser logic to TypeScript
- [ ] Create TS MCP tool `parse_google_timeline`
- [ ] Handle both semantic locations and coordinate data
- [ ] Extract activity type and confidence metadata
- [ ] Implement timeline reconstruction/gap filling
- [ ] Study TakeoutsTimelining utility for visualization patterns

## Testing Checklist
- [ ] Coordinate extraction and validation
- [ ] Semantic location parsing
- [ ] Activity type classification
- [ ] Timeline continuity analysis
