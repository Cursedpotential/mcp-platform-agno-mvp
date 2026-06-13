# Core Concepts

**Learn the fundamental concepts behind Semantica in simple, practical terms.**

!!! tip "Quick Start"
    New to Semantica? Start with [Getting Started](getting-started.md) for hands-on examples.

---

## What is Semantica?

Semantica transforms unstructured data (documents, web pages, reports) into **knowledge graphs** - structured databases that AI systems can understand and reason about.

**What it does:**
- **Reads** documents, PDFs, web pages, databases
- **Extracts** entities (people, companies, dates) and relationships
- **Builds** connected knowledge graphs
- **Enables** AI to reason with structured knowledge

---

## Core Architecture

Semantica uses a **layered architecture** - use only what you need:

<div class="grid cards" markdown>

-   **Input Layer**
    
    ---
    
    Data ingestion and preparation
    
    **Modules**: Ingest, Parse, Split, Normalize

-   **Semantic Layer**
    
    ---
    
    Intelligence and understanding
    
    **Modules**: Semantic Extract, Knowledge Graph, Ontology, Reasoning

-   **Storage Layer**
    
    ---
    
    Persistent data storage
    
    **Modules**: Embeddings, Vector Store, Graph Store

-   **Quality Layer**
    
    ---
    
    Data quality and consistency
    
    **Modules**: Deduplication, Conflicts

-   **Context & Memory**
    
    ---
    
    Agent memory and foundation data
    
    **Modules**: Context, Seed, LLM Providers

-   **Output & Orchestration**
    
    ---
    
    Export, visualization, and workflows
    
    **Modules**: Export, Visualization, Pipeline

</div>

---

## Knowledge Graphs

The foundation of Semantica - turning data into structured knowledge.

### What is a Knowledge Graph?

A knowledge graph represents real-world information as:
- **Nodes** (entities): People, companies, locations, dates
- **Edges** (relationships): works_for, located_in, founded_by
- **Properties**: Name, date, confidence score, source

### Why Knowledge Graphs?

- **Searchable**: Find information instantly
- **Connectable**: Discover hidden relationships
- **Queryable**: Ask complex questions
- **Explainable**: Trace answers back to sources

---

## Entity Extraction (NER)

Finding and classifying entities in text.

### What it does:
- Scans text for people, organizations, locations, dates
- Classifies each entity by type
- Assigns confidence scores
- Tracks source provenance

### Example Output:
```python
# From: "Apple Inc. was founded by Steve Jobs in 1976 in Cupertino."
{
    "entities": [
        {"text": "Apple Inc.", "type": "ORGANIZATION", "confidence": 0.98},
        {"text": "Steve Jobs", "type": "PERSON", "confidence": 0.99},
        {"text": "1976", "type": "DATE", "confidence": 0.95},
        {"text": "Cupertino", "type": "LOCATION", "confidence": 0.97}
    ]
}
```

---

## Relationship Extraction

Finding connections between entities.

### What it does:
- Identifies how entities relate to each other
- Extracts relationship types and directions
- Provides context and confidence
- Links to source documents

### Example Output:
```python
{
    "relationships": [
        {"subject": "Steve Jobs", "predicate": "founded", "object": "Apple Inc.", "confidence": 0.92},
        {"subject": "Apple Inc.", "predicate": "located_in", "object": "Cupertino", "confidence": 0.89}
    ]
}
```

---

## Embeddings

Turning text into numerical vectors for AI understanding.

### What are embeddings?
- **Numerical representations** of text, entities, and relationships
- **Similarity calculations** - find related concepts
- **AI-powered search** - semantic understanding
- **Clustering and grouping** - discover patterns

### Use Cases:
- **Semantic Search** - find documents by meaning, not keywords
- **Entity Resolution** - match similar entities across sources
- **Recommendations** - suggest related content
- **AI Input** - provide structured context to LLMs

---

## Temporal Graphs

Knowledge graphs that understand time.

### What they track:
- **When** events happened
- **How** entities changed over time
- **Temporal relationships** - before, after, during
- **Historical context** - point-in-time snapshots

### Example Uses:
- **Company History** - track mergers, leadership changes
- **Person Careers** - job changes, relocations
- **Policy Evolution** - law changes over time
- **Research Progress** - scientific discoveries timeline

---

## GraphRAG

Enhanced AI retrieval using knowledge graphs.

### How it works:
1. **Query** user question
2. **Retrieve** relevant graph context
3. **Enhance** with relationships and entities
4. **Generate** AI response with sources

