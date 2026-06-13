# Use Cases

Semantica is designed to solve complex data challenges across various domains. This guide explores common use cases and how to implement them.

!!! info "About This Guide"
    This guide provides detailed implementation guides for real-world use cases, complete with code examples, prerequisites, and step-by-step instructions.

---

## Use Case Comparison

| Use Case                          | Difficulty    | Time        | Domain      | Key Features                                    | Cookbook                                    |
| :-------------------------------- | :------------ | :---------- | :---------- | :---------------------------------------------- | :------------------------------------------ |
| **Biomedical Knowledge Graphs**  | Intermediate  | 1-2 hours   | Healthcare  | Gene-protein-disease relationships              | Drug Discovery, Genomic Variant Analysis   |
| **Financial Data Integration**   | Intermediate  | 1-2 hours   | Finance     | MCP integration, real-time data                 | Financial Data Integration MCP             |
| **Fraud Detection**              | Advanced      | 2-3 hours   | Finance     | Temporal graphs, pattern detection              | Fraud Detection                            |
| **Blockchain Analytics**         | Intermediate  | 1-2 hours   | Finance     | Transaction tracing, DeFi intelligence         | DeFi Protocol Intelligence, Transaction Network |
| **Cybersecurity Threat Intelligence**| Advanced   | 2-3 hours   | Security    | Threat mapping, anomaly detection               | Real-Time Anomaly Detection, Threat Intelligence |
| **Intelligence Analysis**        | Intermediate  | 1-2 hours   | Security    | Criminal networks, OSINT analysis               | Criminal Network Analysis, Intelligence Orchestrator |
| **Supply Chain Optimization**    | Intermediate  | 1-2 hours   | Industry    | Data integration, route optimization            | Supply Chain Data Integration               |
| **Renewable Energy Management**  | Intermediate  | 1-2 hours   | Energy      | Energy market analysis, optimization             | Energy Market Analysis                     |
| **GraphRAG**                      | Advanced      | 1-2 hours   | AI          | Enhanced RAG with knowledge graphs              | GraphRAG Complete, RAG vs GraphRAG         |

**Difficulty Levels**:
- **Beginner**: Basic Semantica knowledge required
- **Intermediate**: Some domain knowledge helpful
- **Advanced**: Requires domain expertise and advanced Semantica features

---

## Research & Science

<div class="grid cards" markdown>

-   :material-dna: **Biomedical Knowledge Graphs**
    ---
    Accelerate drug discovery and understand disease pathways by connecting genes, proteins, drugs, and diseases.
    
    **Goal**: Connect genes, proteins, drugs, and diseases from scientific literature and databases.
    
    **Difficulty**: Intermediate
    
    [:material-arrow-right: Drug Discovery Pipeline](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/use_cases/biomedical/01_Drug_Discovery_Pipeline.ipynb)
    
    [:material-arrow-right: Genomic Variant Analysis](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/use_cases/biomedical/02_Genomic_Variant_Analysis.ipynb)

</div>

### Biomedical Knowledge Graphs Implementation

**Prerequisites**:
- Domain knowledge of biomedical concepts
- Access to biomedical literature/databases

**Implementation Guides:**

- **[Drug Discovery Pipeline Cookbook](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/use_cases/biomedical/01_Drug_Discovery_Pipeline.ipynb)**: Build knowledge graphs from PubMed RSS feeds
  - **Topics**: PubMed RSS ingestion, entity-aware chunking, GraphRAG, vector similarity search
  - **Difficulty**: Intermediate
  - **Time**: 1-2 hours
  - **Use Cases**: Drug discovery, biomedical research

- **[Genomic Variant Analysis Cookbook](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/use_cases/biomedical/02_Genomic_Variant_Analysis.ipynb)**: Analyze genomic variants using temporal knowledge graphs
  - **Topics**: bioRxiv RSS, temporal KGs, deduplication, pathway analysis
  - **Difficulty**: Intermediate
  - **Time**: 1-2 hours
  - **Use Cases**: Genomic research, variant analysis

---

## Finance & Trading

<div class="grid cards" markdown>

-   :material-finance: **Financial Data Integration**
    ---
    Integrate financial data from multiple sources using MCP servers and real-time ingestion.
    
    **Goal**: Connect Alpha Vantage API, MCP servers, seed data, and real-time ingestion for comprehensive financial analysis.
    
    [:material-arrow-right: View Cookbook](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/use_cases/finance/01_Financial_Data_Integration_MCP.ipynb)

-   :material-shield-alert: **Fraud Detection**
    ---
    Detect complex fraud rings using temporal knowledge graphs and pattern detection.
    
    **Goal**: Build a graph of Users, Devices, IP Addresses, and Transactions to find cycles and detect fraud patterns.
    
    [:material-arrow-right: View Cookbook](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/use_cases/finance/02_Fraud_Detection.ipynb)

