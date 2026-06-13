# Google Cloud Natural Language API — Skill Reference

## Overview
- **What**: Google Cloud text analysis service (sentiment, entity extraction, syntax analysis)
- **Status**: 🔴 Pending Evaluation
- **Target Server**: TS MCP
- **Category**: pending
- **MCP Tool**: Not yet implemented

## Legacy Reference
- **Source**: `MCP_Tool_Platform/plugins-pending/gcp-natural-language.ts` (READ-ONLY)
- **Key patterns**: GCP API integration, NLP task routing, response parsing

## Capabilities
- Sentiment analysis (document and sentence level)
- Entity recognition and linking (including mentions)
- Syntax analysis (parts of speech, dependencies)
- Content classification (document categorization)
- Multi-language support

## Integration Points
- Input: Text documents, conversation transcripts, message content
- Output: Sentiment scores, entities, syntax trees, classifications
- Used by: Evidence analysis, conversation analysis, text enrichment
- Related: Claude API (alternative), local NLP tools

## Implementation Considerations
- Requires GCP project setup and authentication
- API quota and rate limiting
- Cost model (per 1K requests)
- Language detection and auto-handling
- Evaluate vs Claude embeddings/analysis for cost/quality

## Implementation Tasks
- [ ] Set up GCP service account and credentials
- [ ] Create TS MCP wrapper for NL API
- [ ] Implement batch processing for efficiency
- [ ] Add language detection/handling
- [ ] Error handling and retry logic
- [ ] Cost tracking and optimization
- [ ] Compare quality vs local alternatives

## Testing Checklist
- [ ] Sentiment accuracy across document types
- [ ] Entity recognition precision/recall
- [ ] Multi-language support
- [ ] Batch processing efficiency
