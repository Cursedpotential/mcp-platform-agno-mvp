# DPK HAP Scoring — Skill Reference

## Overview
- **What**: Hate, Abuse, and Profanity scoring using IBM Granite 38M model
- **Version**: data-prep-toolkit-transforms v1.1.7
- **Category**: nlp
- **Installed In**: Py MCP Server (port 8082)

## Configuration
- **Model**: `ibm-granite/granite-guardian-hap-38m` (38M parameters, CPU-friendly)
- **Performance**: 6.16k tokens/sec on CPU
- **Larger model**: `ibm-granite/granite-guardian-hap-125m` (125M, slower, more accurate)
- **Environment**: `DPK_HAP_MODEL` — override model name (optional)

## API Patterns
```python
# Basic usage
dpk_hap_score(text="Some text to analyze", mode="pass1")

# Response format
{
  "score": 0.85,                    # Max HAP score (0-1)
  "sentence_scores": [0.1, 0.85],   # Per-sentence scores
  "categories": ["hap"],            # "hap" if score > 0.5, else "clean"
  "confidence": 0.85,
  "metadata": {"model": "granite-guardian-hap-38m", "processing_time_ms": 150}
}
```

## Integration Points
- **Input**: Raw text from evidence.messages.body
- **Output**: Stored in evidence.message_analysis.hap_score
- **Workflow**: Runs in `full_analysis` and `quick_scan` workflows
- **Downstream**: High HAP scores trigger behavioral analysis modules

## Common Pitfalls
- HAP model requires sentence splitting (NLTK punkt_tab) — must be downloaded in Dockerfile
- Scores are per-sentence, document score is the MAX
- Mode "pass1" vs "pass2" affects context window size

## References
- IBM Granite Guardian: https://huggingface.co/ibm-granite/granite-guardian-hap-38m
- DPK HAP Transform: https://github.com/IBM/data-prep-kit
- Local reference: `py-mcp-server/src/tools/dpk_tools.py`
