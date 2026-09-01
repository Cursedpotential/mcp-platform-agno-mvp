"""Deployment contract for LibreChat's ContextForge/Portkey MCP cutover.

Byline: Codex · GPT-5.6-Sol · 2026-08-29
"""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "deploy" / "librechat.yaml"
DOCKERFILE = ROOT / "deploy" / "docker" / "librechat" / "Dockerfile"
CONFIG = ROOT / "deploy" / "docker" / "librechat" / "librechat.yaml"


def test_librechat_bakes_the_tracked_mcp_config() -> None:
    manifest = yaml.safe_load(DEPLOY.read_text(encoding="utf-8"))
    service = manifest["services"]["librechat"]

    assert service["build"] == {"context": ".", "dockerfile": "docker/librechat/Dockerfile"}
    assert all("librechat.yaml:/app/librechat.yaml" not in volume for volume in service["volumes"])
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")
    assert "COPY docker/librechat/librechat.yaml /app/librechat.yaml" in dockerfile
    assert "@sha256:" in dockerfile


def test_librechat_injects_portkey_published_contextforge_settings() -> None:
    manifest = yaml.safe_load(DEPLOY.read_text(encoding="utf-8"))
    environment = manifest["services"]["librechat"]["environment"]
    config = CONFIG.read_text(encoding="utf-8")

    assert "PORTKEY_PLATFORM_TOOLS_MCP_URL" in environment
    assert "PORTKEY_MCP_API_KEY" in environment
    assert "${PORTKEY_PLATFORM_TOOLS_MCP_URL}" in config
    assert "${PORTKEY_MCP_API_KEY}" in config
    assert "x-portkey-api-key: \"${PORTKEY_MCP_API_KEY}\"" in config
    assert 'Authorization: "Bearer ${PORTKEY_MCP_API_KEY}"' not in config
    assert "agentos" not in config.lower()
