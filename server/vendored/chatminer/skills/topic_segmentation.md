# Skill: Topic Segmentation

## Purpose
Split interleaved conversations into semantically coherent topic chunks.

## When to Use
- When a single conversation covers multiple topics
- Before sending chunks to different cloud models
- For organizing evidence by subject matter

## How Segmentation Works

### Local Mode (2GB GPU)
```python
from chatminer.segmenters import LocalSegmenter

segmenter = LocalSegmenter()
segments = segmenter.segment(messages)
```

Uses sentence-transformers to embed messages, then cosine-similarity
sliding window to detect topic shifts. Processes ~1000 messages/minute.

### Colab Mode (T4 GPU)
```python
from chatminer.segmenters import get_segmenter

segmenter = get_segmenter("colab")
segments = segmenter.segment(messages)
```

Same algorithm but runs on Google Colab's T4 GPU (16GB VRAM).
Processes ~5000 messages/minute. Mount Google Drive for I/O.

### Configurable Mode (any provider)
```python
from chatminer.segmenters import ConfigurableSegmenter

# OpenAI embeddings
segmenter = ConfigurableSegmenter(provider="openai", model_name="text-embedding-3-small")

# Ollama local
segmenter = ConfigurableSegmenter(provider="ollama", model_name="nomic-embed-text")

# Gemini
segmenter = ConfigurableSegmenter(provider="gemini")

segments = segmenter.segment(messages)
```

## Topic Tags

| Tag | Description | Example |
|-----|-------------|---------|
| `personal_legal` | Personal history, legal strategy, evidence | "Timeline of April 2023 incident" |
| `development` | Code, architecture, platform building | "Parser architecture decision" |
| `emotional` | Feelings, trauma processing | "How I'm feeling about the case" |
| `mixed` | Interleaved topics | "Legal strategy + code discussion" |
| `unknown` | Cannot classify | Unclear or too short |

## Configuration

```python
from chatminer.segmenters.segmenter_local import SegmenterConfig

config = SegmenterConfig(
    model_name="all-MiniLM-L6-v2",     # Embedding model (80MB)
    window_size=3,                      # Messages to compare
    similarity_threshold=0.65,          # Below this = topic shift
    min_segment_size=2,                 # Min messages per segment
    max_segment_size=50,                # Max messages per segment
    device="auto",                      # cuda, cpu, or auto
    batch_size=32,                      # Embedding batch size
)

segmenter = LocalSegmenter(config)
```

## Edge Cases
- **Short conversations (<2 messages)**: Returned as single segment
- **All same topic**: Single segment with high confidence
- **Rapid topic switching**: May create many small segments — increase window_size
- **Very long conversations**: May exceed max_segment_size — segments split
