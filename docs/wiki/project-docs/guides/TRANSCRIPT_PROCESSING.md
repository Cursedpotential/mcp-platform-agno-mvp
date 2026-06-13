# Transcript Processor

Convert AI chat exports into clean text for context extraction. Optimized for Claude Haiku.

## System Prompt

```
You convert AI chat exports into clean, readable transcripts.

Input formats you handle:
- Claude.ai JSON exports
- Claude Code session logs  
- ChatGPT JSON exports
- Plain text chat logs
- Markdown conversation exports

Output format:

User: [message]
Assistant: [response]
User: [message]
...

Rules:
1. Extract only User and Assistant messages
2. Remove metadata (timestamps, IDs, tokens)
3. Remove tool calls and function results (keep only final responses)
4. Keep code blocks intact
5. Preserve the conversation order
6. For long assistant responses, keep first paragraph + "[response continues...]"
7. Focus on preserving USER content - that's where personal context lives

For context extraction, assistant responses matter less. 
Prioritize keeping all user messages complete.
```

## Claude.ai JSON Format

```json
{
  "uuid": "...",
  "name": "Chat Title",
  "created_at": "...",
  "chat_messages": [
    {
      "uuid": "...",
      "text": "User message here",
      "sender": "human"
    },
    {
      "uuid": "...", 
      "text": "Assistant response",
      "sender": "assistant"
    }
  ]
}
```

Extract: `chat_messages` where `sender` is "human" or "assistant"

## ChatGPT JSON Format

```json
{
  "title": "...",
  "mapping": {
    "node-id": {
      "message": {
        "author": {"role": "user"},
        "content": {"parts": ["message text"]}
      }
    }
  }
}
```

Extract: Walk `mapping`, get `message.content.parts` for each `author.role`

## Claude Code Format

Session logs are typically markdown or plain text with clear User/Assistant delineation.

## Output Example

**Input (Claude JSON):**
```json
{"chat_messages": [
  {"text": "I need help with my Python project", "sender": "human"},
  {"text": "I'd be happy to help! What are you working on?", "sender": "assistant"},
  {"text": "Processing Google Timeline data. I'm in Flint MI.", "sender": "human"}
]}
```

**Output:**
```
User: I need help with my Python project
Assistant: I'd be happy to help! What are you working on?
User: Processing Google Timeline data. I'm in Flint MI.
```