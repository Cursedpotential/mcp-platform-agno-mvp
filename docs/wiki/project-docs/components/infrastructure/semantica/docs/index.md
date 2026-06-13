<div align="center">
  <img src="assets/img/Semantica Logo.png" alt="Semantica Logo" width="450" height="auto">
  
  <h1>🧠 Semantica</h1>
  
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.8+-blue.svg" alt="Python 3.8+"></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT"></a>
  <a href="https://badge.fury.io/py/semantica"><img src="https://img.shields.io/badge/pypi-v0.2.3-blue.svg" alt="PyPI version"></a>
  <a href="https://pypi.org/project/semantica/"><img src="https://img.shields.io/pypi/dm/semantica" alt="Monthly Downloads"></a>
  <a href="https://pepy.tech/project/semantica"><img src="https://static.pepy.tech/badge/semantica" alt="Total Downloads"></a>
  <a href="https://semantica.readthedocs.io/"><img src="https://img.shields.io/badge/docs-latest-brightgreen.svg" alt="Documentation"></a>
  <a href="https://discord.gg/N7WmAuDH"><img src="https://img.shields.io/badge/Discord-Join%20Us-7289da?style=flat&logo=discord&logoColor=white" alt="Discord"></a>
  
  <p><strong>Open-Source Semantic Layer & Knowledge Engineering Framework</strong></p>
  
  <p><strong>Transform Chaos into Intelligence. Build AI systems that are explainable, traceable, and trustworthy — not black boxes.</strong></p>
  
  <p><em>The semantic intelligence layer that makes your AI agents auditable, explainable, and trustworthy. Perfect for high-stakes domains where mistakes have real consequences.</em></p>
  
  <p>🆓 <strong>Open Source</strong> • 📜 <strong>MIT Licensed</strong> • 🚀 <strong>Production Ready</strong> • 🌍 <strong>Community Driven</strong></p>
  
  <p>
    <a href="getting-started/" class="md-button md-button--primary">Get Started</a>
    <a href="https://github.com/Hawksight-AI/semantica" class="md-button">View on GitHub</a>
  </p>
</div>

---

## 🚀 Why Semantica?

**Semantica** bridges the **semantic gap** between text similarity and true meaning. It's the **semantic intelligence layer** that makes your AI agents auditable, explainable, and trustworthy.

Perfect for **high-stakes domains** where mistakes have real consequences.

---

### ⚡ Get Started in 30 Seconds

```bash
pip install semantica
```

```python
from semantica.semantic_extract import NERExtractor
from semantica.kg import GraphBuilder

# Extract entities and build knowledge graph
ner = NERExtractor(method="ml", model="en_core_web_sm")
entities = ner.extract("Apple Inc. was founded by Steve Jobs in 1976.")
kg = GraphBuilder().build({"entities": entities, "relationships": []})

print(f"Built KG with {len(kg.get('entities', []))} entities")
```

