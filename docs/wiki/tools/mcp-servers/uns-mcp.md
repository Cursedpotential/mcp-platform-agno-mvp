# Unstructured API MCP (UNS-MCP)

## Overview
- **What**: MCP server for Unstructured API - manages sources, destinations, workflows, and jobs for document processing
- **Version**: Latest
- **Category**: document-processing | workflow | mcp-server
- **Framework**: FastMCP
- **Language**: Python 3.12+

## Purpose
Manages end-to-end document processing workflows with support for multiple sources and destinations.

## Available Tools (20+)
- list_sources - List available sources
- get_source_info - Get detailed source information
- create_source_connector - Create source connector
- update_source_connector - Update source connector
- delete_source_connector - Delete source connector
- list_destinations - List available destinations
- get_destination_info - Get destination information
- create_destination_connector - Create destination connector
- update_destination_connector - Update destination connector
- delete_destination_connector - Delete destination connector
- list_workflows - List workflows
- get_workflow_info - Get workflow details
- create_workflow - Create new workflow
- run_workflow - Run specific workflow
- update_workflow - Update workflow
- delete_workflow - Delete workflow
- list_jobs - List jobs for workflow
- get_job_info - Get job details
- cancel_job - Cancel job
- list_workflows_with_finished_jobs - List completed workflows

## Supported Connectors
**Sources**: S3, Azure, Google Drive, OneDrive, Salesforce, Sharepoint
**Destinations**: S3, Weaviate, Pinecone, AstraDB, MongoDB, Neo4j, Databricks

## Installation
```bash
cd C:/Users/matts/Projects/TheBigOne/dial-stack/utilities/mcp-servers/UNS-MCP
uv sync
export UNSTRUCTURED_API_KEY=your-key
uv run uns_mcp/server.py
```

## Use Cases
- S3 to vector DB pipelines
- Azure to Weaviate workflows
- Google Drive to Neo4j ingestion
- Document processing automation
- Multi-source data consolidation

## Dependencies
- fastmcp
- unstructured-client

---
**Last Updated**: 2026-03-15
**Status**: Production Ready
