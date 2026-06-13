# Archive Extractor — Skill Reference

## Overview
- **What**: ZIP/archive extraction with automatic R2 (Cloudflare Workers) file linking
- **Status**: 🔴 Pending Implementation
- **Target Server**: TS MCP
- **Category**: pending
- **MCP Tool**: Not yet implemented

## Legacy Reference
- **Source**: `MCP_Tool_Platform/ingest/archive-handler.ts` (READ-ONLY)
- **Key patterns**: Archive handling, R2 upload, file linking, cleanup

## What It Does
- Extracts files from ZIP, TAR, TAR.GZ archives
- Uploads extracted files to Cloudflare R2 storage
- Generates shareable/accessible URLs for extracted files
- Manages temporary local extraction directory
- Handles nested archives and complex structures

## Supported Formats
- ZIP archives (.zip)
- TAR archives (.tar)
- Compressed TAR (.tar.gz, .tgz)
- Potential: 7z, RAR (if library support available)

## Integration Points
- Input: Archive files from upload or evidence collection
- Output: List of extracted files with R2 URLs
- Used by: File ingestion pipeline, evidence processing
- Related: Format detector (identifies archives), all parsers

## Implementation Considerations
- R2 credentials and bucket configuration
- Temp directory management and cleanup
- Nested archive handling strategy
- File naming and deduplication
- Access control and sharing model for R2 URLs
- Virus/malware scanning on extraction (optional)

## Implementation Tasks
- [ ] Create TS MCP tool `extract_archive`
- [ ] Implement ZIP, TAR, TAR.GZ support
- [ ] Add R2 integration (upload and URL generation)
- [ ] Implement temporary directory cleanup
- [ ] Handle nested archives appropriately
- [ ] Error handling for corrupt archives
- [ ] Test with various archive types and sizes

## Configuration Needed
- R2 account credentials (access key, secret)
- R2 bucket name
- Temp directory path
- URL expiration policy (if using signed URLs)

## Testing Checklist
- [ ] ZIP extraction and R2 upload
- [ ] TAR/TAR.GZ extraction
- [ ] Nested archive handling
- [ ] Large archive processing
- [ ] Error handling (corrupt files)