### Benefits:
- **More accurate** answers
- **Source attribution** - trace answers back
- **Context awareness** - understand relationships
- **Reduced hallucination** - grounded in facts

---

## Ontology

Defining the structure and rules of your knowledge.

### What it provides:
- **Schema definition** - what types exist
- **Relationship rules** - valid connections
- **Property constraints** - required fields
- **Inheritance hierarchies** - parent-child relationships

### Example:
```python
# Define ontology structure
ontology = {
    "classes": ["Person", "Organization", "Location"],
    "properties": ["name", "date", "confidence"],
    "relationships": ["works_for", "located_in", "born_in"],
    "rules": {
        "Person": ["must_have_name", "can_have_birth_date"],
        "Organization": ["must_have_name", "can_have_founding_date"]
    }
}
```

---

## Reasoning & Inference

Making logical deductions from your knowledge.

### What it can do:
- **Infer missing facts** - derive new knowledge
- **Detect inconsistencies** - find contradictions
- **Apply rules** - automate decision making
- **Explain reasoning** - show how conclusions were reached

### Example:
```
Known: Steve Jobs founded Apple Inc.
Known: Apple Inc. is headquartered in Cupertino
Inferred: Steve Jobs has connection to Cupertino
```

---

## Deduplication & Entity Resolution

Finding and merging duplicate entities.

### What it does:
- **Detects duplicates** - same entity, different names
- **Merges information** - combine attributes
- **Resolves conflicts** - handle contradictory data
- **Maintains provenance** - track original sources

### Example:
```python
# These refer to the same entity:
"Apple Inc." â†’ "Apple" â†’ "Apple Computer Inc."
# Merge into single entity with all attributes
```

---

## Data Normalization

Cleaning and standardizing your data.

### What it fixes:
- **Format inconsistencies** - dates, names, numbers
- **Canonical forms** - standard representations
- **Data quality** - remove errors and noise
- **Standardization** - consistent naming conventions

### Examples:
- **Dates**: "Jan 1, 2020" â†’ "2020-01-01"
- **Names**: "Dr. Smith PhD" â†’ "John Smith"
- **Companies**: "Apple" â†’ "Apple Inc."
- **Locations**: "NYC" â†’ "New York City"

---

## Conflict Detection

Finding and resolving contradictory information.

### What it identifies:
- **Factual conflicts** - different values for same fact
- **Temporal conflicts** - impossible timelines
- **Logical conflicts** - contradictory relationships
- **Source reliability** - trustworthiness assessment

### Resolution Strategies:
- **Most recent** - prefer newer information
- **Most reliable** - prefer trusted sources
- **Majority vote** - go with consensus
- **Manual review** - flag for human review

---

## Getting Started

Ready to build your first knowledge graph?

### Quick Start (5 minutes)
```python
from semantica.semantic_extract import NERExtractor
from semantica.kg import GraphBuilder

# Extract entities
ner = NERExtractor()
entities = ner.extract("Apple Inc. was founded by Steve Jobs in 1976.")

# Build graph
kg = GraphBuilder().build({"entities": entities, "relationships": []})
```

### Learn More
- **Getting Started Guide** - [Getting Started](getting-started.md)
- **Cookbook Examples** - [Cookbook](cookbook.md)
- **Module Documentation** - [Reference](reference/)
- **Community Support** - [Community](community.md)

### Common Use Cases
- **Document Analysis** - extract knowledge from reports
- **Research Assistant** - find connections in academic papers
- **Business Intelligence** - analyze company relationships
- **Regulatory Compliance** - track policy changes

---

## Best Practices

### Start Small
- Begin with a single document type
- Focus on specific entity types
- Validate results before scaling

### Configure Properly
- Choose appropriate models for your domain
- Set confidence thresholds
- Define clear ontology rules

### Validate Data
- Check extraction quality
- Review relationship accuracy
- Test with known examples

### Handle Errors
- Implement error handling
- Log processing issues
- Provide feedback mechanisms

### Optimize Performance
- Use appropriate storage backends
- Cache frequently accessed data
- Monitor resource usage

### Document Workflows
- Record processing steps
- Track data sources
- Maintain change logs

---

## Need Help?

- **Documentation**: [Getting Started](getting-started.md)
- **Examples**: [Cookbook](cookbook.md)
- **Community**: [Discord](community.md)
- **Issues**: [GitHub Issues](https://github.com/Hawksight-AI/semantica/issues)
- **Support**: [Contact Us](community.md)