**[📖 Full Quick Start](getting-started.md)** • **[🍳 Cookbook Examples](cookbook.md)** • **[💬 Join Discord](https://discord.gg/N7WmAuDH)** • **[⭐ Star Us](https://github.com/Hawksight-AI/semantica)**

---

## Core Value Proposition

| **Trustworthy** | **Explainable** | **Auditable** |
|:------------------:|:------------------:|:-----------------:|
| Conflict detection & validation | Transparent reasoning paths | Complete provenance tracking |
| Rule-based governance | Entity relationships & ontologies | W3C PROV-O compliant lineage |
| Production-grade QA | Multi-hop graph reasoning | Source tracking & integrity verification |

---

## Key Features & Benefits

### Not Just Another Agentic Framework

**Semantica complements** LangChain, LlamaIndex, AutoGen, CrewAI, Google ADK, Agno, and other frameworks to enhance your agents with:

| Feature | Benefit |
|:--------|:--------|
| **Auditable** | Complete provenance tracking with W3C PROV-O compliance |
| **Explainable** | Transparent reasoning paths with entity relationships |
| **Provenance-Aware** | End-to-end lineage from documents to responses |
| **Validated** | Built-in conflict detection, deduplication, QA |
| **Governed** | Rule-based validation and semantic consistency |
| **Version Control** | Enterprise-grade change management with integrity verification |

### Perfect For High-Stakes Use Cases

| 🏥 **Healthcare** | 💰 **Finance** | ⚖️ **Legal** |
|:-----------------:|:--------------:|:------------:|
| Clinical decisions | Fraud detection | Evidence-backed research |
| Drug interactions | Regulatory support | Contract analysis |
| Patient safety | Risk assessment | Case law reasoning |

| 🔒 **Cybersecurity** | 🏛️ **Government** | 🏭 **Infrastructure** | 🚗 **Autonomous** |
|:-------------------:|:----------------:|:-------------------:|:-----------------:|
| Threat attribution | Policy decisions | Power grids | Decision logs |
| Incident response | Classified info | Transportation | Safety validation |

### Powers Your AI Stack

- **GraphRAG Systems** — Retrieval with graph reasoning and hybrid search
- **AI Agents** — Trustworthy, accountable multi-agent systems with semantic memory
- **Reasoning Models** — Explainable AI decisions with reasoning paths
- **Enterprise AI** — Governed, auditable platforms that support compliance

### Integrations

- **Docling Support** — Document parsing with table extraction (PDF, DOCX, PPTX, XLSX)
- **AWS Neptune** — Amazon Neptune graph database support with IAM authentication
- **Custom Ontology Import** — Import existing ontologies (OWL, RDF, Turtle, JSON-LD)

> **Built for environments where every answer must be explainable and governed.**

---

## 🚨 The Problem: The Semantic Gap

### Most AI systems fail in high-stakes domains because they operate on **text similarity**, not **meaning**.

### Understanding the Semantic Gap

The **semantic gap** is the fundamental disconnect between what AI systems can process (text patterns, vector similarities) and what high-stakes applications require (semantic understanding, meaning, context, and relationships).

**Traditional AI approaches:**
- Rely on statistical patterns and text similarity
- Cannot understand relationships between entities
- Cannot reason about domain-specific rules
- Cannot explain why decisions were made
- Cannot trace back to original sources with confidence

**High-stakes AI requires:**
- Semantic understanding of entities and their relationships
- Domain knowledge encoded as formal rules (ontologies)
- Explainable reasoning paths
- Source-level provenance
- Conflict detection and resolution

**Semantica bridges this gap** by providing a semantic intelligence layer that transforms unstructured data into validated, explainable, and auditable knowledge.

### What Organizations Have vs What They Need

| **Current State** | **Required for High-Stakes AI** |
|:---------------------|:-----------------------------------|
| PDFs, DOCX, emails, logs | Formal domain rules (ontologies) |
| APIs, databases, streams | Structured and validated entities |
| Conflicting facts and duplicates | Explicit semantic relationships |
| Siloed systems with no lineage | **Explainable reasoning paths** |
| | **Source-level provenance** |
| | **Audit-ready compliance** |

### The Cost of Missing Semantics

- **Decisions cannot be explained** — No transparency in AI reasoning
- **Errors cannot be traced** — No way to debug or improve
- **Conflicts go undetected** — Contradictory information causes failures
- **Compliance becomes impossible** — No audit trails for regulations

**Trustworthy AI requires semantic accountability.**

---

## 🆚 Semantica vs Traditional RAG

| Feature | Traditional RAG | Semantica |
|:--------|:----------------|:----------|
| **Reasoning** | ❌ Black-box answers | ✅ Explainable reasoning paths |
| **Provenance** | ❌ No provenance | ✅ W3C PROV-O compliant lineage tracking |
| **Search** | ⚠️ Vector similarity only | ✅ Semantic + graph reasoning |
| **Quality** | ❌ No conflict handling | ✅ Explicit contradiction detection |
| **Safety** | ⚠️ Unsafe for high-stakes | ✅ Designed for governed environments |
| **Compliance** | ❌ No audit trails | ✅ Complete audit trails with integrity verification |

---

## 🧩 Semantica Architecture

### 1️⃣ Input Layer — Governed Ingestion
- 📄 **Multiple Formats** — PDFs, DOCX, HTML, JSON, CSV, Excel, PPTX
- 🔧 **Docling Support** — Docling parser for table extraction
- 💾 **Data Sources** — Databases, APIs, streams, archives, web content
- 🎨 **Media Support** — Image parsing with OCR, audio/video metadata extraction
- � **Single Pipeline** — Unified ingestion with metadata and source tracking

### 2️⃣ Semantic Layer — Trust & Reasoning Engine
- 🔍 **Entity Extraction** — NER, normalization, classification
- 🔗 **Relationship Discovery** — Triplet generation, semantic links
- 📐 **Ontology Induction** — Automated domain rule generation
- 🔄 **Deduplication** — Jaro-Winkler similarity, conflict resolution
- ✅ **Quality Assurance** — Conflict detection, validation
- 📊 **Provenance Tracking** — W3C PROV-O compliant lineage tracking across all modules
- 🧠 **Reasoning Traces** — Explainable inference paths
- 🔐 **Change Management** — Version control with audit trails, checksums, compliance support

### 3️⃣ Output Layer — Auditable Knowledge Assets
- � **Knowledge Graphs** — Queryable, temporal, explainable
- 📐 **OWL Ontologies** — HermiT/Pellet validated, custom ontology import support
- 🔢 **Vector Embeddings** — FastEmbed by default
- ☁️ **AWS Neptune** — Amazon Neptune graph database support
- 🔍 **Provenance** — Every AI response links back to:
  - 📄 Source documents
  - 🏷️ Extracted entities & relations
  - 📐 Ontology rules applied
  - 🧠 Reasoning steps used

---

## 🏥 Built for High-Stakes Domains

Designed for domains where **mistakes have real consequences** and **every decision must be accountable**:

- **🏥 Healthcare & Life Sciences** — Clinical decision support, drug interaction analysis, medical literature reasoning, patient safety tracking
- **💰 Finance & Risk** — Fraud detection, regulatory support (SOX, GDPR, MiFID II), credit risk assessment, algorithmic trading validation
- **⚖️ Legal & Compliance** — Evidence-backed legal research, contract analysis, regulatory change tracking, case law reasoning
- **🔒 Cybersecurity & Intelligence** — Threat attribution, incident response, security audit trails, intelligence analysis
- **🏛️ Government & Defense** — Governed AI systems, policy decisions, classified information handling, defense intelligence
- **🏭 Critical Infrastructure** — Power grid management, transportation safety, water treatment, emergency response
- **🚗 Autonomous Systems** — Self-driving vehicles, drone navigation, robotics safety, industrial automation  

---

## � Who Uses Semantica?

- **🤖 AI / ML Engineers** — Building explainable GraphRAG & agents
- **⚙️ Data Engineers** — Creating governed semantic pipelines
- **📊 Knowledge Engineers** — Managing ontologies & KGs at scale
- **🏢 Enterprise Teams** — Requiring trustworthy AI infrastructure
- **🛡️ Risk & Compliance Teams** — Needing audit-ready systems  

---

## 🚀 Choose Your Path

<div class="grid cards" markdown>

-   :material-rocket-launch: **Quick Start**
    ---
    Get up and running with Semantica in minutes. Learn the basics of ingestion and extraction.
    
    [:arrow_right: Start Here](getting-started.md)

-   :material-book-open-page-variant: **Core Concepts**
    ---
    Deep dive into Knowledge Graphs, Ontologies, and Semantic Reasoning.
    
    [:arrow_right: Learn Concepts](concepts.md)

-   :material-code-braces: **API Reference**
    ---
    Detailed technical documentation for all Semantica modules and classes.
    
    [:arrow_right: View API](reference/core.md)

-   :material-chef-hat: **Cookbook**
    ---
    Interactive tutorials, real-world examples, and **14 domain-specific cookbooks**.
    
    [:arrow_right: Explore Cookbook](cookbook.md)

</div>

---

## 📦 Installation

!!! success "Now Available on PyPI!"
    Semantica is officially published on PyPI! Install it with a single command.

=== "From PyPI (Recommended)"

    Install Semantica directly from PyPI:

    ```bash
    # Install the core package
    pip install semantica

    # Or install with all optional dependencies
    pip install semantica[all]
    ```

=== "From Source"

    Install from the local source for the latest development version:

    ```bash
    # Clone the repository
    git clone https://github.com/Hawksight-AI/semantica.git
    cd semantica

    # Install in editable mode with core dependencies
    pip install -e .

    # Or install with all optional dependencies
    pip install -e ".[all]"
    ```

=== "Development"

    For contributors who want to modify the framework:

    ```bash
    # Clone the repository
    git clone https://github.com/Hawksight-AI/semantica.git
    cd semantica

    # Install in editable mode with dev dependencies
    pip install -e ".[dev]"
    ```

=== "Docker"

    Run Semantica in a containerized environment:

    ```bash
    docker pull semantica/semantica:latest
    docker run -it semantica/semantica
    ```

---

## 🚦 Quick Example

Semantica uses a modular architecture. You can use individual modules directly for maximum flexibility:

```python
from semantica.ingest import FileIngestor
from semantica.parse import DocumentParser
from semantica.semantic_extract import NERExtractor, RelationExtractor
from semantica.kg import GraphBuilder

# 1. Ingest documents
ingestor = FileIngestor()
documents = ingestor.ingest_directory("documents/", recursive=True)

# 2. Parse documents
parser = DocumentParser()
parsed_docs = [parser.parse_document(doc) for doc in documents]

# 3. Extract entities and relationships
ner = NERExtractor()
rel_extractor = RelationExtractor()

entities = []
relationships = []
for doc in parsed_docs:
    text = doc.get("full_text", "")
    doc_entities = ner.extract_entities(text)
    doc_rels = rel_extractor.extract_relations(text, entities=doc_entities)
    entities.extend(doc_entities)
    relationships.extend(doc_rels)

# 4. Build knowledge graph
builder = GraphBuilder(merge_entities=True)
kg = builder.build_graph(entities=entities, relationships=relationships)

print(f"Created graph with {len(kg.nodes)} nodes and {len(kg.edges)} edges")
```

!!! tip "Orchestration Option"
    For complex workflows, you can also use the `Semantica` class for orchestration. See the [Core Module](reference/core.md) documentation for details.

---

## 🎯 Why Semantica?

<div class="grid cards" markdown>

-   **🆓 Open Source**
    ---
    MIT licensed. No vendor lock-in. Full transparency.

-   **🚀 Production Ready**
    ---
    Battle-tested with quality assurance, conflict resolution, and validation.

-   **🧩 Modular Architecture**
    ---
    Use only what you need. Swap components easily.

-   **🌍 Community Driven**
    ---
    Built by developers, for developers. Active Discord community.

-   **📚 Comprehensive**
    ---
    End-to-end solution from ingestion to reasoning. No duct-taping required.

-   **🔬 Research-Backed**
    ---
    Based on latest research in knowledge graphs, ontologies, and semantic web.

</div>

---

## 🏗️ Built For

- **Data Scientists**: Transform messy data into clean knowledge graphs
- **Data Engineers**: Build scalable data pipelines with semantic enrichment
- **AI Engineers**: Build GraphRAG, AI agents, and multi-agent systems
- **Knowledge Engineers**: Generate and manage formal ontologies
- **Ontologists**: Design and validate domain-specific ontologies and taxonomies
- **Researchers**: Analyze scientific literature and build citation networks
- **ML Engineers**: Create semantic features for machine learning models
- **Enterprises**: Unify data silos into a semantic layer

---

## 📚 Learn More

- [Getting Started Guide](getting-started.md) - Your first knowledge graph in 5 minutes
- [Core Concepts](concepts.md) - Deep dive into knowledge graphs and ontologies
- [Cookbook](cookbook.md) - Real-world examples and **14 domain-specific cookbooks**
- [API Reference](reference/core.md) - Complete technical documentation

### 🍳 Recommended Cookbook Tutorials

Get hands-on with interactive Jupyter notebooks:

- **[Welcome to Semantica](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/introduction/01_Welcome_to_Semantica.ipynb)**: Comprehensive introduction to all Semantica modules
  - **Topics**: Framework overview, all modules, architecture
  - **Difficulty**: Beginner
  - **Use Cases**: First-time users, understanding the framework

- **[Your First Knowledge Graph](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/introduction/08_Your_First_Knowledge_Graph.ipynb)**: Build your first knowledge graph from scratch
  - **Topics**: Entity extraction, relationship extraction, graph construction
  - **Difficulty**: Beginner
  - **Use Cases**: Learning the basics, quick start

- **[GraphRAG Complete](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/use_cases/advanced_rag/01_GraphRAG_Complete.ipynb)**: Production-ready Graph Retrieval Augmented Generation
  - **Topics**: GraphRAG, hybrid retrieval, vector search, graph traversal
  - **Difficulty**: Advanced
  - **Use Cases**: Building AI applications with knowledge graphs

