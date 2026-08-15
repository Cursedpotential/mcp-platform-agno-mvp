# Classification & Sentiment Analysis Test System Design

## Overview

Build a front-end and test system to run conversation chunks and AI chat chunks through classification and sentiment analysis via LLM using **Ollama** and **hosted NVIDIA models**, enabling easy comparison of results, structured output, and classification quality with the ability to swap providers/models.

## Architecture

### Backend (Workbench API - FastAPI)

```
workbench/api/
├── app/
│   ├── service/
│   │   ├── classification.py       # NEW: Classification service with provider abstraction
│   │   ├── sentiment.py            # NEW: Sentiment analysis service
│   │   ├── model_providers.py      # NEW: Provider factory (Ollama, NVIDIA, etc.)
│   │   └── __init__.py
│   ├── runtime/
│   │   ├── classification.py       # NEW: Runtime router for classification endpoints
│   │   ├── sentiment.py            # NEW: Runtime router for sentiment endpoints
│   │   └── compare.py              # NEW: Runtime router for comparison endpoints
│   └── types/
│       └── classification.py       # NEW: Pydantic models for requests/responses
```

### Frontend (Workbench Web - Next.js)

```
workbench/web/src/
├── app/
│   └── classification-test/        # NEW: Test page route
│       ├── page.tsx
│       └── components/
│           ├── ModelSelector.tsx   # Provider/model selection
│           ├── InputEditor.tsx     # Text input for chunks
│           ├── ResultsTable.tsx    # Comparison table
│           ├── ResultCard.tsx      # Individual result display
│           └── ExportButton.tsx    # Export results
├── components/
│   └── classification/             # NEW: Reusable classification components
��── lib/
    └── classification-api.ts       # API client
```

## Backend Design

### 1. Provider Abstraction (`model_providers.py`)

```python
# Following server/core/settings.py pattern but for workbench-specific classification/sentiment
class ClassificationProvider(Protocol):
    """Protocol for classification providers."""
    async def classify(self, text: str, categories: list[str]) -> ClassificationResult: ...
    async def classify_batch(self, texts: list[str], categories: list[str]) -> list[ClassificationResult]: ...

class SentimentProvider(Protocol):
    """Protocol for sentiment providers."""
    async def analyze(self, text: str) -> SentimentResult: ...
    async def analyze_batch(self, texts: list[str]) -> list[SentimentResult]: ...

# Providers: Ollama, NVIDIA NIM, OpenRouter, etc.
```

### 2. Request/Response Types (`types/classification.py`)

```python
class ClassificationRequest(BaseModel):
    text: str
    categories: list[str]  # e.g., ["platform", "legal", "personal_history", "context"]
    provider: str = "ollama"  # ollama, nvidia, openrouter, etc.
    model_id: str | None = None
    temperature: float = 0.0
    max_tokens: int = 1024

class ClassificationResponse(BaseModel):
    category: str
    confidence: float
    reasoning: str
    raw_response: str
    provider: str
    model_id: str
    latency_ms: int

class SentimentRequest(BaseModel):
    text: str
    provider: str = "ollama"
    model_id: str | None = None

class SentimentResponse(BaseModel):
    sentiment: Literal["positive", "negative", "neutral", "mixed"]
    score: float  # -1 to 1
    emotions: dict[str, float]  # e.g., {"anger": 0.3, "joy": 0.1, "fear": 0.6}
    reasoning: str
    provider: str
    model_id: str
    latency_ms: int

class ComparisonRequest(BaseModel):
    texts: list[str]
    categories: list[str]
    providers: list[ProviderConfig]  # [{provider: "ollama", model_id: "glm-5.1"}, ...]
    include_sentiment: bool = True

class ComparisonResponse(BaseModel):
    results: list[ComparisonResult]  # One per text per provider
    summary: ComparisonSummary
```

### 3. API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/classification/classify` | Single classification |
| POST | `/api/v1/classification/batch` | Batch classification |
| POST | `/api/v1/sentiment/analyze` | Single sentiment |
| POST | `/api/v1/sentiment/batch` | Batch sentiment |
| POST | `/api/v1/comparison/run` | Run comparison across providers |
| GET | `/api/v1/comparison/providers` | List available providers/models |
| POST | `/api/v1/comparison/export` | Export results (JSON/CSV) |

## Frontend Design

### Main Page: `/classification-test`

