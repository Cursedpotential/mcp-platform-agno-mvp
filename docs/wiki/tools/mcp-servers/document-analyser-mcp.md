# Document Analyser MCP

## Overview
- **What**: FastMCP-based document analysis server with sentiment analysis, keyword extraction, readability scoring, and semantic search
- **Version**: 1.0.0
- **Category**: nlp | document-analysis | mcp-server
- **Framework**: FastMCP 2.3+
- **Language**: Python 3.8+

## Purpose
Provides comprehensive document analysis capabilities through MCP tools:
- Sentiment analysis (VADER + TextBlob dual-engine)
- Keyword extraction (TF-IDF + frequency analysis)
- Readability metrics (Flesch, Flesch-Kincaid, ARI)
- Document management (CRUD operations)
- Semantic search across document collections
- Collection statistics and analytics

## Available Tools
- analyze_document - Complete document analysis
- get_sentiment - Sentiment analysis of text
- extract_keywords - Extract top keywords
- calculate_readability - Readability metrics
- add_document - Add new document
- get_document - Retrieve document
- delete_document - Delete document
- list_documents - List documents by category
- search_documents - Semantic search
- search_by_tags - Tag-based filtering
- get_collection_stats - Collection statistics

## Installation
```bash
cd C:/Users/matts/Projects/TheBigOne/dial-stack/utilities/mcp-servers/Document-Analyser-MCP
pip install -r requirements.txt
python -c "import nltk; nltk.download('punkt'); nltk.download('vader_lexicon'); nltk.download('stopwords')"
python fastmcp_document_analyzer.py
```

## Use Cases
- Document sentiment analysis
- Keyword extraction from text
- Readability assessment
- Document collection management
- Semantic search across documents
- LLM output evaluation

## Dependencies
- fastmcp>=2.3.0
- textblob>=0.17.1
- nltk>=3.8.1
- textstat>=0.7.3
- scikit-learn>=1.3.0
- numpy>=1.24.0
- pandas>=2.0.0

---
**Last Updated**: 2026-03-15
**Status**: Production Ready
