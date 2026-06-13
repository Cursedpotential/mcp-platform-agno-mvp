---
title: Dial-Stack Dependency Graph
version: 1.0.0
created: 2026-03-16
author: execution@opencode
status: active
---

# Dial-Stack Dependency Graph

Complete inventory of open source projects and libraries across the dial-stack monorepo.

## Tech Stack Summary

| Language | Package Managers | Manifest Files |
|----------|------------------|----------------|
| **Python** | pip, uv, hatch | 42 files |
| **TypeScript/JavaScript** | npm | 17 files |
| **Go** | go modules | 1 file |
| **Java** | Maven | 1 file |

**Total:** 55 dependency manifests

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        DIAL-STACK MONOREPO                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │   CLIENT    │    │  INFRA      │    │  TOOLS      │    │ UTILITIES   │  │
│  │  (React)    │    │ (FastAPI)   │    │  (Go/Py)    │    │  (Mixed)    │  │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘    └──────┬──────┘  │
│         │                  │                  │                  │          │
│         └──────────────────┴──────────────────┴──────────────────┘          │
│                                     │                                        │
│                        ┌────────────┴────────────┐                           │
│                        │      MCP SERVERS        │                           │
│                        │  (11 total servers)     │                           │
│                        └────────────┬────────────┘                           │
│                                     │                                        │
│         ┌───────────────────────────┼───────────────────────────┐            │
│         │                           │                           │            │
│  ┌──────┴──────┐            ┌───────┴───────┐           ┌────────┴────────┐ │
│  │  SEMANTICA  │            │  NER/ML/AI    │           │ DOC PROCESSING  │ │
│  │ (Knowledge) │            │  (Models)     │           │  (MinerU/PDF)   │ │
│  └──────┬──────┘            └───────┬───────┘           └────────┬────────┘ │
│         │                           │                           │            │
│         └───────────────────────────┴───────────────────────────┘            │
│                                     │                                        │
└─────────────────────────────────────┴────────────────────────────────────────┘
                                      │
                                      ▼
                    ┌─────────────────────────────────┐
                    │     STORAGE & EXTERNAL APIs      │
                    ├─────────────────────────────────┤
                    │ • Neo4j (knowledge graph)        │
                    │ • LanceDB (vector embeddings)    │
                    │ • PostgreSQL (relational)        │
                    │ • DuckDB (analytics)             │
                    │ • Redis (caching)                │
                    │ • OpenAI/Anthropic/Groq (LLMs)   │
                    └─────────────────────────────────┘
