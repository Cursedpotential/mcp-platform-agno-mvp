# Deduplication & Conflict Resolution Strategies Summary

## Quick Reference by Use Case

| Use Case | Deduplication Method | Merge Strategy | Conflict Detection | Conflict Resolution |
|----------|---------------------|----------------|-------------------|---------------------|
| **Finance** |
| `01_Financial_Data_Integration_MCP` | `DuplicateDetector` (incremental) | `keep_highest_confidence` | `temporal` | `most_recent` |
| `02_Fraud_Detection` | `ClusterBuilder` (graph_based) | `merge_all` | `logical` | `expert_review` |
| **Biomedical** |
| `01_Drug_Discovery_Pipeline` | `EntityResolver` (semantic) | - | `relationship` | `voting` |
| `02_Genomic_Variant_Analysis` | `DuplicateDetector` (group) | `keep_most_complete` | `value` | `credibility_weighted` |
| **Cybersecurity** |
| `01_Real_Time_Anomaly_Detection` | `DuplicateDetector` (pairwise) | `keep_first` | `entity` | `first_seen` |
| `02_Threat_Intelligence_Hybrid_RAG` | `EntityResolver` (exact) | - | `type` | `highest_confidence` |
| **Blockchain** |
| `01_DeFi_Protocol_Intelligence` | `DuplicateDetector` (group) | `keep_last` | `relationship` | `voting` |
| `02_Transaction_Network_Analysis` | `ClusterBuilder` (hierarchical) | `keep_most_complete` | `temporal` | `most_recent` |
| **Intelligence** |
| `01_Criminal_Network_Analysis` | `EntityResolver` (fuzzy) | - | `value` | `credibility_weighted` |
| `02_Intelligence_Analysis_Orchestrator_Worker` | `DuplicateDetector` (batch) | `merge_all` | `entity` | `voting` |
| **Renewable Energy** |
| `01_Energy_Market_Analysis` | `DuplicateDetector` (pairwise) | `keep_highest_confidence` | `temporal` | `most_recent` |
| **Supply Chain** |
| `01_Supply_Chain_Data_Integration` | `DuplicateDetector` (incremental) | `keep_most_complete` | `value` | `credibility_weighted` |

---

## Strategy Rationale by Domain

### Finance
- **Financial Data Integration**: Incremental for streaming data; most_recent for time-sensitive financial data
- **Fraud Detection**: Graph-based clustering for fraud groups; expert_review for fraud assessment

### Biomedical
- **Drug Discovery**: Semantic matching for drug compounds; voting for research source aggregation
- **Genomic Variants**: Group method for related variants; credibility weighting for research sources

### Cybersecurity
- **Real-Time Anomaly**: Pairwise for real-time streams; keep_first for first detection priority
- **Threat Intelligence**: Exact matching for IOCs; highest_confidence for threat classification

### Blockchain
- **DeFi Protocols**: Group method for related protocols; keep_last for latest protocol info
- **Transaction Networks**: Hierarchical clustering for nested groups; temporal for time-sensitive data

### Intelligence
- **Criminal Networks**: Fuzzy matching for intelligence data; credibility weighting for intelligence sources
- **Intelligence Analysis**: Batch for multi-source integration; merge_all to combine all intelligence sources

### Renewable Energy
- **Energy Markets**: Pairwise for real-time market data; most_recent for time-sensitive energy data

### Supply Chain
- **Supply Chain Integration**: Incremental for continuous updates; credibility weighting for supply chain sources

---

## Method Distribution

### Deduplication Methods (9 total)
- `pairwise`: 2 notebooks (real-time processing)
- `batch`: 3 notebooks (large datasets)
- `incremental`: 2 notebooks (streaming/continuous)
- `group`: 2 notebooks (related entities)
- `graph_based` (ClusterBuilder): 2 notebooks (interconnected entities)
- `hierarchical` (ClusterBuilder): 1 notebook (nested groups)
- `exact` (EntityResolver): 1 notebook (exact matching)
- `semantic` (EntityResolver): 2 notebooks (semantic similarity)
- `fuzzy` (EntityResolver): 1 notebook (fuzzy matching)

### Merge Strategies (5 total)
- `keep_first`: 1 notebook (first detection priority)
- `keep_last`: 1 notebook (latest information)
- `keep_most_complete`: 5 notebooks (preserve all details)
- `keep_highest_confidence`: 2 notebooks (most reliable data)
- `merge_all`: 3 notebooks (combine all information)

### Conflict Detection Methods (6 total)
- `value`: 4 notebooks (property value conflicts)
- `type`: 2 notebooks (type/classification conflicts)
- `entity`: 2 notebooks (entity-wide conflicts)
- `relationship`: 3 notebooks (relationship conflicts)
- `temporal`: 3 notebooks (time-sensitive conflicts)
- `logical`: 2 notebooks (logical inconsistencies)

### Conflict Resolution Strategies (6 total)
- `voting`: 5 notebooks (majority vote)
- `credibility_weighted`: 4 notebooks (source credibility)
- `most_recent`: 3 notebooks (latest data)
- `first_seen`: 1 notebook (first detection)
- `highest_confidence`: 2 notebooks (most confident)
- `expert_review`: 1 notebook (manual review)

---

## Key Patterns

1. **Real-Time Systems**: Use `pairwise` + `keep_first` + `first_seen`
2. **Time-Sensitive Data**: Use `temporal` + `most_recent`
3. **Multi-Source Integration**: Use `batch` + `merge_all` + `voting`
4. **Medical/Research**: Use `credibility_weighted` for authoritative sources
5. **Fraud/Security**: Use `graph_based` + `logical` + `expert_review`
6. **Exact Matching Required**: Use `exact` strategy (IOCs, identifiers)

