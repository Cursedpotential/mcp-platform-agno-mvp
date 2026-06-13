# Config-Driven Workflows — Skill Reference

## Overview
- **What**: Config-driven workflow engine for running identification tool pipelines
- **Version**: 1.0.0
- **Category**: orchestration
- **Installed In**: Py MCP Server (port 8082)

## Configuration
- **Config file**: `py-mcp-server/config/workflows.json`
- **Structure**: Two sections — `modules` (tool definitions) and `workflows` (module sequences)
- **Runtime modifiable**: Yes — via `workflow_update_config`, `workflow_add_module`, `workflow_remove_module`

## Config Structure
```json
{
  "modules": {
    "module_id": {
      "name": "Display Name",
      "tool": "actual_tool_function_name",
      "enabled": true,
      "timeout_ms": 30000,
      "config": {"key": "value"}
    }
  },
  "workflows": {
    "workflow_name": {
      "name": "Display Name",
      "description": "What this workflow does",
      "modules": ["module_id_1", "module_id_2"],
      "enabled": true
    }
  }
}
```

## API Patterns
```python
# List all workflows
workflow_list()

# Run a workflow
workflow_run(text="...", workflow_name="full_analysis", mode="pass1")

# Add a module to a workflow
workflow_add_module(workflow_name="full_analysis", module_id="new_module", position=5)

# Remove a module from a workflow
workflow_remove_module(workflow_name="full_analysis", module_id="old_module")

# Update config at runtime
workflow_update_config('{"modules": {"my_module": {"enabled": false}}}')
```

## Preset Workflows
| Workflow | Modules | Description |
|----------|---------|-------------|
| `full_analysis` | 10 | All identification tools in sequence |
| `quick_scan` | 3 | Language, HAP, doc quality only |
| `behavioral_only` | 3 | Behavioral, DARVO, coercive control |
| `pii_check` | 1 | PII detection only |

## Adding New Modules
1. Add module definition to `modules` section in `workflows.json`
2. Register the tool function with `register_tool("tool_name", func)` in server.py
3. Add module ID to desired workflow's `modules` array
4. No server restart needed if using `workflow_update_config`

## References
- Config file: `py-mcp-server/config/workflows.json`
- Engine: `py-mcp-server/src/tools/workflow_tools.py`
- Local reference: `docs/plans/2026-03-14-cognitive-synthesis-system-design.md`