```

---

## Core Dependencies by Category

### 1. NLP & Machine Learning

| Library | Version | Projects Using | Purpose |
|---------|---------|----------------|---------|
| **spaCy** | >=3.4.0 | Semantica, Manip-Expr, Chunker | NLP pipeline, NER |
| **transformers** | >=4.20.0 | Semantica, Tether, TetherPro | HuggingFace models |
| **torch** | >=1.12.0 | Semantica, Tether, Toxicity | Deep learning |
| **sentence-transformers** | >=2.2.0 | Semantica | Embeddings |
| **scikit-learn** | >=1.0.0 | Semantica, Toxicity, Doc-Analyser | ML algorithms |
| **flair** | >=0.14.0 | py-mcp-server | NER (used by DPK) |
| **gensim** | >=4.3.0 | Semantica | Topic modeling |

### 2. Graph & Knowledge Storage

| Library | Version | Projects Using | Purpose |
|---------|---------|----------------|---------|
| **neo4j** | (driver) | Semantica, py-mcp-server | Graph database |
| **networkx** | >=2.8.0 | Semantica | Graph algorithms |
| **rdflib** | >=6.2.0 | Semantica | RDF/SPARQL |
| **lancedb** | (latest) | py-mcp-server | Vector storage |

### 3. MCP Framework

| Library | Version | Projects Using | Purpose |
|---------|---------|----------------|---------|
| **fastmcp** | >=2.0.0 | py-mcp-server, notebooklm-mcp, langextract-mcp | MCP server framework |
| **mcp[cli]** | >=1.13.1 | UNS-MCP, mcp-nltk | MCP SDK |
| **@modelcontextprotocol/sdk** | latest | js-mcp-server, ts-mcp-server, inspector | Node.js MCP SDK |

### 4. Data Processing

| Library | Version | Projects Using | Purpose |
|---------|---------|----------------|---------|
| **pandas** | >=1.3.0 | Semantica, py-mcp-server, Toxicity | DataFrames |
| **numpy** | >=1.21.0 | Semantica, Tether, Toxicity | Numerical computing |
| **pyarrow** | (latest) | py-mcp-server | Arrow format |
| **faiss-cpu** | >=1.7.0 | Semantica | Vector search |

### 5. Web & UI

| Library | Version | Projects Using | Purpose |
|---------|---------|----------------|---------|
| **React** | 18.x - 19.x | client, pandoc_wizard, inspector | Frontend UI |
| **Vite** | 5.x - 8.x | client, pandoc_wizard, inspector | Build tool |
| **Radix UI** | various | client, inspector | UI components |
| **Tailwind CSS** | 3.x | client, pandoc_wizard, inspector | Styling |
| **FastAPI** | (latest) | audit_logger, py-mcp-server | Python web framework |

### 6. LLM Providers

| Library | Version | Projects Using | Purpose |
|---------|---------|----------------|---------|
| **openai** | >=1.0.0 | Semantica[llm-openai] | OpenAI API |
| **anthropic** | >=0.49.0 | Semantica, UNS-MCP | Claude API |
| **groq** | >=0.4.0 | Semantica[llm-groq] | Groq API |
| **google-genai** | >=0.1.0 | Semantica, context-relay, lexicon | Gemini API |
| **ollama** | >=0.1.0 | Semantica[llm-ollama] | Local LLMs |

### 7. Document Processing

| Library | Version | Projects Using | Purpose |
|---------|---------|----------------|---------|
| **python-docx** | >=0.8.11 | Semantica | Word documents |
| **pypdf2** | >=2.10.0 | Semantica | PDF reading |
| **beautifulsoup4** | >=4.11.0 | Semantica, Chunker | HTML parsing |
| **lxml** | >=4.9.0 | Semantica | XML processing |
| **openpyxl** | >=3.0.10 | Semantica | Excel files |

### 8. Data Extraction & ETL

| Library | Version | Projects Using | Purpose |
|---------|---------|----------------|---------|
| **unstructured-client** | >=0.32.1 | UNS-MCP | Unstructured.io |
| **firecrawl-py** | >=1.14.1 | UNS-MCP | Web scraping |
| **selenium** | >=4.22.0 | notebooklm-mcp | Browser automation |
| **data-prep-toolkit** | >=1.1.7 | py-mcp-server | IBM DPK transforms |
| **presidio-analyzer** | >=2.2.355 | py-mcp-server | PII detection |

---

## Project-Specific Dependencies

### Semantica (Knowledge Graph)
```
semantica[all] >= 0.2.6
├── Core ML: numpy, pandas, scipy, scikit-learn
├── NLP: spacy, transformers, torch, sentence-transformers
├── Graph: neo4j, networkx, rdflib
├── Visualization: matplotlib, seaborn, plotly
├── Embeddings: faiss-cpu, fastembed, onnxruntime
├── Documents: beautifulsoup4, pypdf2, python-docx, openpyxl
├── Audio: librosa
├── Vision: opencv-python, pillow
└── LLM (optional): openai, groq, google-genai, anthropic, ollama
```

### MCP Servers
```
py-mcp-server
├── fastmcp
├── semantica[all] >= 0.2.6
├── lancedb, pyarrow
├── presidio-analyzer, presidio-anonymizer (PII)
├── flair (NER)
└── data-prep-toolkit-transforms

notebooklm-mcp
├── fastmcp >= 2.0.0
├── selenium, undetected-chromedriver
├── pydantic, click, rich
└── loguru, psutil

UNS-MCP
├── mcp[cli] >= 1.13.1
├── anthropic >= 0.49.0
├── firecrawl-py >= 1.14.1
├── unstructured-client >= 0.32.1
└── boto3 (AWS)