**Layout:**
```
��─────────────────────────────────────────────────────────────��
│  Classification & Sentiment Test Lab                        │
├─────────────────────────────────────────────────────────────��
│  [Model Selector Panel]          │  [Input Editor]         │
│  ��─────────────────────────��     │  ��───────────────────��  │
│  │ Provider: [Ollama ��]    │     │  │ Text to analyze:  │  │
│  │ Model:    [glm-5.1 ��]   │     │  │ [textarea......]  │  │
│  │ Temperature: [0.0 ��]    │     │  │                   │  │
│  │                         │     │  │ Categories:       │  │
│  │ [Add Provider]          │     │  │ [platform, legal, │  │
│  │                         │     │  │  personal_history,│  │
│  │ Provider 2: [NVIDIA ��]  │     │  │  context]         │  │
│  │ Model:      [nemotron ��] │     │  │                   │  │
│  │                         │     │  │ [Run Analysis]    │  │
│  └─────────────────────────��     │  └───────────────────��  │
├─────────────────────────────────────────────────────────────��
│  [Results Comparison Table]                                 │
│  ��─────────────────────────────────────────────────────────��│
│  │ Text | Provider/Model | Category | Conf. | Sentiment    ││
│  │      |                |          |       | Score        ││
│  │------|----------------|----------|-------|--------------││
│  │ "My  | Ollama/glm-5.1 | legal    | 0.92  | negative     ││
│  │ ex..."| NVIDIA/nemotron| legal    | 0.88  | negative     ││
│  │      | Ollama/glm-5.1 | platform | 0.15  | neutral      ││
│  └─────────────────────────────────────────────────────────��│
│  [Export JSON] [Export CSV] [Clear Results]                 │
��─────────────────────────────────────────────────────────────��
```

### Key Components

1. **ModelSelector** - Multi-provider selection with model dropdown per provider
2. **InputEditor** - Textarea with category chips, batch input support
3. **ResultsTable** - Sortable, filterable comparison table with expandable rows
4. **ResultCard** - Detailed view with raw response, reasoning, latency
5. **ExportButton** - Download results as JSON/CSV

## Integration with Existing Systems

### 1. Reuse Server Core Model Factory
- Import `server.core.settings.build_model()` for provider chain
- Extend with classification/sentiment-specific prompts

### 2. Leverage Existing Classification Logic
- Use `server.analysis.lane_classifier` categories as defaults
- Extend with sentiment analysis prompts

### 3. Use Existing Eval Framework
- Add test cases to `evals/cases.py` for regression testing
- Run via `python -m evals --case classification-comparison`

### 4. Workbench API Patterns
- Follow `workbench/api/app/service/` patterns
- Use existing `workbench/api/app/runtime/` router pattern

## Implementation Phases

### Phase 1: Backend Core (Week 1)
- [ ] Provider abstraction layer
- [ ] Classification service with Ollama/NVIDIA
- [ ] Sentiment analysis service
- [ ] API endpoints
- [ ] Unit tests

### Phase 2: Frontend (Week 2)
- [ ] Model selector component
- [ ] Input editor with batch support
- [ ] Results comparison table
- [ ] Export functionality
- [ ] E2E tests

### Phase 3: Integration & Polish (Week 3)
- [ ] Connect to existing eval framework
- [ ] Add provider health checks
- [ ] Performance optimization
- [ ] Documentation

## Configuration

### Environment Variables
```bash
# Workbench API
CLASSIFICATION_OLLAMA_HOST=http://localhost:11434
CLASSIFICATION_NVIDIA_API_KEY=...
CLASSIFICATION_NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
CLASSIFICATION_OPENROUTER_API_KEY=...

# Default categories (can be overridden per request)
DEFAULT_CLASSIFICATION_CATEGORIES=platform,legal,personal_history,context
```

## Testing Strategy

### Unit Tests
- Provider factory returns correct instances
- Classification parsing handles edge cases
- Sentiment scoring normalization

### Integration Tests
- API endpoints return expected schemas
- Multi-provider comparison works
- Batch processing handles errors gracefully

### Eval Cases (Regression)
```python
# evals/cases.py additions
Case(
    name="classification-ollama-vs-nvidia",
    agent=classification_comparison_agent,
    input="I need to file a motion for custody modification...",
    criteria="Both providers classify as 'legal' with confidence > 0.8",
    expected_tool_calls=("classify_batch", "analyze_sentiment_batch")
)
```

## Future Extensions

1. **Prompt Templates** - Save/share prompt templates for different use cases
2. **Ground Truth Labels** - Compare against human-labeled data
3. **A/B Testing** - Statistical significance testing between providers
4. **Cost Tracking** - Token usage and cost per provider
5. **Custom Categories** - Dynamic category definition per project