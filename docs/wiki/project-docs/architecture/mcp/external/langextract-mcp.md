# LangExtract MCP

## Overview
- **What**: FastMCP server for Google's langextract library - extracts structured information from unstructured text using LLMs
- **Version**: Latest
- **Category**: nlp | information-extraction | mcp-server
- **Framework**: FastMCP
- **Language**: Python 3.10+

## Purpose
Extracts structured information from text documents while maintaining precise source grounding using Google Gemini models.

## Available Tools
- extract_from_text - Extract structured information from provided text
- extract_from_url - Extract information from web content
- save_extraction_results - Save results to JSONL format
- generate_visualization - Create interactive HTML visualizations

## Installation
```bash
cd C:/Users/matts/Projects/TheBigOne/dial-stack/utilities/mcp-servers/langextract-mcp
uv sync
export LANGEXTRACT_API_KEY=your-gemini-api-key
uv run src/langextract_mcp/server.py
```

## Use Cases
- Healthcare: Extract medications, dosages, treatment protocols
- Legal: Extract contract terms, parties, obligations
- Research: Extract methodologies, findings, citations
- Business: Extract insights from customer feedback
- Compliance: Analyze regulatory documents

## Dependencies
- fastmcp
- langextract
- google-generativeai

---
**Last Updated**: 2026-03-15
**Status**: Production Ready