langextract-mcp
├── fastmcp >= 0.1.0
├── langextract >= 0.1.0
├── pydantic, python-dotenv
└── httpx
```

### Client (React Frontend)
```
client
├── @copilotkit/react-core, @copilotkit/react-ui
├── radix-ui/* (12 components)
├── react, react-dom (v19)
├── lucide-react (icons)
├── tailwind-merge, clsx
├── date-fns
├── wouter (router)
├── sonner (toast)
└── vite, typescript (build)
```

### Manipulative Expression Recognition
```
manipulative-expression-recognition
├── spacy >= 3.5.4
├── openai_async
├── tiktoken
├── rapidfuzz, fuzzysearch
├── cryptography
├── tenacity (retries)
└── pygal (charts)
```

---

## Dependency Graph (Mermaid)

```mermaid
graph TD
    subgraph "Client Layer"
        CLIENT[client<br/>React 19]
        COPILOT[@copilotkit]
        RADIX[Radix UI<br/>12 components]
    end

    subgraph "MCP Servers"
        PY_MCP[py-mcp-server]
        TS_MCP[ts-mcp-server]
        JS_MCP[js-mcp-server]
        NB_MCP[notebooklm-mcp]
        UNS_MCP[UNS-MCP]
        LANG_MCP[langextract-mcp]
        NLTK_MCP[mcp-nltk]
        DOC_MCP[Document-Analyser-MCP]
    end

    subgraph "Core Libraries"
        SEMANTICA[Semantica<br/>Knowledge Graph]
        FASTMCP[fastmcp]
        SDK_MCP[@modelcontextprotocol/sdk]
    end

    subgraph "ML/NLP"
        SPACY[spaCy]
        TRANS[transformers]
        TORCH[PyTorch]
        HF[HuggingFace]
    end

    subgraph "Storage"
        NEO4J[(Neo4j)]
        LANCEDB[(LanceDB)]
        POSTGRES[(PostgreSQL)]
        REDIS[(Redis)]
    end

    subgraph "LLM APIs"
        OPENAI[OpenAI]
        ANTHROPIC[Anthropic]
        GROQ[Groq]
        GEMINI[Gemini]
        OLLAMA[Ollama]
    end

    CLIENT --> COPILOT
    CLIENT --> RADIX

    PY_MCP --> SEMANTICA
    PY_MCP --> FASTMCP

    TS_MCP --> SDK_MCP
    JS_MCP --> SDK_MCP

    NB_MCP --> FASTMCP
    UNS_MCP --> SDK_MCP
    LANG_MCP --> FASTMCP

    SEMANTICA --> SPACY
    SEMANTICA --> TRANS
    SEMANTICA --> TORCH
    SEMANTICA --> NEO4J

    SPACY --> HF
    TRANS --> TORCH
    TRANS --> HF

    PY_MCP --> LANCEDB
    PY_MCP --> OPENAI
    PY_MCP --> ANTHROPIC

    SEMANTICA --> OPENAI
    SEMANTICA --> GROQ
    SEMANTICA --> GEMINI
    SEMANTICA --> OLLAMA

    UNS_MCP --> ANTHROPIC
    UNS_MCP --> OPENAI
```

---

## Common Dependencies Across Projects

| Dependency | Project Count | Projects |
|------------|---------------|----------|
| **pydantic** | 12+ | Semantica, MCP servers, inspector, utilities |
| **requests/httpx** | 10+ | Semantica, MCP servers, utilities |
| **python-dotenv** | 8+ | All MCP servers, Semantica |
| **rich** | 6+ | Semantica, notebooklm-mcp, utilities |
| **click** | 4+ | Semantica, notebooklm-mcp, utilities |
| **loguru** | 4+ | Semantica, py-mcp-server, notebooklm-mcp |
| **react/lucide-react** | 6+ | All frontends |
| **radix-ui** | 3+ | client, inspector |

---

## Security-Minded Dependencies

| Library | Purpose | CVE Status |
|---------|---------|------------|
| **presidio-analyzer** | PII detection | Monitor for updates |
| **cryptography** | Encryption | >= 41.0.2 recommended |
| **selenium** | Browser automation | >= 4.22.0 (security fixes) |
| **undetected-chromedriver** | Anti-detection | Keep updated |

---

## Recommendation: Dependency Consolidation

### Unified Core Stack
Create a monorepo-level requirements file for shared dependencies:

```toml
# pyproject.toml (root)
[project]
dependencies = [
    "pydantic>=2.8.0",
    "python-dotenv>=1.0.0",
    "rich>=13.0.0",
    "loguru>=0.7.0",
    "httpx>=0.25.0",
    "click>=8.1.0",
]

[project.optional-dependencies]
mcp = ["fastmcp>=2.0.0", "mcp[cli]>=1.13.1"]
ml = ["torch>=2.0.0", "transformers>=4.36.0", "spacy>=3.5.0"]
nlp = ["spacy>=3.5.0", "nltk>=3.8.0", "textblob>=0.17.0"]
viz = ["matplotlib>=3.5.0", "plotly>=5.10.0", "seaborn>=0.11.0"]
```

### Version Pinning Strategy
- **Critical**: cryptography, presidio, selenium (security)
- **Stable**: pydantic, fastmcp, mcp-sdk (API stability)
- **Flexible**: rich, loguru, click (utility libraries)

---

## Next Steps

1. **Lock File Generation**: Create `uv.lock` or `poetry.lock` at root
2. **Vulnerability Scan**: Run `pip-audit` or `safety check` on all requirements
3. **License Audit**: Verify all licenses are compatible (MIT/Apache preferred)
4. **Dependabot**: Enable GitHub Dependabot for automated updates
5. **MCP Server Audit**: Verify all 11 MCP servers use consistent SDK versions

---

## References

- [Python Dependency Management](./extensions/README.md)
- [MCP Server Development](./mcp-servers/)
- [Semantica Integration](./semantica.md)
- [WunderGraph Cosmo Federation](./wundergraph-cosmo/INTEGRATION.md)