-   :material-bitcoin: **Blockchain Analytics**
    ---
    Analyze DeFi protocols and transaction networks for intelligence and fraud detection.
    
    **Goal**: Map transaction flows between wallets and exchanges, analyze DeFi protocols, and detect illicit activity.
    
    [:material-arrow-right: DeFi Protocol Intelligence](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/use_cases/blockchain/01_DeFi_Protocol_Intelligence.ipynb)
    
    [:material-arrow-right: Transaction Network Analysis](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/use_cases/blockchain/02_Transaction_Network_Analysis.ipynb)

</div>

---


---

## Security & Intelligence

<div class="grid cards" markdown>

-   :material-shield-lock: **Cybersecurity Threat Intelligence**
    ---
    Proactively identify and mitigate cyber threats using real-time anomaly detection and threat intelligence.
    
    **Goal**: Ingest threat feeds (CVE databases, security RSS), detect anomalies in streaming data, and build threat intelligence knowledge graphs.
    
    [:material-arrow-right: Real-Time Anomaly Detection](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/use_cases/cybersecurity/01_Real_Time_Anomaly_Detection.ipynb)
    
    [:material-arrow-right: Threat Intelligence Hybrid RAG](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/use_cases/cybersecurity/02_Threat_Intelligence_Hybrid_RAG.ipynb)

-   :material-account-network: **Criminal Network Analysis**
    ---
    Analyze criminal networks to identify key players, communities, and suspicious patterns using OSINT RSS feeds, deduplication, and network centrality analysis.
    
    **Goal**: Build knowledge graphs from police reports, court records, and surveillance data.
    
    [:material-arrow-right: View Cookbook](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/use_cases/intelligence/01_Criminal_Network_Analysis.ipynb)

-   :material-file-search: **Intelligence Analysis Orchestrator Worker**
    ---
    Comprehensive intelligence analysis using pipeline orchestrator with multiple RSS feeds, conflict detection, and multi-source integration.
    
    **Goal**: Process multiple intelligence sources in parallel using orchestrator-worker pattern.
    
    [:material-arrow-right: View Cookbook](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/use_cases/intelligence/02_Intelligence_Analysis_Orchestrator_Worker.ipynb)

</div>

---

## Industry & Operations

<div class="grid cards" markdown>

-   :material-truck-delivery: **Supply Chain Optimization**
    ---
    Visualize and optimize complex global supply chains.
    
    **Goal**: Map suppliers, logistics routes, and inventory levels to identify bottlenecks.
    
    [:material-arrow-right: View Cookbook](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/use_cases/supply_chain/01_Supply_Chain_Data_Integration.ipynb)

-   :material-wind-turbine: **Renewable Energy Management**
    ---
    Optimize grid operations and asset maintenance.
    
    **Goal**: Connect sensor data, weather forecasts, and maintenance logs to predict failures.
    
    [:material-arrow-right: View Cookbook](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/use_cases/renewable_energy/01_Energy_Market_Analysis.ipynb)

</div>

---

## Advanced AI Patterns

<div class="grid cards" markdown>

-   :material-robot: **Graph-Augmented Generation (GraphRAG)**
    ---
    Enhance LLM responses with structured ground truth using knowledge graphs.
    
    **Goal**: Use the knowledge graph to retrieve precise context for RAG applications with hybrid retrieval and logical inference.
    
    [:material-arrow-right: GraphRAG Complete](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/use_cases/advanced_rag/01_GraphRAG_Complete.ipynb)
    
    [:material-scale-balance: RAG vs GraphRAG Comparison](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/use_cases/advanced_rag/02_RAG_vs_GraphRAG_Comparison.ipynb)

</div>

---


---

## Summary

This guide covered use cases across multiple domains with corresponding cookbooks:

- **Research & Science**: Biomedical knowledge graphs (Drug Discovery, Genomic Variant Analysis)
- **Finance & Trading**: Financial data integration, fraud detection, blockchain analytics
- **Security & Intelligence**: Cybersecurity threat intelligence, criminal network analysis, intelligence orchestration
- **Industry**: Supply chain optimization, renewable energy management
- **AI Applications**: GraphRAG (Complete implementation and comparison)

---

## Next Steps

- **[Examples](examples.md)** - More detailed code examples
- **[Modules Guide](modules.md)** - Learn about available modules
- **[Cookbook](cookbook.md)** - Interactive Jupyter notebooks
- **[API Reference](reference/core.md)** - Complete API documentation

---

!!! info "Contribute"
    Have a use case to add? [Contribute on GitHub](https://github.com/Hawksight-AI/semantica)

