# NLP Toxicity Analyzer

## Overview
- **What**: Deep learning model using LSTM and TensorFlow to classify text as toxic, severe toxic, obscene, threat, insult, or identity hate
- **Version**: Latest
- **Category**: nlp | content-moderation | deep-learning
- **Framework**: TensorFlow + Streamlit
- **Language**: Python

## Purpose
Classifies text content into toxicity categories using trained LSTM neural network for content moderation and safety.

## Features
- **Multi-class Classification**: 6 toxicity categories
- **LSTM Architecture**: Deep learning model trained on toxic/non-toxic phrases
- **Percentage Scores**: Shows confidence percentage for each category
- **Dual Interface**: Streamlit UI + Flask API
- **Real-time Analysis**: Instant classification results

## Toxicity Categories
1. **Toxic**: General toxic content
2. **Severe Toxic**: Extremely harmful content
3. **Obscene**: Obscene language
4. **Threat**: Threatening language
5. **Insult**: Insulting content
6. **Identity Hate**: Hate speech targeting identity

## Installation
```bash
cd C:/Users/matts/AI_Workspace/Tools/NLP/NLP-Toxicity-Analyzer
pip install -r requirements.txt
```

## Usage
```bash
# Start Flask API (first)
python api.py

# Start Streamlit UI (in another terminal)
streamlit run app.py
```

## API Endpoints
- **POST /predict**: Classify text for toxicity
- Input: JSON with text field
- Output: Toxicity scores for each category

## Streamlit UI
- Text input field
- Real-time classification
- Percentage display for each category
- Visual representation of results

## Use Cases
- Content moderation
- Toxic comment detection
- Online safety monitoring
- Conversation quality assessment
- Hate speech detection
- User-generated content filtering

## Model Architecture
- **Input**: Text tokenization
- **Hidden Layers**: LSTM cells with dropout
- **Output**: 6-class softmax classification
- **Training Data**: Toxic and non-toxic phrases

## Performance
- Fast inference (< 100ms per text)
- Handles variable-length inputs
- Batch processing capable

---
**Last Updated**: 2026-03-15
**Status**: Production Ready
