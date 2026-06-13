# Voice Fingerprinting — Skill Reference

## Overview
- **What**: Authorial voice analysis using Burrows' Delta algorithm (faststylometry)
- **Version**: faststylometry v0.1.0 (MIT license)
- **Category**: nlp
- **Installed In**: Py MCP Server (port 8082)

## Configuration
- **Algorithm**: Burrows' Delta — measures stylistic distance between texts
- **Features**: Word length, vocabulary richness, sentence length, punctuation patterns, function word frequencies
- **CPU-based**: No GPU required
- **Audio support**: TODO — Resemblyzer for audio voice embeddings (256-dim)

## API Patterns
```python
# Basic fingerprint
fingerprint_voice(text="Text to analyze")

# With reference texts (for author comparison)
fingerprint_voice(
    text="Unknown author text",
    reference_texts='["Known author sample 1", "Known author sample 2"]'
)

# Response format
{
  "style_features": {
    "word_count": 150,
    "sentence_count": 8,
    "unique_words": 95,
    "vocab_richness": 0.633,
    "avg_word_length": 4.82,
    "avg_sentence_length": 18.75,
    "punctuation": {"periods": 8, "commas": 12, "exclamations": 2, ...},
    "caps_ratio": 0.02,
    "function_word_profile": {"the": 0.08, "i": 0.06, ...}
  },
  "delta_score": 0.23,           # If reference provided (lower = more similar)
  "author_probability": 0.77     # If reference provided (1 - delta)
}
```

## Integration Points
- **Input**: Text from evidence.messages.body
- **Output**: Stored in evidence.message_analysis.voice_style_features, voice_delta_score
- **Workflow**: Runs in `full_analysis` workflow
- **Use case**: Determine if messages from "unknown" numbers match known author's style

## Common Pitfalls
- Requires NLTK punkt_tab tokenizer
- Reference texts should be similar length for accurate comparison
- Burrows' Delta works best with longer texts (>100 words)

## References
- faststylometry: https://github.com/faststylometry/faststylometry
- Burrows' Delta: https://doi.org/10.1076/jlit.35.3.398.9176
- Local reference: `py-mcp-server/src/tools/voice_tools.py`
