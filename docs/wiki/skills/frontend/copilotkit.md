# CopilotKit — Skill Reference

## Overview
- **What**: React framework for human-in-the-loop (HITL) AI workflows. Evidence review, fact validation, conflict resolution.
- **Version**: Latest stable
- **Category**: Frontend/Framework
- **Installed In**: React 19 application (analyst dashboard)

## Configuration

### React Setup
```jsx
import { CopilotKit } from "@copilotkit/react-core";
import { CopilotSidebar } from "@copilotkit/react-ui";

export default function App() {
  return (
    <CopilotKit publicApiKey={process.env.REACT_APP_COPILOT_KEY}>
      <div className="main-app">
        <AnalystDashboard />
        <CopilotSidebar instructions="Review extracted facts and resolve conflicts." />
      </div>
    </CopilotKit>
  );
}
```

### Tool Registration
```jsx
import { useCopilotAction } from "@copilotkit/react-core";

function FactValidator() {
  useCopilotAction({
    name: "validate_fact",
    description: "User reviews and validates extracted fact",
    parameters: [
      { name: "factId", type: "string", description: "Unique fact ID" },
      { name: "approved", type: "boolean", description: "Approval decision" }
    ],
    handler: async ({ factId, approved }) => {
      await api.updateFactStatus(factId, approved);
    }
  });
  // ...
}
```

## API Patterns

- **Copilot Actions**: User-callable functions exposed to AI assistant
- **Context Sharing**: Dashboard state automatically fed to copilot for context
- **Multi-Step Workflows**: Guide user through validation → conflict resolution → approval
- **Streaming Responses**: Real-time updates as AI processes evidence

## Integration Points

- **DIAL Core**: Chat completions for multi-turn reasoning
- **Semantica Tools**: Invoke fact extraction/validation via MCP
- **PostgreSQL**: Load fact data for review
- **Evidence Visualization**: Display extracted facts, relations, conflicts
- **Analyst Dashboard**: Embedded copilot sidebar for guidance

## Common Pitfalls

- **Public API Key**: Use public key only; never expose secret/session keys to frontend
- **Context Size**: Large fact batches may exceed token limits; paginate or summarize
- **Function Signature**: Parameter names must match handler function exactly
- **Async Handlers**: Long operations should show progress; avoid blocking UI
- **State Sync**: Component state and copilot context can diverge; use useCallback strategically

## References
- [CopilotKit Documentation](https://docs.copilotkit.ai/)
- [React Integration Guide](https://docs.copilotkit.ai/guides/react)
- [Custom Actions](https://docs.copilotkit.ai/guides/actions)
- [HITL Patterns](https://docs.copilotkit.ai/guides/human-in-the-loop)
