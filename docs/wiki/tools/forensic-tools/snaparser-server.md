# Snaparser Server

## Overview
- **What**: Server for parsing Snapchat history exports - converts JSON chat history to structured formats
- **Version**: 0.0.1
- **Category**: forensics | social-media-parsing | digital-evidence
- **Language**: Go

## Purpose
Parses Snapchat data exports and converts them into structured, analyzable formats for digital forensics.

## Features
- HTTP/HTTPS server support
- Rate limiting (none, lenient, normal, strict)
- CORS support with configurable origins
- Docker containerization
- TOML configuration support
- Logging capabilities

## Installation
```bash
# Go install
go install github.com/vanillaiice/snaparser_server/cmd/snaparser_server@latest

# Docker
docker pull vanillaiice/snaparser_server:latest
docker build -t snaparser_server .
```

## Usage
```bash
# Run server with HTTP
snaparser_server --http --endpoint "/parse"

# Run with config file
snaparser_server --load config.toml

# Parse Snapchat history
curl -F 'file=@chat_history.json;type=application/json' http://localhost:8888/parse -o chats.zip

# Docker usage
docker run --rm -p 8888:8888 vanillaiice/snaparser_server -t -g
```

## Configuration Options
- **Port**: Listen port (default: 8888)
- **Endpoint**: Upload endpoint path (default: /upload)
- **Rate Limiter**: none, lenient, normal, strict
- **SSL**: Certificate and key file paths
- **Logging**: Enable/disable logging
- **CORS**: Allowed origins and methods

## Use Cases
- Social media forensics
- Conversation extraction
- Digital evidence collection
- Snapchat data analysis
- Timeline reconstruction

## Dependencies
- Go 1.16+
- Docker (optional)

---
**Last Updated**: 2026-03-15
**Status**: Production Ready
**GitHub**: https://github.com/vanillaiice/snaparser_server
**License**: GPLv3
