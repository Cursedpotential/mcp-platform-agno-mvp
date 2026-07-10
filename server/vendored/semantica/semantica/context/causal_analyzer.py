"""
Causal Chain Analyzer

Analyzes decision causality, influence chains, and precedent relationships using
graph traversal and advanced analytics.

Key Features:
    - Causal chain tracing (upstream/downstream)
    - Decision influence analysis and scoring
    - Precedent relationship mapping
    - Multi-directional causality analysis
    - Path finding and impact assessment

Decision Tracking Integration:
    - Complete decision lifecycle analysis
    - Decision influence and causality tracking
    - Decision relationship mapping
    - Decision metadata and context analysis
    - Decision analytics and statistics

KG Algorithm Integration:
    - Path Finding: Shortest path and advanced path algorithms
    - Centrality Analysis: Decision importance and influence scoring
    - Similarity Calculation: Decision similarity measures
    - Community Detection: Decision community analysis
    - Link Prediction: Predict causal relationships
    - Node Embeddings: Node2Vec embeddings for similarity analysis

Vector Store Integration:
    - Hybrid Search: Semantic + structural similarity
    - Custom Similarity Weights: Configurable scoring
    - Advanced Precedent Search: KG-enhanced similarity
    - Multi-Embedding Support: Multiple embedding types
    - Metadata Filtering: Advanced filtering capabilities
    - Policy Engine: Policy enforcement and compliance checking

Core Methods:
    - get_causal_chain(): Trace causal chains from decisions
    - find_influenced_decisions(): Find decisions influenced by a decision
    - find_influencing_decisions(): Find decisions that influenced a decision
    - analyze_causal_impact(): Analyze causal impact and scope
    - calculate_influence_score(): Calculate decision influence scores
    - find_precedents(): Find decision precedents with similarity

Example Usage:
    >>> from semantica.context import CausalChainAnalyzer
    >>> analyzer = CausalChainAnalyzer(graph_store=kg)
    >>> upstream = analyzer.get_causal_chain(decision_id, "upstream", max_depth=3)
    >>> downstream = analyzer.get_causal_chain(decision_id, "downstream", max_depth=3)
    >>> influenced = analyzer.find_influenced_decisions(decision_id)
    >>> influence_score = analyzer.calculate_influence_score(decision_id)
    >>> impact = analyzer.analyze_causal_impact(decision_id, max_depth=5)

Production Use Cases:
    - Banking: Trace loan approval decisions and their impacts
    - Healthcare: Analyze treatment decision cascades
    - Legal: Trace legal precedent influence chains
    - Manufacturing: Analyze production decision impacts
    - Policy: Trace policy decision consequences
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Set
from collections import deque

from ..graph_store import GraphStore
from ..utils.logging import get_logger
from .decision_models import Decision


class CausalChainAnalyzer:
    """
    Analyzes causal chains between decisions.
    
    This class provides methods for tracing decision causality, finding
    decisions that influenced others, and analyzing precedent relationships
    using graph traversal.
    """
    
    def __init__(self, graph_store: Any):
        """
        Initialize CausalChainAnalyzer.
        
        Args:
            graph_store: Graph database instance for traversal
        """
        self.graph_store = graph_store
        self.logger = get_logger(__name__)
    
    def get_causal_chain(
        self,
        decision_id: str,
        direction: str = "upstream",
        max_depth: int = 10
    ) -> List[Decision]:
        """
        Trace decision causality in specified direction.
        
        Args:
            decision_id: Starting decision ID
            direction: "upstream" (what caused this) or "downstream" (what this caused)
            max_depth: Maximum traversal depth
            
        Returns:
            List of decisions in causal chain
        """
        try:
            if hasattr(self.graph_store, "get_causal_chain") and not hasattr(self.graph_store, "execute_query"):
                return self.graph_store.get_causal_chain(
                    decision_id=decision_id,
                    direction=direction,
                    max_depth=max_depth
                )

            if direction not in ["upstream", "downstream"]:
                raise ValueError("Direction must be 'upstream' or 'downstream'")
            
            # Define relationship direction based on traversal direction
            if direction == "upstream":
                rel_pattern = "<-[:CAUSED|:INFLUENCED|:PRECEDENT_FOR]-"
            else:
                rel_pattern = "-[:CAUSED|:INFLUENCED|:PRECEDENT_FOR]->"
            
            query = f"""
            MATCH (start:Decision {{decision_id: $decision_id}})
            MATCH path = (start){rel_pattern}{{1,{max_depth}}}(end:Decision)
            RETURN DISTINCT end, length(path) as distance
            ORDER BY distance, end.timestamp
            """
            
            results = self.graph_store.execute_query(query, {
                "decision_id": decision_id
            })
            results = self._extract_records(results)
            
            decisions = []
            for record in results:
                decision_data = record.get("end") if isinstance(record, dict) else None
                if not isinstance(decision_data, dict):
                    decision_data = record if isinstance(record, dict) else {}
                decision = self._dict_to_decision(decision_data)
                decision.metadata["causal_distance"] = record.get("distance", 0)
                decisions.append(decision)
            
            self.logger.info(f"Found {len(decisions)} decisions in {direction} causal chain")
            return decisions
            
        except Exception as e:
            self.logger.error(f"Failed to get causal chain: {e}")
            raise
    
    def get_influenced_decisions(
        self,
        decision_id: str,
        max_depth: int = 10
    ) -> List[Decision]:
        """
        Find decisions influenced by this one.
        
        Args:
            decision_id: Decision ID to find influences for
            max_depth: Maximum traversal depth
            
        Returns:
            List of influenced decisions
        """
        try:
            query = f"""
            MATCH (start:Decision {{decision_id: $decision_id}})
            MATCH path = (start)-[:CAUSED|:INFLUENCED*1..{max_depth}]->(end:Decision)
            RETURN DISTINCT end, length(path) as influence_depth
            ORDER BY influence_depth, end.timestamp
            """
            
            results = self.graph_store.execute_query(query, {
                "decision_id": decision_id
            })
            results = self._extract_records(results)
            
            decisions = []
            for record in results:
                decision_data = record.get("end") if isinstance(record, dict) else None
                if not isinstance(decision_data, dict):
                    decision_data = record if isinstance(record, dict) else {}
                decision = self._dict_to_decision(decision_data)
                decision.metadata["influence_depth"] = record.get("influence_depth", 0)
                decisions.append(decision)
            
            self.logger.info(f"Found {len(decisions)} decisions influenced by {decision_id}")
            return decisions
            
        except Exception as e:
            self.logger.error(f"Failed to get influenced decisions: {e}")
            raise
    
    def get_precedent_chain(
        self,
        decision_id: str,
        max_depth: int = 10
    ) -> List[Decision]:
        """
        Find precedent relationships.
        
        Args:
            decision_id: Decision ID to find precedents for
            max_depth: Maximum traversal depth
            
        Returns:
            List of precedent decisions
        """
        try:
            query = f"""
            MATCH (start:Decision {{decision_id: $decision_id}})
            MATCH path = (start)-[:PRECEDENT_FOR*1..{max_depth}]->(end:Decision)
            RETURN DISTINCT end, length(path) as precedent_depth, 
                   [rel in relationships(path) | rel.type] as relationship_types
            ORDER BY precedent_depth, end.timestamp
            """
            
            results = self.graph_store.execute_query(query, {
                "decision_id": decision_id
            })
            results = self._extract_records(results)
            
            decisions = []
            for record in results:
                decision_data = record.get("end") if isinstance(record, dict) else None
                if not isinstance(decision_data, dict):
                    decision_data = record if isinstance(record, dict) else {}
                decision = self._dict_to_decision(decision_data)
                decision.metadata["precedent_depth"] = record.get("precedent_depth", 0)
                decision.metadata["relationship_types"] = record.get("relationship_types", [])
                decisions.append(decision)
            
            self.logger.info(f"Found {len(decisions)} precedent decisions")
            return decisions
            
        except Exception as e:
            self.logger.error(f"Failed to get precedent chain: {e}")
            raise
    
    def find_causal_loops(self, max_depth: int = 10) -> List[List[str]]:
        """
        Find causal loops in decision graph.
        
        Args:
            max_depth: Maximum depth to search for loops
            
        Returns:
            List of decision ID loops
        """
        try:
            query = f"""
            MATCH path = (d1:Decision)-[:CAUSED|:INFLUENCED*2..{max_depth}]->(d1)
            WHERE ALL(i IN range(0, length(path)-2) | 
                     path[i].decision_id <> path[i+1].decision_id)
            RETURN [node in nodes(path) | node.decision_id] as loop_path,
                   length(path) as loop_length
            ORDER BY loop_length
            """
            
            results = self._extract_records(self.graph_store.execute_query(query))
            
            loops = []
            for record in results:
                loop_path = record.get("loop_path", [])
                if loop_path and len(loop_path) > 2:  # Minimum meaningful loop
                    loops.append(loop_path)
            
            self.logger.info(f"Found {len(loops)} causal loops")
            return loops
            
        except Exception as e:
            self.logger.error(f"Failed to find causal loops: {e}")
            raise
    
    def get_causal_impact_score(self, decision_id: str) -> float:
        """
        Calculate causal impact score for a decision.
        
        Args:
            decision_id: Decision ID to analyze
            
        Returns:
            Impact score (0-1)
        """
        try:
            # Get downstream decisions
            downstream = self.get_influenced_decisions(decision_id, max_depth=5)
            
            if not downstream:
                return 0.0
            
            # Calculate impact based on number of influenced decisions and depth
            total_impact = 0.0
            for decision in downstream:
                depth = decision.metadata.get("influence_depth", 1)
                # Deeper decisions have less direct impact
                impact_weight = 1.0 / depth
                total_impact += impact_weight
            
            # Normalize to 0-1 range
            max_possible_impact = sum(1.0 / i for i in range(1, 6))  # Max depth 5
            normalized_impact = min(total_impact / max_possible_impact, 1.0)
            
            return normalized_impact
            
        except Exception as e:
            self.logger.error(f"Failed to calculate causal impact: {e}")
            return 0.0
    
    def find_root_causes(self, decision_id: str, max_depth: int = 10) -> List[Decision]:
        """
        Find root cause decisions (upstream decisions with no further causes).
        
        Args:
            decision_id: Decision ID to analyze
            max_depth: Maximum traversal depth
            
        Returns:
            List of root cause decisions
        """
        try:
            query = f"""
            MATCH (start:Decision {{decision_id: $decision_id}})
            MATCH path = (start)<-[:CAUSED|:INFLUENCED*1..{max_depth}]-(root:Decision)
            WHERE NOT (root)<-[:CAUSED|:INFLUENCED]-(:Decision)
            RETURN DISTINCT root, length(path) as root_distance
            ORDER BY root_distance
            """
            
            results = self.graph_store.execute_query(query, {
                "decision_id": decision_id
            })
            results = self._extract_records(results)
            
            root_decisions = []
            for record in results:
                decision_data = record.get("root") if isinstance(record, dict) else None
                if not isinstance(decision_data, dict):
                    decision_data = record if isinstance(record, dict) else {}
                decision = self._dict_to_decision(decision_data)
                decision.metadata["root_distance"] = record.get("root_distance", 0)
                root_decisions.append(decision)
            
            self.logger.info(f"Found {len(root_decisions)} root cause decisions")
            return root_decisions
            
        except Exception as e:
            self.logger.error(f"Failed to find root causes: {e}")
            raise
    
    def analyze_causal_network(self, decision_ids: List[str]) -> Dict[str, Any]:
        """
        Analyze causal network for a set of decisions.
        
        Args:
            decision_ids: List of decision IDs to analyze
            
        Returns:
            Network analysis results
        """
        try:
            # Build network metrics
            network_analysis = {
                "total_decisions": len(decision_ids),
                "causal_connections": 0,
                "max_depth": 0,
                "isolated_decisions": [],
                "hub_decisions": [],
                "critical_path": []
            }
            
            # Count connections and find hubs
            connection_counts = {}
            
            for decision_id in decision_ids:
                # Count outgoing connections
                outgoing = self.get_influenced_decisions(decision_id, max_depth=1)
                outgoing_count = len(outgoing)
                
                # Count incoming connections
                incoming = self.get_causal_chain(decision_id, direction="upstream", max_depth=1)
                incoming_count = len(incoming)
                
                total_connections = outgoing_count + incoming_count
                connection_counts[decision_id] = total_connections
                
                if total_connections == 0:
                    network_analysis["isolated_decisions"].append(decision_id)
                
                network_analysis["causal_connections"] += total_connections
            
            # Find hub decisions (top 20% most connected)
            if connection_counts:
                sorted_connections = sorted(
                    connection_counts.items(),
                    key=lambda x: x[1],
                    reverse=True
                )
                hub_count = max(1, len(sorted_connections) // 5)
                network_analysis["hub_decisions"] = [
                    decision_id for decision_id, _ in sorted_connections[:hub_count]
                ]
            
            # Find critical path (longest causal chain)
            max_depth_found = 0
            critical_path_decisions = []
            
            for decision_id in decision_ids:
                chain = self.get_causal_chain(decision_id, direction="downstream", max_depth=10)
                if chain:
                    current_depth = max(d.metadata.get("influence_depth", 0) for d in chain)
                    if current_depth > max_depth_found:
                        max_depth_found = current_depth
                        critical_path_decisions = [d.decision_id for d in chain]
            
            network_analysis["max_depth"] = max_depth_found
            network_analysis["critical_path"] = critical_path_decisions
            
            self.logger.info(f"Analyzed causal network for {len(decision_ids)} decisions")
            return network_analysis
            
        except Exception as e:
            self.logger.error(f"Failed to analyze causal network: {e}")
            raise
    
    def _dict_to_decision(self, data: Dict[str, Any]) -> Decision:
        """Convert dictionary to Decision object."""
        # Handle timestamp conversion
        if isinstance(data.get("timestamp"), str):
            data["timestamp"] = datetime.fromisoformat(data["timestamp"])

        decision_id = data.get("decision_id") or data.get("id")
        if not decision_id:
            raise KeyError("decision_id")

        return Decision(
            decision_id=decision_id,
            category=data.get("category", ""),
            scenario=data.get("scenario", ""),
            reasoning=data.get("reasoning", ""),
            outcome=data.get("outcome", ""),
            confidence=data.get("confidence", 0.0),
            timestamp=data.get("timestamp", datetime.now()),
            decision_maker=data.get("decision_maker", ""),
            reasoning_embedding=data.get("reasoning_embedding"),
            node2vec_embedding=data.get("node2vec_embedding"),
            metadata=data.get("metadata", {}),
        )

    def _extract_records(self, results: Any) -> List[Dict[str, Any]]:
        """Normalize execute_query result shapes to a list of record maps."""
        if isinstance(results, dict):
            records = results.get("records", [])
            return records if isinstance(records, list) else []
        if isinstance(results, list):
            return results
        return []
