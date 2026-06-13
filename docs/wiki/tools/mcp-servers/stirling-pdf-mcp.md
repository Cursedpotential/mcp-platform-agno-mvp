# Stirling PDF MCP

## Overview
- **What**: MCP server for Stirling PDF API - converts files to PDF, merges PDFs, compresses PDFs
- **Version**: 1.0.0
- **Category**: document-processing | pdf | mcp-server
- **Framework**: Node.js MCP SDK
- **Language**: JavaScript

## Purpose
Provides PDF manipulation capabilities through MCP tools:
- Convert any file format to PDF (DOCX, MD, HTML, images, etc.)
- Merge multiple PDF files
- Compress PDFs to reduce file size
- Batch convert entire directories

## Available Tools
- convert_to_pdf - Convert any supported file to PDF
- convert_markdown_to_pdf - Convert Markdown files to PDF
- convert_html_to_pdf - Convert HTML files to PDF
- convert_office_to_pdf - Convert Office documents to PDF
- merge_pdfs - Merge multiple PDF files
- compress_pdf - Compress PDF to reduce file size
- batch_convert_to_pdf - Batch convert multiple files in a directory

## Installation
```bash
cd C:/Users/matts/Projects/TheBigOne/dial-stack/utilities/mcp-servers/stirling-pdf-mcp
npm install
export STIRLING_PDF_URL=http://localhost:8080
node index.js
```

## Use Cases
- Convert DOCX/XLSX/PPTX to PDF
- Batch convert document directories
- Merge multiple PDFs
- Compress PDFs for storage
- Convert Markdown documentation to PDF
- Generate PDF reports from HTML

## Dependencies
- node-fetch
- form-data
- @modelcontextprotocol/sdk

---
**Last Updated**: 2026-03-15
**Status**: Production Ready
