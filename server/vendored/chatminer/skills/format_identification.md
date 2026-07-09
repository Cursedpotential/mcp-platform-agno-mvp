# Skill: Format Identification

## Purpose
Determine which parser to use for a given file when auto-detection is uncertain.

## When to Use
- Auto-detection returned low confidence (<70%)
- File has unusual naming or content
- Batch processing shows many "unknown" files

## How to Identify

### Step 1: Check the filename
| Filename Pattern | Likely Source |
|-----------------|---------------|
| `conversations.json` | ChatGPT official OR Perplexity GDPR |
| `Google_Gemini_*.md` | Gemini Chrome extension |
| `chatgpt_export.*` | ChatGPT |
| `claude_conversation.*` | Claude |
| `*.jsonl` | Claude Code |
| `perplexity_*.json` | Perplexity GDPR |

### Step 2: Check content signatures (first 2KB)
| Signature | Source |
|-----------|--------|
| `"mapping"` + `"title"` + `"create_time"` | ChatGPT official |
| `"**User:**"` + `"**Response:**"` + `chatgpt.com/c/` | ChatGPT Share |
| `"Google Gemini"` + `"Exported on:"` + `🤖` `👤` | Gemini Chrome |
| `"uuid"` + `"answers"` + `"mode"` + `"citations"` | Perplexity GDPR |
| `"role": "user"` + `"content"` (per line) | Claude Code JSONL |
| `"## Sources"` + `[Title](URL)` | Perplexity Plugin |

### Step 3: Use the CLI tool
```bash
python -m chatminer parse file.md --source chatgpt_share
# If wrong, try another:
python -m chatminer parse file.md --source gemini_chrome
```

## Manual Fallback
If all auto-detection fails:
1. Open the file in a text editor
2. Look for role markers (who said what)
3. Look for timestamps
4. Look for source-specific branding (ChatGPT, Gemini, etc.)
5. Use the generic_md parser as last resort
