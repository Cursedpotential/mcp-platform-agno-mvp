# Manipulative Expression Recognition (MER)

## Overview
- **What**: LLM-powered tool for detecting manipulative communication styles in conversations and text
- **Version**: Latest
- **Category**: nlp | behavioral-analysis | ai-safety
- **Language**: Python

## Purpose
Detects and analyzes manipulative communication patterns using LLMs with dual-prompt approach and anonymization.

## Features
- **Dual-Prompt Approach**: Closed-ended (specific labels) + open-ended (unrestricted)
- **Anonymization**: Replaces names, organizations, places with abstract identifiers
- **Confidence Scoring**: Multiple sampling for reliability assessment
- **Multiple Outputs**: JSON, HTML, PDF
- **Detailed Analysis**: Expression-level annotations with confidence scores
- **Summary Metrics**: Quantitative counts per participant
- **Qualitative Evaluation**: Descriptive summary of communication patterns

## Manipulation Styles Detected
- Diminishing
- Ignoring
- Victim playing
- Invalidation
- Exaggeration and dramatization
- Aggression
- Changing the topic
- Impatience
- And many more...

## Installation
```bash
cd C:/Users/matts/AI_Workspace/Tools/NLP/Manipulative-Expression-Recognition
pip install -r requirements.txt
export OPENAI_API_KEY=your-key  # or set OPENAI_API_KEY on Windows
python Recogniser.py
```

## Usage
```bash
# Basic usage (uses sample data)
python Recogniser.py

# With custom input
python Recogniser.py input_file.txt output_file.json

# With custom labels
python Recogniser.py input_file.txt output_file.json labels.txt

# With ignored labels
python Recogniser.py input_file.txt output_file.json labels.txt ignored.txt
```

## Input Format
```
Person A: Their message.

Person B: Response text.

Person A: More messages.
```

## Output Formats
- **JSON**: Structured data with expressions, counts, qualitative evaluation
- **HTML**: Rendered conversation with highlighted manipulative expressions
- **PDF**: Printable report with SVG summary diagram

## Use Cases
- Benchmark LLM outputs for manipulation
- Analyze human conversations for manipulation patterns
- Detect prompt injection attempts
- Evaluate news articles and blog posts
- Support victims of manipulation
- AI safety evaluation

## Key Capabilities
- Expression-level annotation with confidence scores
- Summary statistics per participant
- Qualitative analysis of communication patterns
- Anonymization for privacy
- Multiple output formats

---
**Last Updated**: 2026-03-15
**Status**: Production Ready
**GitHub**: https://github.com/levitation-opensource/Manipulative-Expression-Recognition
