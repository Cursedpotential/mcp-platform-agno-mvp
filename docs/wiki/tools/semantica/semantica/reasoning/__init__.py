"""
Reasoning Module

This module provides reasoning and inference capabilities for knowledge graph
analysis and query answering, supporting multiple reasoning strategies including
rule-based inference via Rete, SPARQL reasoning, abductive and deductive reasoning.
"""

from .reasoner import Reasoner, InferenceResult, Rule, Fact, RuleType
from .graph_reasoner import GraphReasoner
from .explanation_generator import (
    Explanation,
    ExplanationGenerator,
    Justification,
    ReasoningPath,
    ReasoningStep,
)
from .rete_engine import (
    AlphaNode,
    BetaNode,
    Match,
    ReteEngine,
    ReteNode,
    TerminalNode,
)
from .sparql_reasoner import SPARQLQueryResult, SPARQLReasoner

__all__ = [
    # Reasoner facade
    "Reasoner",
    "GraphReasoner",
    "InferenceResult",
    "Rule",
    "Fact",
    "RuleType",
    # Rete engine
    "ReteEngine",
    "ReteNode",
    "AlphaNode",
    "BetaNode",
    "TerminalNode",
    "Match",
    # SPARQL reasoning
    "SPARQLReasoner",
    "SPARQLQueryResult",
    # Explanation
    "ExplanationGenerator",
    "Explanation",
    "ReasoningStep",
    "ReasoningPath",
    "Justification",
]
