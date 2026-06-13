"""
Provenance-enabled wrappers for knowledge graph operations and algorithms.

Provides provenance tracking for KG operations including:
- Graph construction and entity/relationship management
- Node embeddings (node2vec, deepwalk, word2vec)
- Similarity calculations (cosine, euclidean, manhattan, correlation)
- Path finding (BFS, Dijkstra, A*, all shortest paths)
- Link prediction (preferential attachment, jaccard, adamic_adar)
- Centrality measures (degree, betweenness, closeness, eigenvector, PageRank)
- Community detection (label propagation, louvain)
- Connectivity analysis and graph properties

Tracks: graph operations, algorithm executions, parameters, timestamps, and metadata.

Usage:
    from semantica.kg.kg_provenance import GraphBuilderWithProvenance, AlgorithmTrackerWithProvenance
    
    # Graph building with provenance
    graph_builder = GraphBuilderWithProvenance(provenance=True)
    result = graph_builder.build_single_source(graph_data)
    
    # Algorithm tracking with provenance
    tracker = AlgorithmTrackerWithProvenance(provenance=True)
    
    # Track embedding computation
    embed_id = tracker.track_embedding_computation(
        graph=networkx_graph,
        algorithm='node2vec',
        embeddings=computed_embeddings,
        parameters={'embedding_dimension': 128, 'walk_length': 80}
    )
    
    # Track similarity analysis
    sim_id = tracker.track_similarity_calculation(
        embeddings=node_embeddings,
        query_embedding=query_vector,
        similarities=similarity_scores,
        method='cosine'
    )

Supported Algorithms:
- Node Embeddings: node2vec, deepwalk, word2vec, line
- Similarity Metrics: cosine, euclidean, manhattan, correlation, jaccard
- Path Finding: BFS, Dijkstra, A*, all shortest paths, k-shortest paths
- Link Prediction: preferential attachment, jaccard, adamic_adar, resource allocation
- Centrality Measures: degree, betweenness, closeness, eigenvector, PageRank
- Community Detection: label propagation, louvain, leiden, infomap
- Graph Analysis: connected components, graph density, clustering coefficient

Author: Semantica Contributors
License: MIT
Version: 1.0.0
"""

from typing import Any, Dict, List, Optional
import uuid
import time


