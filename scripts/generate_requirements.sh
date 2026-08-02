#!/bin/bash

############################################################################
#
#    Agno Requirements Generator
#
#    Usage:
#      ./scripts/generate_requirements.sh           # Generate
#      ./scripts/generate_requirements.sh upgrade   # Generate with upgrade
#
############################################################################

set -e

CURR_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "${CURR_DIR}")"

# ---------------------------------------------------------------------------
# Resolve for the DEPLOY target, not the developer's machine.
# ---------------------------------------------------------------------------
# This script ran without --python-platform/--python-version until 2026-08-02,
# so `uv pip compile` resolved against whatever host invoked it — in practice a
# Windows desktop. Platform-conditional dependencies that Linux needs were then
# omitted from requirements.txt, and because deploys run
# `uv pip sync requirements.txt --system` (which REMOVES anything unlisted),
# the resulting image was missing packages the code imports at module scope.
#
# That caused two separate agentos-api boot crash-loops:
#   * 2026-08-01 — authlib/validators (deps of weaviate-client); agno masked it
#     as "Weaviate is not installed", sending the diagnosis the wrong way.
#   * 2026-08-02 — fastmcp (required by AgentOS.get_app() when mcp_server=True)
#     was found orphaned in the image with an EMPTY `pip show` Required-by,
#     i.e. one rebuild away from being swept out.
#
# Targets verified against the running prod container 2026-08-02:
#   Python 3.12.8 · linux · x86_64 · glibc 2.36
# Keep these in step with docker/postgres + the app image base if they change.
PYTHON_VERSION="3.12"
PYTHON_PLATFORM="x86_64-manylinux2014"

# Colors
ORANGE='\033[38;5;208m'
DIM='\033[2m'
BOLD='\033[1m'
NC='\033[0m'

echo ""
echo -e "    ${ORANGE}▸${NC} ${BOLD}Generating requirements.txt${NC}"
echo ""

if [[ "$1" = "upgrade" ]]; then
    echo -e "    ${DIM}Mode: upgrade${NC}"
    echo -e "    ${DIM}> uv pip compile pyproject.toml --no-cache --upgrade --python-version ${PYTHON_VERSION} --python-platform ${PYTHON_PLATFORM} -o requirements.txt${NC}"
    echo ""
    UV_CUSTOM_COMPILE_COMMAND="./scripts/generate_requirements.sh upgrade" \
        uv pip compile ${REPO_ROOT}/pyproject.toml --no-cache --upgrade \
            --python-version "${PYTHON_VERSION}" \
            --python-platform "${PYTHON_PLATFORM}" \
            -o ${REPO_ROOT}/requirements.txt
else
    echo -e "    ${DIM}Mode: standard${NC}"
    echo -e "    ${DIM}> uv pip compile pyproject.toml --no-cache --python-version ${PYTHON_VERSION} --python-platform ${PYTHON_PLATFORM} -o requirements.txt${NC}"
    echo ""
    UV_CUSTOM_COMPILE_COMMAND="./scripts/generate_requirements.sh" \
        uv pip compile ${REPO_ROOT}/pyproject.toml --no-cache \
            --python-version "${PYTHON_VERSION}" \
            --python-platform "${PYTHON_PLATFORM}" \
            -o ${REPO_ROOT}/requirements.txt
fi

echo ""
echo -e "    ${BOLD}Done.${NC}"
echo ""