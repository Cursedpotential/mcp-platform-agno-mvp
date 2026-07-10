"""
Ontology Generation Module

This module handles automatic generation of ontologies from data and text using
a 6-stage pipeline that transforms raw data into structured OWL ontologies.

Key Features:
    - Automatic ontology generation (6-stage pipeline)
    - Class and property inference
    - Ontology structure optimization
    - Domain-specific ontology creation
    - Ontology quality assessment
    - Semantic network parsing
    - Hierarchy generation

Main Classes:
    - OntologyGenerator: Main ontology generation class (6-stage pipeline)
    - ClassInferencer: Class inference engine (legacy alias)
    - PropertyInferencer: Property inference engine (legacy alias)
    - OntologyOptimizer: Ontology optimization engine

Example Usage:
    >>> from semantica.ontology import OntologyGenerator
    >>> generator = OntologyGenerator(base_uri="https://example.org/ontology/")
    >>> ontology = generator.generate_ontology({"entities": [...], "relationships": [...]})
    >>> classes = generator.infer_classes(data)
    >>> properties = generator.infer_properties(data, classes)

Author: Semantica Contributors
License: MIT
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from ..utils.exceptions import ProcessingError, ValidationError
from ..utils.logging import get_logger
from ..utils.progress_tracker import get_progress_tracker
from .class_inferrer import ClassInferrer
from .namespace_manager import NamespaceManager
from .naming_conventions import NamingConventions
from .property_generator import PropertyGenerator
from .ontology_validator import OntologyValidator


class OntologyGenerator:
    """
    Ontology generation handler with 6-stage pipeline.

    6-Stage Pipeline:
    1. Semantic Network Parsing → Extract domain concepts
    2. YAML-to-Definition → Transform into class definitions
    3. Definition-to-Types → Map to OWL types
    4. Hierarchy Generation → Build taxonomic structures
    5. TTL Generation → Generate OWL/Turtle syntax using rdflib, triplet generation (subject-predicate-object)
    6. Symbolic Validation → HermiT/Pellet reasoning

    • Generates ontologies from data and text
    • Infers classes and properties automatically
    • Creates domain-specific ontologies
    • Optimizes ontology structure
    • Validates ontology quality
    • Supports various ontology formats
    """

    def __init__(self, config=None, **kwargs):
        """
        Initialize ontology generator.

        Sets up the ontology generator with namespace management, naming conventions,
        and inference engines for classes and properties.

        Args:
            config: Configuration dictionary
            **kwargs: Additional configuration options:
                - base_uri: Base URI for ontology (default: "https://semantica.dev/ontology/")
                - namespace_manager: Optional namespace manager instance
                - min_occurrences: Minimum occurrences for class inference (default: 2)

        Example:
            ```python
            generator = OntologyGenerator(
                base_uri="https://example.org/ontology/",
                min_occurrences=3
            )
            ```
        """
        self.logger = get_logger("ontology_generator")
        self.config = config or {}
        self.config.update(kwargs)

        # Initialize progress tracker
        self.progress_tracker = get_progress_tracker()
        # Ensure progress tracker is enabled
        if not self.progress_tracker.enabled:
            self.progress_tracker.enabled = True

        # Initialize components
        self.namespace_manager = self.config.get(
            "namespace_manager"
        ) or NamespaceManager(**self.config)
        self.naming_conventions = NamingConventions(**self.config)
        self.class_inferrer = ClassInferrer(
            namespace_manager=self.namespace_manager, **self.config
        )
        self.property_generator = PropertyGenerator(
            namespace_manager=self.namespace_manager, **self.config
        )
        self.validator = OntologyValidator(**self.config)

        self.supported_formats = ["owl", "ttl", "rdf", "json-ld"]

    def generate_ontology(self, data: Dict[str, Any], **options) -> Dict[str, Any]:
        """
        Generate ontology from data using 5-stage pipeline.

        Executes the complete 5-stage ontology generation pipeline:
        1. Semantic Network Parsing: Extract domain concepts from entities/relationships
        2. YAML-to-Definition: Transform concepts into class definitions
        3. Definition-to-Types: Map definitions to OWL types
        4. Hierarchy Generation: Build taxonomic structures
        5. TTL Generation: (Handled by OWLGenerator)

        Args:
            data: Input data dictionary containing:
                - entities: List of entity dictionaries
                - relationships: List of relationship dictionaries
                - semantic_network: Optional pre-parsed semantic network
            **options: Generation options:
                - name: Ontology name (default: "GeneratedOntology")
                - build_hierarchy: Whether to build class hierarchy (default: True)
                - namespace_manager: Optional namespace manager instance

        Returns:
            Generated ontology dictionary containing:
                - uri: Ontology URI
                - name: Ontology name
                - version: Version string
                - classes: List of class definitions
                - properties: List of property definitions
                - metadata: Additional metadata

        Example:
            ```python
            generator = OntologyGenerator(base_uri="https://example.org/ontology/")
            ontology = generator.generate_ontology({
                "entities": [{"type": "Person", "name": "John"}],
                "relationships": [{"type": "worksFor", "source": "John", "target": "Acme"}]
            })
            ```
        """
        tracking_id = self.progress_tracker.start_tracking(
            module="ontology",
            submodule="OntologyGenerator",
            message="Generating ontology using 6-stage pipeline",
        )

        try:
            self.logger.info("Starting ontology generation pipeline")

            # Stage 1: Semantic Network Parsing
            self.progress_tracker.update_tracking(
                tracking_id, message="Stage 1: Parsing semantic network..."
            )
            semantic_network = self._stage1_parse_semantic_network(data, **options)

            # Stage 2: YAML-to-Definition
            self.progress_tracker.update_tracking(
                tracking_id, message="Stage 2: Converting to class definitions..."
            )
            definitions = self._stage2_yaml_to_definition(semantic_network, **options)

            # Stage 3: Definition-to-Types
            self.progress_tracker.update_tracking(
                tracking_id, message="Stage 3: Mapping to OWL types..."
            )
            
            # Ensure entities and relationships are available for property inference
            stage3_options = options.copy()
            # Use normalized entities and relationships from stage 1 if available
            stage3_options["entities"] = semantic_network.get("entities", data.get("entities", []))
            stage3_options["relationships"] = semantic_network.get("relationships", data.get("relationships", []))
            
            typed_definitions = self._stage3_definition_to_types(definitions, **stage3_options)

            # Stage 4: Hierarchy Generation
            self.progress_tracker.update_tracking(
                tracking_id, message="Stage 4: Building class hierarchy..."
            )
            ontology = self._stage4_hierarchy_generation(typed_definitions, **options)

            # Stage 5: TTL Generation (handled by OWLGenerator)

            # Stage 6: Symbolic Validation
            if options.get("validate", True):
                self.progress_tracker.update_tracking(
                    tracking_id, message="Stage 6: Validating ontology..."
                )
                validation_result = self.validator.validate(ontology)
                ontology["validation"] = {
                    "valid": validation_result.valid,
                    "consistent": validation_result.consistent,
                    "satisfiable": validation_result.satisfiable,
                    "errors": validation_result.errors,
                    "warnings": validation_result.warnings
                }
                if not validation_result.valid:
                    self.logger.warning(f"Ontology validation failed: {validation_result.errors}")

            self.progress_tracker.stop_tracking(
                tracking_id,
                status="completed",
                message=f"Generated ontology with {len(ontology.get('classes', []))} classes, {len(ontology.get('properties', []))} properties",
            )
            return ontology

        except Exception as e:
            self.progress_tracker.stop_tracking(
                tracking_id, status="failed", message=str(e)
            )
            raise

    def generate_from_graph(self, graph: Dict[str, Any], **options) -> Dict[str, Any]:
        """
        Generate ontology from a knowledge graph.

        Alias for generate_ontology.

        Args:
            graph: Knowledge graph dictionary (output from GraphBuilder)
            **options: Additional options

        Returns:
            Generated ontology dictionary
        """
        return self.generate_ontology(graph, **options)

    def _stage1_parse_semantic_network(
        self, data: Dict[str, Any], **options
    ) -> Dict[str, Any]:
        """
        Stage 1: Parse semantic network from data.

        Extract domain concepts from entities and relationships.
        """
        raw_entities = data.get("entities", [])
        relationships = data.get("relationships", [])

        # Normalize entities
        entities = []

        def process_entity(ent):
            """Normalize entity to dictionary."""
            if isinstance(ent, dict):
                return ent
            # Handle Entity object (from NERExtractor)
            if hasattr(ent, "label") and hasattr(ent, "text"):
                return {
                    "type": ent.label,
                    "name": ent.text,
                    "entity_type": ent.label,
                    "text": ent.text,
                    "start_char": getattr(ent, "start_char", 0),
                    "end_char": getattr(ent, "end_char", 0),
                    "confidence": getattr(ent, "confidence", 1.0),
                    "metadata": getattr(ent, "metadata", {}),
                }
            # Handle list/tuple (legacy or raw format)
            if isinstance(ent, (list, tuple)) and len(ent) >= 2:
                # Assume [text, label, ...]
                return {
                    "name": str(ent[0]),
                    "text": str(ent[0]),
                    "type": str(ent[1]),
                    "entity_type": str(ent[1]),
                }
            return None

        # Handle list of lists (batch output) or flat list
        for item in raw_entities:
            if isinstance(item, list):
                # Check if it's a list of entities (batch) or a single entity as list
                # If the first element is also a list or Entity object, it's a batch
                if len(item) > 0 and (
                    isinstance(item[0], list) or hasattr(item[0], "label")
                ):
                    for sub_item in item:
                        processed = process_entity(sub_item)
                        if processed:
                            entities.append(processed)
                else:
                    # Treat as single entity [text, label]
                    processed = process_entity(item)
                    if processed:
                        entities.append(processed)
            else:
                processed = process_entity(item)
                if processed:
                    entities.append(processed)

        # Extract concepts
        concepts = {}
        for entity in entities:
            entity_type = entity.get("type") or entity.get("entity_type", "Entity")
            if entity_type not in concepts:
                concepts[entity_type] = {"instances": [], "relationships": []}
            concepts[entity_type]["instances"].append(entity)

        # Extract relationships
        normalized_relationships = []
        for rel_item in relationships:
            # Normalize relationship to dictionary
            rel = None
            if isinstance(rel_item, dict):
                rel = rel_item
            elif hasattr(rel_item, "subject") and hasattr(rel_item, "predicate") and hasattr(rel_item, "object"):
                # Handle Relation object (subject, predicate, object)
                rel = {
                    "source": getattr(rel_item, "subject"),
                    "type": getattr(rel_item, "predicate"),
                    "target": getattr(rel_item, "object"),
                    "relationship_type": getattr(rel_item, "predicate"),
                    "source_type": getattr(rel_item, "source_type", "Entity"),
                    "target_type": getattr(rel_item, "target_type", "Entity"),
                    "confidence": getattr(rel_item, "confidence", 1.0),
                    "metadata": getattr(rel_item, "metadata", {}),
                }
            elif hasattr(rel_item, "source") and hasattr(rel_item, "type") and hasattr(rel_item, "target"):
                 # Handle Relation object (source, type, target) - alternative
                rel = {
                    "source": getattr(rel_item, "source"),
                    "type": getattr(rel_item, "type"),
                    "target": getattr(rel_item, "target"),
                    "relationship_type": getattr(rel_item, "type"),
                    "source_type": getattr(rel_item, "source_type", "Entity"),
                    "target_type": getattr(rel_item, "target_type", "Entity"),
                    "confidence": getattr(rel_item, "confidence", 1.0),
                    "metadata": getattr(rel_item, "metadata", {}),
                }
            elif isinstance(rel_item, (list, tuple)) and len(rel_item) >= 3:
                # Assume [source, type, target] (RDF triplet style)
                # or [source, target, type]
                # Heuristic: if 2nd element is short and looks like a relation, assume [source, type, target]
                rel = {
                    "source": str(rel_item[0]),
                    "type": str(rel_item[1]),
                    "target": str(rel_item[2]),
                    "relationship_type": str(rel_item[1]),
                    "source_type": "Entity",
                    "target_type": "Entity",
                }
            
            if not rel:
                continue

            rel_type = rel.get("type") or rel.get("relationship_type", "relatedTo")
            source_type = rel.get("source_type")
            target_type = rel.get("target_type")

            # Try to resolve source/target types if not provided
            if not source_type or source_type == "Entity":
                # Look up source in entities list to find its type
                source_name = rel.get("source")
                for ent in entities:
                    if ent.get("name") == source_name or ent.get("text") == source_name:
                        source_type = ent.get("type") or ent.get("entity_type")
                        break
            
            if not target_type or target_type == "Entity":
                 # Look up target in entities list to find its type
                target_name = rel.get("target")
                for ent in entities:
                    if ent.get("name") == target_name or ent.get("text") == target_name:
                        target_type = ent.get("type") or ent.get("entity_type")
                        break
            
            # Update rel with resolved types
            rel["source_type"] = source_type
            rel["target_type"] = target_type
            
            normalized_relationships.append(rel)

            if source_type and source_type in concepts:
                concepts[source_type]["relationships"].append(rel)

        return {
            "concepts": concepts,
            "entities": entities,
            "relationships": normalized_relationships,
        }

    def _stage2_yaml_to_definition(
        self, semantic_network: Dict[str, Any], **options
    ) -> Dict[str, Any]:
        """
        Stage 2: Transform semantic network to class definitions.

        Convert concepts to structured class definitions.
        """
        concepts = semantic_network.get("concepts", {})
        entities = semantic_network.get("entities", [])

        # Infer classes from entities
        classes = self.class_inferrer.infer_classes(entities, **options)

        # Create definitions
        definitions = {
            "classes": classes,
            "properties": [],
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "concept_count": len(concepts),
            },
        }

        return definitions

    def _stage3_definition_to_types(
        self, definitions: Dict[str, Any], **options
    ) -> Dict[str, Any]:
        """
        Stage 3: Map definitions to OWL types.

        Convert class definitions to OWL-compliant types.
        """
        classes = definitions.get("classes", [])
        relationships = options.get("relationships", [])
        entities = options.get("entities", [])

        # Clean options for infer_properties to avoid multiple values for arguments
        prop_options = options.copy()
        prop_options.pop("entities", None)
        prop_options.pop("relationships", None)

        # Infer properties
        properties = self.property_generator.infer_properties(
            entities=entities, relationships=relationships, classes=classes, **prop_options
        )

        # Add types to classes
        for cls in classes:
            cls["@type"] = "owl:Class"
            if "uri" not in cls:
                cls["uri"] = self.namespace_manager.generate_class_iri(cls["name"])

        # Add types to properties
        for prop in properties:
            if prop["type"] == "object":
                prop["@type"] = "owl:ObjectProperty"
            else:
                prop["@type"] = "owl:DatatypeProperty"

            if "uri" not in prop:
                prop["uri"] = self.namespace_manager.generate_property_iri(prop["name"])

        return {
            "classes": classes,
            "properties": properties,
            "metadata": definitions.get("metadata", {}),
        }

    def _stage4_hierarchy_generation(
        self, typed_definitions: Dict[str, Any], **options
    ) -> Dict[str, Any]:
        """
        Stage 4: Build taxonomic structures.

        Generate class hierarchies and property relationships.
        """
        classes = typed_definitions.get("classes", [])
        properties = typed_definitions.get("properties", [])

        # Build class hierarchy
        classes = self.class_inferrer.build_class_hierarchy(classes, **options)

        # Build ontology structure
        ontology = {
            "uri": self.namespace_manager.get_base_uri(),
            "name": options.get("name", "GeneratedOntology"),
            "version": self.namespace_manager.version,
            "classes": classes,
            "properties": properties,
            "imports": [],
            "metadata": {
                **typed_definitions.get("metadata", {}),
                "class_count": len(classes),
                "property_count": len(properties),
            },
        }

        return ontology

    def infer_classes(self, data: Dict[str, Any], **options) -> List[Dict[str, Any]]:
        """
        Infer ontology classes from data.

        Args:
            data: Input data
            **options: Additional options

        Returns:
            List of inferred classes
        """
        entities = data.get("entities", [])
        return self.class_inferrer.infer_classes(entities, **options)

    def infer_properties(
        self, data: Dict[str, Any], classes: List[Dict[str, Any]], **options
    ) -> List[Dict[str, Any]]:
        """
        Infer ontology properties from data.

        Args:
            data: Input data
            classes: List of class definitions
            **options: Additional options

        Returns:
            List of inferred properties
        """
        entities = data.get("entities", [])
        relationships = data.get("relationships", [])

        return self.property_generator.infer_properties(
            entities=entities, relationships=relationships, classes=classes, **options
        )

    def optimize_ontology(self, ontology: Dict[str, Any], **options) -> Dict[str, Any]:
        """
        Optimize ontology structure and quality.

        Args:
            ontology: Ontology dictionary
            **options: Additional options

        Returns:
            Optimized ontology
        """
        optimizer = OntologyOptimizer(**self.config)
        return optimizer.optimize_ontology(ontology, **options)


class ClassInferencer:
    """
    Class inference engine (legacy compatibility).

    • Infers ontology classes from data
    • Handles class hierarchies
    • Manages class relationships
    • Processes class constraints
    """

    def __init__(self, **config):
        """Initialize class inferencer."""
        self.class_inferrer = ClassInferrer(**config)

    def infer_classes(self, data, **options):
        """Infer classes from data."""
        entities = data.get("entities", []) if isinstance(data, dict) else data
        return self.class_inferrer.infer_classes(entities, **options)

    def build_class_hierarchy(self, classes, **options):
        """Build class hierarchy."""
        return self.class_inferrer.build_class_hierarchy(classes, **options)

    def validate_classes(self, classes, **criteria):
        """Validate classes."""
        return self.class_inferrer.validate_classes(classes, **criteria)


class PropertyInferencer:
    """
    Property inference engine (legacy compatibility).

    • Infers ontology properties from data
    • Handles property domains and ranges
    • Manages property relationships
    • Processes property constraints
    """

    def __init__(self, **config):
        """Initialize property inferencer."""
        self.property_generator = PropertyGenerator(**config)

    def infer_properties(self, data, classes, **options):
        """Infer properties from data and classes."""
        entities = data.get("entities", []) if isinstance(data, dict) else []
        relationships = data.get("relationships", []) if isinstance(data, dict) else []

        return self.property_generator.infer_properties(
            entities=entities, relationships=relationships, classes=classes, **options
        )

    def infer_domains_and_ranges(self, properties, classes):
        """Infer domains and ranges."""
        return self.property_generator.infer_domains_and_ranges(properties, classes)

    def validate_properties(self, properties, **criteria):
        """Validate properties."""
        return self.property_generator.validate_properties(properties, **criteria)


class OntologyOptimizer:
    """
    Ontology optimization engine.

    • Optimizes ontology structure
    • Removes redundant elements
    • Improves ontology coherence
    • Manages optimization metrics
    """

    def __init__(self, **config):
        """
        Initialize ontology optimizer.

        Args:
            **config: Configuration options
        """
        self.logger = get_logger("ontology_optimizer")
        self.config = config

    def optimize_ontology(self, ontology: Dict[str, Any], **options) -> Dict[str, Any]:
        """
        Optimize ontology structure.

        Args:
            ontology: Ontology dictionary
            **options: Additional options

        Returns:
            Optimized ontology
        """
        optimized = dict(ontology)

        # Remove redundancy
        if options.get("remove_redundancy", True):
            optimized = self.remove_redundancy(optimized)

        # Improve coherence
        if options.get("improve_coherence", True):
            optimized = self.improve_coherence(optimized)

        return optimized

    def remove_redundancy(self, ontology: Dict[str, Any]) -> Dict[str, Any]:
        """
        Remove redundant elements from ontology.

        Args:
            ontology: Ontology dictionary

        Returns:
            Cleaned ontology
        """
        # Remove duplicate classes
        classes = ontology.get("classes", [])
        seen_names = set()
        unique_classes = []

        for cls in classes:
            class_name = cls.get("name")
            if class_name and class_name not in seen_names:
                seen_names.add(class_name)
                unique_classes.append(cls)

        ontology["classes"] = unique_classes

        # Remove duplicate properties
        properties = ontology.get("properties", [])
        seen_prop_names = set()
        unique_properties = []

        for prop in properties:
            prop_name = prop.get("name")
            if prop_name and prop_name not in seen_prop_names:
                seen_prop_names.add(prop_name)
                unique_properties.append(prop)

        ontology["properties"] = unique_properties

        return ontology

    def improve_coherence(self, ontology: Dict[str, Any]) -> Dict[str, Any]:
        """
        Improve ontology coherence.

        Args:
            ontology: Ontology dictionary

        Returns:
            Improved ontology
        """
        # Ensure all classes have required fields
        classes = ontology.get("classes", [])
        for cls in classes:
            if "uri" not in cls:
                cls["uri"] = cls.get("name", "Entity")
            if "label" not in cls:
                cls["label"] = cls.get("name", "Entity")

        # Ensure all properties have domains and ranges
        properties = ontology.get("properties", [])
        for prop in properties:
            if prop.get("type") == "object":
                if "domain" not in prop or not prop["domain"]:
                    prop["domain"] = ["owl:Thing"]
                if "range" not in prop or not prop["range"]:
                    prop["range"] = ["owl:Thing"]

        return ontology
