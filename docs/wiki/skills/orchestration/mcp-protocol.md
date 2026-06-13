# Model Context Protocol (MCP) — Skill Reference

## Overview
- **What**: Standardized protocol for exposing tools and resources to LLM-based applications. Transport-agnostic interface for model contexts.
- **Version**: 1.0+
- **Category**: Orchestration/Protocol
- **Installed In**: DIAL Core, Semantica server, tool endpoints

## Configuration

### Stdio Transport (Default)
```python
# Server: Semantica registers tools
from fastmcp import FastMCP
server = FastMCP("semantica")

@server.tool()
def extract_facts(text: str) -> list:
    return semantica.extract_temporal_facts(text)

if __name__ == "__main__":
    server.run()  # Listens on stdin/stdout

# Client: DIAL Core invokes via subprocess
import subprocess
proc = subprocess.Popen(
  ["python", "semantica_server.py"],
  stdin=subprocess.PIPE,
  stdout=subprocess.PIPE
)
```

### HTTP Transport (Optional)
```python
# FastMCP with HTTP wrapper
from fastapi import FastAPI
app = FastAPI()

@app.post("/mcp/invoke")
async def invoke_tool(request: ToolRequest):
    return await server.handle_tool_call(request)
```

## API Patterns

- **Tool Discovery**: Client requests `list_tools()` to discover available operations
- **Tool Invocation**: `call_tool(name, arguments)` with JSON parameters
- **Result Streaming**: Large results chunked and streamed
- **Error Handling**: Tool errors returned as structured responses, not exceptions
- **Resource Context**: Optional resource trees for document/database contexts

```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "extract_facts",
    "arguments": { "text": "..." }
  }
}
```

## Integration Points

- **DIAL Core**: Client connecting to tool servers (Semantica, etc.)
- **Semantica**: Exposes NLP pipeline as callable tools
- **Custom Applications**: Any tool server implementing MCP protocol
- **CopilotKit**: Frontend invokes tools via DIAL Core → MCP → tool endpoint
- **Cosmo GraphQL**: Can wrap tool results as GraphQL types

## Common Pitfalls

- **Stdio Buffering**: Large messages may buffer; explicit flush needed on some systems
- **Error Serialization**: Custom exception types not JSON-serializable; convert to strings
- **Timeout Handling**: Long-running tools need progress indicators; clients may timeout
- **Argument Validation**: Server responsible for type checking; clients send JSON
- **Resource Management**: Server must clean up file handles, DB connections; no auto-close

## References
- [MCP Specification](https://modelcontextprotocol.io/specification)
- [FastMCP Library](https://github.com/dial-stack/fastmcp)
- [Tool Best Practices](https://modelcontextprotocol.io/docs/tools/)
- [Transport Protocols](https://modelcontextprotocol.io/docs/concepts/)