class GraphBuilderWithProvenance:
    """
    Graph builder with provenance tracking.
    
    Tracks graph construction operations including entity/relationship creation,
    source data lineage, construction parameters, and execution metadata.
    
    Methods:
        build_single_source: Build graph from single data source with provenance
        build: Build graph from multiple sources with provenance
        __getattr__: Delegate other methods to underlying GraphBuilder
    
    Example:
        builder = GraphBuilderWithProvenance(provenance=True)
        result = builder.build_single_source({
            'entities': [{'id': 'person1', 'type': 'Person'}],
            'relationships': [{'source': 'person1', 'target': 'person2', 'type': 'KNOWS'}]
        })
    """
    
    def __init__(self, provenance: bool = False, **config):
        from .graph_builder import GraphBuilder
        
        self.provenance = provenance
        self._builder = GraphBuilder(**config)
        self._prov_manager = None
        
        if provenance:
            try:
                from semantica.provenance import ProvenanceManager
                self._prov_manager = ProvenanceManager()
            except ImportError:
                self.provenance = False
    
    def build(self, sources, **kwargs):
        """Build graph with provenance tracking."""
        # Track the build operation
        if self.provenance and self._prov_manager:
            build_id = f"graph_build_{uuid.uuid4().hex[:8]}"
            self._prov_manager.track_entity(
                entity_id=build_id,
                source="graph_construction",
                metadata={
                    "entity_type": "graph_build_operation",
                    "operation": "build_graph",
                    "sources_count": len(sources) if isinstance(sources, list) else 1,
                    "timestamp": time.time()
                }
            )
        
        result = self._builder.build(sources, **kwargs)
        
        # Track individual entities and relationships if available
        if self.provenance and self._prov_manager and hasattr(result, 'get'):
            try:
                # Try to extract entities and relationships for tracking
                entities = result.get('entities', [])
                relationships = result.get('relationships', [])
                
                for entity in entities:
                    entity_id = entity.get('id') or str(entity.get('name', ''))
                    if entity_id:
                        self._prov_manager.track_entity(
                            entity_id=entity_id,
                            source="graph_construction",
                            entity_type="graph_entity",
                            metadata={
                                "operation": "build_entity",
                                "entity_type": entity.get('type'),
                                "build_id": build_id,
                                "timestamp": time.time()
                            }
                        )
                
                for relationship in relationships:
                    rel_id = relationship.get('id') or f"{relationship.get('source', '')}-{relationship.get('target', '')}"
                    if rel_id:
                        self._prov_manager.track_entity(
                            entity_id=rel_id,
                            source="graph_construction",
                            entity_type="graph_relationship",
                            metadata={
                                "operation": "build_relationship",
                                "relationship_type": relationship.get('type'),
                                "build_id": build_id,
                                "timestamp": time.time()
                            }
                        )
            except Exception as e:
                # Don't fail the build if provenance tracking fails
                pass
        
        return result
    
    def build_single_source(self, kg_data, **kwargs):
        """Build graph from single source with provenance tracking."""
        # Track the build operation
        if self.provenance and self._prov_manager:
            build_id = f"graph_build_single_{uuid.uuid4().hex[:8]}"
            self._prov_manager.track_entity(
                entity_id=build_id,
                source="graph_construction",
                metadata={
                    "entity_type": "graph_build_operation",
                    "operation": "build_single_source",
                    "timestamp": time.time()
                }
            )
        
        result = self._builder.build_single_source(kg_data, **kwargs)
        
        # Track entities and relationships if available
        if self.provenance and self._prov_manager and isinstance(result, dict):
            try:
                entities = result.get('entities', [])
                relationships = result.get('relationships', [])
                
                for entity in entities:
                    entity_id = entity.get('id') or str(entity.get('name', ''))
                    if entity_id:
                        self._prov_manager.track_entity(
                            entity_id=entity_id,
                            source="graph_construction",
                            entity_type="graph_entity",
                            metadata={
                                "operation": "build_entity",
                                "entity_type": entity.get('type'),
                                "build_id": build_id,
                                "timestamp": time.time()
                            }
                        )
                
                for relationship in relationships:
                    rel_id = relationship.get('id') or f"{relationship.get('source', '')}-{relationship.get('target', '')}"
                    if rel_id:
                        self._prov_manager.track_entity(
                            entity_id=rel_id,
                            source="graph_construction",
                            entity_type="graph_relationship",
                            metadata={
                                "operation": "build_relationship",
                                "relationship_type": relationship.get('type'),
                                "build_id": build_id,
                                "timestamp": time.time()
                            }
                        )
            except Exception as e:
                # Don't fail the build if provenance tracking fails
                pass
        
        return result
    
    def __getattr__(self, name):
        """Delegate other methods to the underlying builder."""
        return getattr(self._builder, name)


