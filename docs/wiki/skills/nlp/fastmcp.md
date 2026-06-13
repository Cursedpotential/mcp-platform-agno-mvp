# FastMCP — Skill Reference

## Overview
- **What**: Lightweight Python SDK for building Model Context Protocol (MCP) servers. Transport layer for tool invocation.
- **Version**: 0.1+
- **Category**: NLP/Protocol
- **Installed In**: Python environments hosting tool servers (Semantica, etc.)

## Configuration

### Server Setup
```python
from fastmcp import FastMCP

server = FastMCP("semantica-tools")

# Register a tool
@server.tool()
def extract_entities(text: str) -> list[dict]:
    """Extract named entities from text."""
    return semantica.extract_entities(text)

@server.tool()
def detect_conflicts(facts: list[dict]) -> list[dict]:
    """Detect conflicts in fact batch."""
    return semantica.detect_conflicts(facts)

# Run server (stdio transport)
if __name__ == "__main__":
    server.run()
```

### Transport Options
- **stdio**: Direct process I/O (default, used by DIAL Chat)
- **HTTP**: Optional REST wrapper for network isolation

## API Patterns

- **Tool Registration**: `@server.tool()` decorator with type hints
- **Context Sharing**: Tools can access server state via closure
- **Error Handling**: Exceptions returned as error responses (not crashes)
- **Logging**: Server logs available on stderr for debugging

```python
@server.tool()
def long_running_task(data: list) -> dict:
    """Process data asynchronously."""
    try:
        result = process(data)
        return {"status": "success", "result": result}
    except ValueError as e:
        return {"status": "error", "message": str(e)}
```

## Integration Points

- **DIAL Chat**: Requests tools via MCP client → FastMCP server (stdio)
- **CopilotKit**: Frontend can invoke tools for multi-step workflows
- **Orchestration**: Cosmo GraphQL can route to MCP endpoints
- **Async Processing**: Tools can trigger background jobs (e.g., embedding generation)

## Common Pitfalls

- **Type Hints Required**: All parameters must have type annotations; used for validation
- **Blocking I/O**: Long operations block stdio; consider async patterns
- **Encoding**: JSON serialization may fail on custom types; use `dict` return types
- **Error Messages**: Return error responses, not exceptions; clients expect structured format
- **Resource Cleanup**: No automatic cleanup; manage database connections manually

## References
- [FastMCP GitHub](https://github.com/dial-stack/fastmcp) (internal)
- [MCP Protocol Specification](https://modelcontextprotocol.io/specification)
- [Python Type Hints](https://docs.python.org/3/library/typing.html)
