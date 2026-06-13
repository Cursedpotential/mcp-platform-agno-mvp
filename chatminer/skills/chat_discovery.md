# Skill: Chat Discovery

## Purpose
Find all AI chat export files scattered across directories.

## When to Use
- Starting a new batch processing job
- Migrating chat exports from multiple locations
- Audit: "do I have all my conversations?"

## How to Use
```python
from chatminer.parsers.discovery import discover_transcripts

results = discover_transcripts("./conversations", recursive=True)
for f in results:
    print(f"{f.source_hint}: {f.path} ({f.size_human})")
```

Or via CLI:
```bash
python -m chatminer discover ./conversations/ --recursive
```

## What It Finds
| Source | File Patterns | Confidence |
|--------|--------------|------------|
| ChatGPT Share | `*.md` with User:/Response: headers | 90%+ |
| ChatGPT Official | `conversations.json` | 80%+ |
| Gemini Chrome | `Google_Gemini_YYYY-MM-DD_HHMM.md` | 90%+ |
| Gemini JSON | `*.json` with author:user/model | 70%+ |
| Claude MD | `*.md` with Human:/Assistant: markers | 75%+ |
| Claude Code | `*.jsonl` with role:user/assistant | 80%+ |
| Perplexity GDPR | `conversations.json` with uuid/answers | 90%+ |
| Perplexity Plugin | `*.md` with Sources section | 70%+ |
| Generic MD | `*.md` with **User:**/**Assistant:** | 50%+ |

## Output Format
```json
{
  "confidence": 0.92,
  "path": "./conversations/chat_export.md",
  "size_human": "68.6 KB",
  "size_bytes": 70246,
  "source_hint": "chatgpt_share",
  "format_hint": "md"
}
```

## Edge Cases
- **False positives**: README.md files with conversation examples
- **Mixed directories**: Results sorted by confidence — review bottom items
- **Unknown formats**: Files with <50% confidence need manual review
