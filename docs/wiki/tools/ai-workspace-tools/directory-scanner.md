# Directory Scanner Pro

## Overview
- **What**: High-performance desktop application for scanning and analyzing directory structures with cloud drive detection
- **Version**: Latest
- **Category**: utility | file-analysis | desktop-app
- **Framework**: Wails v2 (Go + Vanilla JS)
- **Language**: Go + JavaScript

## Purpose
Scans directory structures with multi-threaded performance and detects cloud-synced files for comprehensive file analysis.

## Features
- **Multi-threaded Scanning**: Configurable worker pool for fast scanning
- **Cloud Drive Detection**: Identifies OneDrive, Google Drive, Dropbox, iCloud, Box
- **Lazy Loading**: Efficient memory usage with lazy-loaded directory trees
- **File Hashing**: SHA-256 hashing for files < 100MB
- **Multiple Exports**: JSON, CSV, Excel, HTML, PDF
- **Real-time Progress**: Live scanning statistics and speed calculation
- **Settings Persistence**: Saves user preferences

## Supported Cloud Drives
- OneDrive (multiple accounts)
- Google Drive (multiple accounts)
- Dropbox
- iCloud
- Box

## Export Formats
- **JSON**: Structured tree format
- **CSV**: Flat file listing
- **Excel**: Spreadsheet with formatting
- **HTML**: Interactive web view
- **PDF**: Printable report

## Installation
```bash
cd C:/Users/matts/AI_Workspace/Tools/DirectoryScanner
go mod download
go mod tidy
wails dev  # Development mode with hot reload
```

## Build
```bash
# Production build
build.bat
# or
wails build -platform windows/amd64 -ldflags "-H windowsgui -s -w" -o DirectoryScanner.exe
```

## Use Cases
- Directory analysis and reporting
- Cloud file detection
- File distribution analysis
- Storage optimization
- Evidence collection
- System auditing

## Architecture
- **Backend (Go)**: Multi-threaded scanning, cloud detection, export
- **Frontend (Vanilla JS)**: UI controls, progress display, settings
- **Wails**: Desktop application framework

## Key Capabilities
- Scan local directories
- Detect cloud-synced files
- Calculate file statistics
- Generate reports
- Export in multiple formats

---
**Last Updated**: 2026-03-15
**Status**: Production Ready
