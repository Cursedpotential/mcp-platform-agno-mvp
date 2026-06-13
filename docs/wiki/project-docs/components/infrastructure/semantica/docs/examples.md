# Examples

Real-world examples and use cases for Semantica.

!!! tip "Interactive Learning"
    For hands-on interactive tutorials, check out our [Cookbook](cookbook.md) with Jupyter notebooks covering everything from basics to advanced use cases.

---

## Example Gallery

<div class="grid cards" markdown>

-   :material-school: **Getting Started**
    ---
    Quick examples to get you up and running in 5 minutes.
    
    [View Examples](#getting-started-5-min-examples)

-   :material-cogs: **Core Workflows**
    ---
    Common workflows for building production-ready graphs.
    
    [View Examples](#core-workflows-15-min-examples)

-   :material-rocket: **Advanced Patterns**
    ---
    Complex use cases and production deployments.
    
    [View Examples](#advanced-patterns-30-min-examples)

-   :material-factory: **Production Patterns**
    ---
    Scalable deployment patterns for enterprise use.
    
    [View Examples](#production-patterns)

</div>

---

## Getting Started (5 min examples)

### Example 1: Basic Knowledge Graph

**Difficulty**: Beginner

Build a knowledge graph from a single document using Semantica's modular approach. This example demonstrates the complete workflow from document ingestion to graph construction.

**What it demonstrates:**
- Document ingestion and parsing
- Entity and relationship extraction
- Knowledge graph construction

**For complete step-by-step examples, see:**
- **[Your First Knowledge Graph Cookbook](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/introduction/08_Your_First_Knowledge_Graph.ipynb)**: Complete walkthrough
  - **Topics**: Ingestion, parsing, extraction, graph building
  - **Difficulty**: Beginner
  - **Time**: 20-30 minutes
  - **Use Cases**: Learning the complete workflow

### Example 2: Entity Extraction

**Difficulty**: Beginner

Extract entities from text using Named Entity Recognition. This example shows how to identify and classify named entities in text.

**What it demonstrates:**
- Named Entity Recognition (NER)
- Entity type classification
- Confidence scoring

**For complete examples, see:**
- **[Entity Extraction Cookbook](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/introduction/05_Entity_Extraction.ipynb)**: Learn entity extraction
  - **Topics**: NER methods, entity types, extraction techniques
  - **Difficulty**: Beginner
  - **Time**: 15-20 minutes
  - **Use Cases**: Understanding entity extraction
    print(f"{entity.text}: {entity.label}")
```

**Expected Output:**
```
Apple Inc.: ORGANIZATION
Steve Jobs: PERSON
```

### Example 3: Multi-Source Integration

**Difficulty**: Beginner

Combine data from multiple sources into a unified knowledge graph. This example demonstrates integrating data from diverse sources.

**What it demonstrates:**
- Multi-source data ingestion
- Entity merging and resolution
- Unified graph construction

**For complete examples, see:**
- **[Multi-Source Data Integration Cookbook](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/advanced/06_Multi_Source_Data_Integration.ipynb)**: Advanced integration patterns
  - **Topics**: Multi-source integration, entity resolution, conflict handling
  - **Difficulty**: Intermediate
  - **Time**: 30-45 minutes
  - **Use Cases**: Building unified knowledge graphs from diverse sources

---

## Core Workflows (15 min examples)

### Example 4: Conflict Resolution

**Difficulty**: Intermediate

Resolve conflicts in data from multiple sources. This example shows how to identify and resolve conflicting information.

**What it demonstrates:**
- Conflict detection
- Conflict resolution strategies
- Data quality assurance

**For complete examples, see:**
- **[Multi-Source Data Integration Cookbook](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/advanced/06_Multi_Source_Data_Integration.ipynb)**: Conflict resolution patterns
  - **Topics**: Conflict detection, resolution strategies, data quality
  - **Difficulty**: Intermediate
  - **Time**: 30-45 minutes
  - **Use Cases**: Data integration, quality assurance
ingestor = FileIngestor()
parser = DocumentParser()
ner = NERExtractor()

all_entities = []
for source in ["source1.pdf", "source2.pdf"]:
    doc = ingestor.ingest_file(source)
    parsed = parser.parse_document(source)
    text = parsed.get("full_text", "")
    entities = ner.extract_entities(text)
    all_entities.extend(entities)

# Detect and resolve conflicts
detector = ConflictDetector()
conflicts = detector.detect_conflicts(all_entities)

resolver = ConflictResolver(default_strategy="voting")
resolved = resolver.resolve_conflicts(conflicts)

print(f"Detected {len(conflicts)} conflicts")
print(f"Resolved {len(resolved)} conflicts")
```

### Example 5: Custom Entity Extraction Configuration

**Difficulty**: Intermediate

Use custom configuration for entity extraction with specific models and thresholds.

```python
from semantica.semantic_extract import NERExtractor
from semantica.kg import GraphBuilder

# Use LLM-based extraction with custom configuration
ner = NERExtractor(
    method="llm",
    provider="openai",
    model="gpt-4",
    confidence_threshold=0.8,
    temperature=0.0
)

text = "Your document text here..."
entities = ner.extract_entities(text)

# Build graph with custom merge settings
builder = GraphBuilder(
    merge_entities=True,
    merge_threshold=0.9
)
kg = builder.build_graph(entities=entities, relationships=[])
```

### Example 6: Incremental Graph Building

**Difficulty**: Intermediate

Build knowledge graph incrementally from multiple sources.

```python
from semantica.ingest import FileIngestor
from semantica.parse import DocumentParser
from semantica.semantic_extract import NERExtractor, RelationExtractor
from semantica.kg import GraphBuilder, GraphMerger

def build_kg_from_source(source_path):
    """Helper function to build a knowledge graph from a single source."""
    ingestor = FileIngestor()
    parser = DocumentParser()
    ner = NERExtractor()
    rel_extractor = RelationExtractor()
    
    doc = ingestor.ingest_file(source_path)
    parsed = parser.parse_document(source_path)
    text = parsed.get("full_text", "")
    
    entities = ner.extract_entities(text)
    relationships = rel_extractor.extract_relations(text, entities=entities)
    
    builder = GraphBuilder()
    return builder.build_graph(entities=entities, relationships=relationships)

# Build graphs separately
kg1 = build_kg_from_source("source1.pdf")
kg2 = build_kg_from_source("source2.pdf")

# Merge into unified graph
merger = GraphMerger()
merged_kg = merger.merge([kg1, kg2])

print(f"Merged graph: {len(merged_kg.nodes)} nodes, {len(merged_kg.edges)} edges")
```

---

## Advanced Patterns (30+ min examples)

### Example 7: Graph Visualization

**Difficulty**: Beginner

Visualize your knowledge graph to understand entity relationships.

```python
from semantica.ingest import FileIngestor
from semantica.parse import DocumentParser
from semantica.semantic_extract import NERExtractor, RelationExtractor
from semantica.kg import GraphBuilder
from semantica.visualization import KGVisualizer

# Build a small graph
ingestor = FileIngestor()
parser = DocumentParser()
ner = NERExtractor()
rel_extractor = RelationExtractor()

doc = ingestor.ingest_file("semantica_intro.pdf")
parsed = parser.parse_document("semantica_intro.pdf")
text = parsed.get("full_text", "")

entities = ner.extract_entities(text)
relationships = rel_extractor.extract_relations(text, entities=entities)

builder = GraphBuilder()
kg = builder.build_graph(entities=entities, relationships=relationships)

# Visualize
viz = KGVisualizer()
viz.visualize_network(kg, output="html", file_path="semantica_knowledge_map.html")
print("Visualization saved to semantica_knowledge_map.html")
```

---

## Advanced Patterns (30+ min examples)

### Example 8: Persistent Storage (Neo4j)

**Difficulty**: Intermediate

Store and query knowledge graphs in a persistent graph database.

```python
from semantica.graph_store import GraphStore

# Initialize with Neo4j
store = GraphStore(
    backend="neo4j",
    uri="bolt://localhost:7687",
    user="neo4j",
    password="password"
)
store.connect()

# Create nodes and relationships
apple = store.create_node(
    labels=["Company"],
    properties={"name": "Apple Inc."}
)
tim = store.create_node(
    labels=["Person"],
    properties={"name": "Tim Cook"}
)
store.create_relationship(
    start_node_id=tim["id"],
    end_node_id=apple["id"],
    rel_type="CEO_OF"
)

store.close()
```

### Example 9: FalkorDB for Real-Time Applications

**Difficulty**: Intermediate

Ultra-fast graph queries for LLM applications using FalkorDB.

```python
from semantica.graph_store import GraphStore

store = GraphStore(
    backend="falkordb",
    host="localhost",
    port=6379,
    graph_name="knowledge_graph"
)
store.connect()

# Fast queries
results = store.execute_query("MATCH (n)-[r]->(m) WHERE n.name CONTAINS 'AI' RETURN n")
store.close()
```

### Example 10: GraphRAG (Knowledge-Powered Retrieval)

**Difficulty**: Advanced

Build a production-ready GraphRAG system with logical inference and hybrid retrieval.

```python
from semantica.context import AgentContext
from semantica.reasoning import Reasoner

# 1. Initialize context with GraphRAG (Hybrid Retrieval)
context = AgentContext(
    vector_store=vs, 
    knowledge_graph=kg,
    graph_expansion=True,
    hybrid_alpha=0.7
)

# 2. Enrich Knowledge Graph using Logical Reasoning
reasoner = Reasoner()

# Add a rule to categorize technology stack items
reasoner.add_rule("IF Library(?x) AND Language(?y) THEN TechStackItem(?x)")

# Infer new facts from the existing graph
all_facts = kg.get_all_triplets()
inferred = reasoner.infer_facts(all_facts)

# Add inferred knowledge back to the graph
for fact_str in inferred:
    kg.add_fact_from_string(fact_str)

# 3. Retrieve context for a query (now with enriched knowledge)
results = context.retrieve("What technologies are used in this project?")
```

[**View Complete GraphRAG Tutorial**](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/use_cases/advanced_rag/01_GraphRAG_Complete.ipynb)

### Example 11: RAG vs. GraphRAG Comparison

**Difficulty**: Intermediate

Benchmark standard Vector RAG against Graph-enhanced retrieval.

[**View RAG vs. GraphRAG Comparison**](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/use_cases/advanced_rag/02_RAG_vs_GraphRAG_Comparison.ipynb)

---

## Production Patterns

### Example 12: Streaming Data Processing

**Difficulty**: Advanced

Process data streams in real-time.

```python
from semantica.ingest import StreamIngestor
from semantica.parse import DocumentParser
from semantica.semantic_extract import NERExtractor, RelationExtractor
from semantica.kg import GraphBuilder

stream_ingestor = StreamIngestor(stream_uri="kafka://localhost:9092/topic")
parser = DocumentParser()
ner = NERExtractor()
rel_extractor = RelationExtractor()
builder = GraphBuilder()

for batch in stream_ingestor.stream(batch_size=100):
    all_entities = []
    all_relationships = []
    
    for item in batch:
        text = str(item)  # Convert stream item to text
        entities = ner.extract_entities(text)
        relationships = rel_extractor.extract_relations(text, entities=entities)
        all_entities.extend(entities)
        all_relationships.extend(relationships)
    
    # Build graph from batch
    kg = builder.build_graph(entities=all_entities, relationships=all_relationships)
    # Process results
    print(f"Processed batch: {len(kg.nodes)} nodes")
```

### Example 13: Batch Processing Large Datasets

**Difficulty**: Intermediate

Process large datasets efficiently with batching.

```python
from semantica.ingest import FileIngestor
from semantica.parse import DocumentParser
from semantica.semantic_extract import NERExtractor, RelationExtractor
from semantica.kg import GraphBuilder

ingestor = FileIngestor()
parser = DocumentParser()
ner = NERExtractor()
rel_extractor = RelationExtractor()
builder = GraphBuilder()

sources = [f"data/doc_{i}.pdf" for i in range(1000)]
batch_size = 50

for i in range(0, len(sources), batch_size):
    batch = sources[i:i+batch_size]
    
    all_entities = []
    all_relationships = []
    
    for source in batch:
        doc = ingestor.ingest_file(source)
        parsed = parser.parse_document(source)
        text = parsed.get("full_text", "")
        
        entities = ner.extract_entities(text)
        relationships = rel_extractor.extract_relations(text, entities=entities)
        
        all_entities.extend(entities)
        all_relationships.extend(relationships)
    
    # Build graph from batch
    kg = builder.build_graph(entities=all_entities, relationships=all_relationships)
    
    # Save intermediate results
    print(f"Processed batch {i//batch_size + 1}: {len(kg.nodes)} nodes")
```

---

## More Resources

- **[Quick Start Guide](quickstart.md)** - Step-by-step tutorial
- **[API Reference](reference/core.md)** - Complete API documentation
- **[Cookbook](cookbook.md)** - Interactive Jupyter notebooks
- **[Use Cases](use-cases.md)** - Real-world applications

### 🍳 Recommended Cookbook Tutorials

- **[Welcome to Semantica](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/introduction/01_Welcome_to_Semantica.ipynb)**: Comprehensive introduction to all modules
  - **Topics**: Framework overview, all modules, architecture, configuration
  - **Difficulty**: Beginner
  - **Time**: 30-45 minutes
  - **Use Cases**: First-time users, understanding the framework

- **[Your First Knowledge Graph](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/introduction/08_Your_First_Knowledge_Graph.ipynb)**: Build your first knowledge graph
  - **Topics**: Entity extraction, relationship extraction, graph construction, visualization
  - **Difficulty**: Beginner
  - **Time**: 20-30 minutes
  - **Use Cases**: Learning the basics, quick start

- **[GraphRAG Complete](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/use_cases/advanced_rag/01_GraphRAG_Complete.ipynb)**: Production-ready GraphRAG system
  - **Topics**: GraphRAG, hybrid retrieval, vector search, graph traversal, LLM integration
  - **Difficulty**: Advanced
  - **Time**: 1-2 hours
  - **Use Cases**: Production RAG applications

- **[RAG vs. GraphRAG Comparison](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/use_cases/advanced_rag/02_RAG_vs_GraphRAG_Comparison.ipynb)**: Benchmark standard RAG vs GraphRAG
  - **Topics**: RAG, GraphRAG, benchmarking, visualization, reasoning gap
  - **Difficulty**: Intermediate
  - **Time**: 45-60 minutes
  - **Use Cases**: Understanding GraphRAG advantages, choosing the right approach

---

!!! info "Contribute"
    Have an example to share? [Contribute on GitHub](https://github.com/Hawksight-AI/semantica)