class AlgorithmTrackerWithProvenance:
    """
    Algorithm execution tracker with provenance tracking.
    
    Tracks KG algorithm executions including embeddings, similarity, paths, links,
    centrality, communities, and graph analysis operations.
    
    Methods:
        track_embedding_computation: Track node embedding algorithm executions
        track_similarity_calculation: Track similarity analysis operations
        track_link_prediction: Track link prediction algorithm executions
        track_centrality_calculation: Track centrality measure calculations
        track_community_detection: Track community detection executions
    
    Example:
        tracker = AlgorithmTrackerWithProvenance(provenance=True)
        
        embed_id = tracker.track_embedding_computation(
            graph=networkx_graph,
            algorithm='node2vec',
            embeddings=computed_embeddings,
            parameters={'embedding_dimension': 128, 'walk_length': 80}
        )
        
        sim_id = tracker.track_similarity_calculation(
            embeddings=node_embeddings,
            query_embedding=query_vector,
            similarities=similarity_scores,
            method='cosine'
        )
    """
    
    def __init__(self, provenance: bool = False, **config):
        self.provenance = provenance
        self._prov_manager = None
        
        if provenance:
            try:
                from semantica.provenance import ProvenanceManager
                self._prov_manager = ProvenanceManager()
            except ImportError:
                self.provenance = False
    
    def track_embedding_computation(
        self,
        graph: Any,
        algorithm: str,
        embeddings: Dict[str, List[float]],
        parameters: Dict[str, Any],
        source: str = None
    ):
        """
        Track node embedding algorithm computation with provenance.
        
        Args:
            graph: Input graph (NetworkX or similar format)
            algorithm: Embedding algorithm name (e.g., 'node2vec', 'deepwalk')
            embeddings: Computed node embeddings {node_id: embedding_vector}
            parameters: Algorithm parameters (embedding_dimension, walk_length, etc.)
            source: Source identifier for provenance tracking
        
        Returns:
            str: Execution ID for tracking and reproducibility
        """
        if self.provenance and self._prov_manager:
            execution_id = f"embedding_{uuid.uuid4().hex[:8]}"
            
            # Track the execution
            self._prov_manager.track_entity(
                entity_id=execution_id,
                source=source or "algorithm_execution",
                metadata={
                    "entity_type": "embedding_computation",
                    "algorithm": algorithm,
                    "parameters": parameters,
                    "input_data_type": type(graph).__name__,
                    "output_data_type": "embeddings",
                    "node_count": len(embeddings),
                    "embedding_dimension": len(next(iter(embeddings.values()))) if embeddings else 0,
                    "timestamp": time.time()
                }
            )
            
            # Track each embedding as separate entity
            for node_id, embedding_vector in embeddings.items():
                self._prov_manager.track_entity(
                    entity_id=f"embedding_{node_id}",
                    source=source or "algorithm_execution",
                    metadata={
                        "entity_type": "node_embedding",
                        "algorithm": algorithm,
                        "node_id": node_id,
                        "embedding_dimension": len(embedding_vector),
                        "execution_id": execution_id,
                        "timestamp": time.time()
                    }
                )
            
            return execution_id
        return None
    
    def track_similarity_calculation(
        self,
        embeddings: Dict[str, List[float]],
        query_embedding: List[float],
        similarities: Dict[str, float],
        method: str,
        source: str = None
    ):
        """
        Track similarity calculation analysis with provenance.
        
        Args:
            embeddings: Node embeddings {node_id: embedding_vector}
            query_embedding: Query embedding vector for similarity comparison
            similarities: Computed similarity scores {node_id: similarity_score}
            method: Similarity method ('cosine', 'euclidean', 'manhattan', 'correlation')
            source: Source identifier for provenance tracking
        
        Returns:
            str: Execution ID for tracking and reproducibility
        """
        if self.provenance and self._prov_manager:
            execution_id = f"similarity_{uuid.uuid4().hex[:8]}"
            
            # Track the execution
            self._prov_manager.track_entity(
                entity_id=execution_id,
                source=source or "algorithm_execution",
                metadata={
                    "entity_type": "similarity_calculation",
                    "algorithm": f"similarity_{method}",
                    "method": method,
                    "input_data_type": "embeddings",
                    "output_data_type": "similarities",
                    "embeddings_count": len(embeddings),
                    "similarities_count": len(similarities),
                    "query_dimension": len(query_embedding),
                    "timestamp": time.time()
                }
            )
            
            # Track similarity results
            for node_id, similarity_score in similarities.items():
                self._prov_manager.track_entity(
                    entity_id=f"similarity_{node_id}_{execution_id}",
                    source=source or "algorithm_execution",
                    metadata={
                        "entity_type": "similarity_result",
                        "method": method,
                        "node_id": node_id,
                        "similarity_score": similarity_score,
                        "execution_id": execution_id,
                        "timestamp": time.time()
                    }
                )
            
            return execution_id
        return None
    
    def track_link_prediction(
        self,
        graph: Any,
        predictions: List[tuple],
        method: str,
        parameters: Dict[str, Any],
        source: str = None
    ):
        """Track link prediction with provenance."""
        if self.provenance and self._prov_manager:
            execution_id = f"link_prediction_{uuid.uuid4().hex[:8]}"
            
            # Track the execution
            self._prov_manager.track_entity(
                entity_id=execution_id,
                source=source or "algorithm_execution",
                metadata={
                    "entity_type": "link_prediction",
                    "algorithm": f"link_prediction_{method}",
                    "method": method,
                    "input_data_type": type(graph).__name__,
                    "output_data_type": "predictions",
                    "predictions_count": len(predictions),
                    "parameters": parameters,
                    "timestamp": time.time()
                }
            )
            
            # Track each prediction
            for i, (node1, node2, score) in enumerate(predictions):
                self._prov_manager.track_entity(
                    entity_id=f"prediction_{execution_id}_{i}",
                    source=source or "algorithm_execution",
                    metadata={
                        "entity_type": "link_prediction_result",
                        "method": method,
                        "node1": node1,
                        "node2": node2,
                        "score": score,
                        "execution_id": execution_id,
                        "timestamp": time.time()
                    }
                )
            
            return execution_id
        return None
    
    def track_centrality_calculation(
        self,
        graph: Any,
        centrality_scores: Dict[str, float],
        method: str,
        parameters: Dict[str, Any],
        source: str = None
    ):
        """
        Track centrality measure calculation with provenance.
        
        Args:
            graph: Input graph (NetworkX or similar format)
            centrality_scores: Computed centrality scores {node_id: centrality_value}
            method: Centrality method ('degree', 'betweenness', 'closeness', 'eigenvector', 'pagerank')
            parameters: Algorithm parameters (normalized, max_iter, alpha, tolerance)
            source: Source identifier for provenance tracking
        
        Returns:
            str: Execution ID for tracking and reproducibility
        """
        if self.provenance and self._prov_manager:
            execution_id = f"centrality_{uuid.uuid4().hex[:8]}"
            
            # Track the execution
            self._prov_manager.track_entity(
                entity_id=execution_id,
                source=source or "algorithm_execution",
                metadata={
                    "entity_type": "centrality_calculation",
                    "algorithm": f"centrality_{method}",
                    "method": method,
                    "input_data_type": type(graph).__name__,
                    "output_data_type": "centrality_scores",
                    "scores_count": len(centrality_scores),
                    "parameters": parameters,
                    "timestamp": time.time()
                }
            )
            
            # Track centrality scores
            for node_id, score in centrality_scores.items():
                self._prov_manager.track_entity(
                    entity_id=f"centrality_{node_id}_{execution_id}",
                    source=source or "algorithm_execution",
                    metadata={
                        "entity_type": "centrality_score",
                        "method": method,
                        "node_id": node_id,
                        "centrality_score": score,
                        "execution_id": execution_id,
                        "timestamp": time.time()
                    }
                )
            
            return execution_id
        return None
    
    def track_community_detection(
        self,
        graph: Any,
        communities: List[List[str]],
        method: str,
        parameters: Dict[str, Any],
        source: str = None
    ):
        """Track community detection with provenance."""
        if self.provenance and self._prov_manager:
            execution_id = f"community_{uuid.uuid4().hex[:8]}"
            
            # Track the execution
            self._prov_manager.track_entity(
                entity_id=execution_id,
                source=source or "algorithm_execution",
                metadata={
                    "entity_type": "community_detection",
                    "algorithm": f"community_detection_{method}",
                    "method": method,
                    "input_data_type": type(graph).__name__,
                    "output_data_type": "communities",
                    "communities_count": len(communities),
                    "parameters": parameters,
                    "timestamp": time.time()
                }
            )
            
            # Track communities
            for i, community in enumerate(communities):
                self._prov_manager.track_entity(
                    entity_id=f"community_{execution_id}_{i}",
                    source=source or "algorithm_execution",
                    metadata={
                        "entity_type": "community",
                        "method": method,
                        "community_id": i,
                        "nodes": community,
                        "community_size": len(community),
                        "execution_id": execution_id,
                        "timestamp": time.time()
                    }
                )
            
            return execution_id
        return None


# Convenience functions for easy access
def create_provenance_enabled_graph_builder(**config):
    """Create a provenance-enabled graph builder."""
    return GraphBuilderWithProvenance(provenance=True, **config)


def create_provenance_enabled_algorithm_tracker(**config):
    """Create a provenance-enabled algorithm tracker."""
    return AlgorithmTrackerWithProvenance(provenance=True, **config)
