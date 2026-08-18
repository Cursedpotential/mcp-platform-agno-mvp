"""Production composition contracts for native-only evidence cutover.

Byline: Codex · GPT-5 · 2026-08-18
"""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "server" / "api" / "main.py"
EXEC_MANIFEST = ROOT / "deploy" / "exec.yaml"


def _knowledge_bases() -> dict[str, str]:
    tree = ast.parse(MAIN.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == "_KNOWLEDGE_BASES":
                return ast.literal_eval(node.value)
    raise AssertionError("_KNOWLEDGE_BASES assignment not found")


def test_agentos_compatibility_bases_exclude_evidence() -> None:
    """Evidence has no legacy selectable base or fallback collection."""
    bases = _knowledge_bases()

    assert bases == {
        "legal": "legal_knowledge",
        "personal_history": "personal_history_knowledge",
        "context": "platform_context",
    }
    assert "evidence_knowledge" not in MAIN.read_text(encoding="utf-8")


def test_native_routes_are_registered_only_behind_the_activation_gate() -> None:
    """Disabled native evidence exposes no search route and no legacy substitute."""
    source = MAIN.read_text(encoding="utf-8")
    gate = "if _native_evidence_runtime is not None:"
    registration = "register_native_evidence_search_routes(app, native_runtime=_native_evidence_runtime)"

    gate_at = source.index(gate, source.index("register_ingest_routes(app, native_projector)"))
    registration_at = source.index(registration)
    assert gate_at < registration_at
    assert source[gate_at:registration_at].strip().endswith(gate)


def test_exec_manifest_requires_native_activation_inputs_and_blue_ports() -> None:
    """Coolify supplies activation/security/target values without checked-in secrets."""
    manifest = EXEC_MANIFEST.read_text(encoding="utf-8")

    required_inputs = {
        "NATIVE_EVIDENCE_ENABLED": "${NATIVE_EVIDENCE_ENABLED:?",
        "WEAVIATE_HTTP_HOST": "${WEAVIATE_HTTP_HOST:?",
        "WALK_PASS_SIGNING_KEY": "${WALK_PASS_SIGNING_KEY:?",
        "EVIDENCE_OPERATOR_SECURITY_KEY": "${EVIDENCE_OPERATOR_SECURITY_KEY:?",
    }
    for key, interpolation in required_inputs.items():
        assert f"{key}: {interpolation}" in manifest

    assert "WEAVIATE_HTTP_PORT: ${WEAVIATE_HTTP_PORT:-8082}" in manifest
    assert "WEAVIATE_GRPC_PORT: ${WEAVIATE_GRPC_PORT:-50052}" in manifest
