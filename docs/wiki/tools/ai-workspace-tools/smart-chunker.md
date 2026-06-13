# Smart Chunker

## Overview
- **What**: Modular, cross-platform document chunker built with Flet - intelligently splits large documents into AI-friendly chunks
- **Version**: Latest
- **Category**: document-processing | nlp | utility
- **Framework**: Flet (cross-platform UI)
- **Language**: Python

## Purpose
Intelligently splits large documents into manageable chunks for LLM processing while preserving context and structure.

## Features
- **Smart Chunking**: Respects code blocks, lists, headers, and date boundaries
- **Date Detection**: Automatically detects and uses dates as chunk boundaries
- **Auto-Labeling**: Chunks labeled with dates, headers, or content preview
- **Configurable Overlap**: Context continuity between chunks
- **LLM Instructions**: Embed system prompts in chunk headers
- **Schema Editor**: Create/edit HTML parsing schemas on-the-fly
- **Dark/Light Theme**: Persistent theme preference

## Supported Formats
- **Markdown/Text**: Smart header and code block detection
- **HTML**: Schema-based parsing (Facebook, Snapchat, custom)
- **CSV/TSV**: Row-based chunking with header preservation

## Export Formats
- **TXT**: Single file with AI-friendly headers and metadata
- **JSON**: Structured format with chunk metadata
- **ZIP**: Individual files per chunk

## Installation
```bash
cd C:/Users/matts/AI_Workspace/Tools/Chunker
pip install -r requirements.txt
python main.py
```

## Build Standalone
```bash
flet build windows  # Creates .exe
flet build macos    # Creates .app
flet build linux    # Creates binary
flet build web      # Creates PWA
flet build apk      # Creates Android app
flet build ipa      # Creates iOS app
```

## Use Cases
- Split large documents for LLM context windows
- Parse Facebook/Snapchat message exports
- Chunk legal documents by date/speaker
- Split research papers by sections
- Process CSV datasets with header preservation

## Architecture
- **Parsers**: File format parsers (markdown, html, csv, tsv)
- **Chunkers**: Chunking strategies (smart chunker with metadata)
- **Exporters**: Export formats (txt, json, zip)
- **Schemas**: HTML parsing schemas (facebook, snapchat, generic)
- **UI**: Flet-based user interface

---
**Last Updated**: 2026-03-15
**Status**: Production Ready
