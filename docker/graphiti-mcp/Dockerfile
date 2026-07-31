# =============================================================================
# graphiti-mcp — OUR build of the Graphiti MCP server.
# Byline: Claude Code · Fable 5 · 2026-07-31
#
# WHY WE BUILD OUR OWN (owner call 2026-07-31: "I don't believe you're using the
# right image and we should be able to customize our own image... not to mention
# all the side hot fixes"):
#
#   1. zepai/knowledge-graph-mcp:latest was built 2026-03-11 and is UNPINNED —
#      any redeploy could silently pull a different image.
#   2. Upstream DISCARDS the configured Neo4j database for the neo4j provider
#      (factories.py returns only uri/user/password; the falkordb branch does
#      pass it). So NEO4J_DATABASE and config `database:` are dead letters and
#      every instance writes the default DB — which broke our case-memory lane.
#      Fixed by patches/0001-neo4j-database-selection.patch.
#   3. Upstream installs `graphiti-core[neo4j,falkordb]`: `[neo4j]` IS NOT A REAL
#      EXTRA (neo4j>=5.26.0 is a CORE dependency — verified against PyPI 0.29.3)
#      so it is silently ignored, while `[falkordb]` drags in a Redis client we
#      never use. We install the extras we actually want instead.
#   4. The image ignores CONFIG_PATH, so config had to be bind-mounted. We bake it.
#
# REPRODUCIBILITY: upstream is pinned to an immutable commit SHA and our patch is
# committed alongside. `git checkout <sha>` + a patch that must apply cleanly is
# equivalent to vendoring the tree, without dumping ~1k upstream files into this
# repo. If upstream ever changes those anchors the build FAILS LOUDLY rather than
# producing a silently-unpatched image.
# =============================================================================
FROM python:3.11-slim-bookworm

# `patch` and `git` are build-time needs (fetch the pinned upstream, apply our
# hunks); `curl` is also the healthcheck at runtime.
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates git patch \
    && rm -rf /var/lib/apt/lists/*

ADD https://astral.sh/uv/install.sh /uv-installer.sh
RUN sh /uv-installer.sh && rm /uv-installer.sh
ENV PATH="/root/.local/bin:${PATH}"

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    MCP_SERVER_HOST="0.0.0.0" \
    PYTHONUNBUFFERED=1 \
    # No phone-home from a forensic platform. posthog is a CORE dependency of
    # graphiti-core and telemetry defaults to ON; anything other than
    # true/1/yes/on disables it.
    GRAPHITI_TELEMETRY_ENABLED=false \
    # Keep model weights inside the image (see the pre-warm layer below) so a
    # cold start never reaches out to HuggingFace.
    HF_HOME=/opt/models \
    SENTENCE_TRANSFORMERS_HOME=/opt/models

WORKDIR /app/mcp

# Immutable upstream pin. Bump deliberately, never floating.
ARG UPSTREAM_REF=4f62cfe7a2d519e55bfdf2dc4a2fd06649dc00b3
ARG GRAPHITI_CORE_VERSION=0.29.3

# Extras we actually use. NOT falkordb (unused Redis client) and NOT the
# nonexistent [neo4j]. gliner2 = CPU-local NER; sentence-transformers = the
# local BGE reranker fallback (no API key); the rest are provider clients.
ARG GRAPHITI_EXTRAS=anthropic,google-genai,groq,gliner2,sentence-transformers,voyageai,tracing,neo4j-opensearch,neptune

RUN git clone --filter=blob:none --no-checkout https://github.com/getzep/graphiti.git /tmp/graphiti \
    && cd /tmp/graphiti \
    && git sparse-checkout set mcp_server \
    && git checkout -q "${UPSTREAM_REF}" \
    && cp -r /tmp/graphiti/mcp_server/. /app/mcp/ \
    && rm -rf /tmp/graphiti

# The database-selection fix. --forward makes an already-applied patch a no-op
# instead of an error; a genuinely failed hunk still aborts the build.
COPY patches/0001-neo4j-database-selection.patch /tmp/
RUN cd /app/mcp \
    && patch -p2 --forward --batch < /tmp/0001-neo4j-database-selection.patch \
    && grep -q "graph_driver=neo4j_driver" src/graphiti_mcp_server.py \
    && grep -q "'database': database," src/services/factories.py \
    && echo "patch verified in place"

# Swap upstream's dependency line for ours (same mechanism upstream uses).
#
# requires-python is also raised to >=3.11. Upstream declares >=3.10, which makes
# `uv lock` go looking for a 3.10 interpreter that this 3.11 image doesn't have
# (UV_PYTHON_DOWNLOADS=never, deliberately — no surprise interpreter downloads).
# 3.11 is also the correct floor for us regardless: the gliner2 extra is gated on
# python_version >= "3.11", so resolving for 3.10 would silently drop CPU-local NER.
RUN sed -i '/\[tool\.uv\.sources\]/,/graphiti-core/d' pyproject.toml \
    && sed -i 's/^requires-python = ">=3\.10/requires-python = ">=3.11/' pyproject.toml \
    && sed -i "s/graphiti-core\[falkordb\][>=]\+[0-9]\+\.[0-9]\+\.[0-9]\+/graphiti-core[${GRAPHITI_EXTRAS}]==${GRAPHITI_CORE_VERSION}/" pyproject.toml \
    && grep -q "graphiti-core\[${GRAPHITI_EXTRAS}\]==${GRAPHITI_CORE_VERSION}" pyproject.toml \
    && ! grep -q "falkordb" pyproject.toml \
    && grep -q 'requires-python = ">=3.11"' pyproject.toml \
    && rm -f uv.lock \
    && uv lock

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-group dev --extra providers

# Pre-warm model weights into an image layer so cold start is offline and fast.
# Non-fatal: a network hiccup at build time must not break the image, it just
# means first use downloads. Logged either way.
RUN mkdir -p /opt/models && (uv run python -c "\
from gliner2 import GLiNER2; GLiNER2.from_pretrained('fastino/gliner2-large-v1'); print('gliner2 weights cached')" \
    || echo 'WARN: gliner2 pre-warm skipped') \
 && (uv run python -c "\
from sentence_transformers import CrossEncoder; CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2'); print('bge/cross-encoder weights cached')" \
    || echo 'WARN: reranker pre-warm skipped')

# Baked config — this is what kills the CONFIG_PATH bind-mount.
COPY config.yaml /app/mcp/config/config.yaml

RUN mkdir -p /var/log/graphiti \
    && echo "${GRAPHITI_CORE_VERSION}" > /app/mcp/.graphiti-core-version \
    && echo "${UPSTREAM_REF}" > /app/mcp/.upstream-ref

ARG BUILD_DATE
ARG VCS_REF
LABEL org.opencontainers.image.title="Graphiti MCP Server (platform build)" \
      org.opencontainers.image.description="Graphiti MCP server with the Neo4j database-selection fix, CPU-local GLiNER2 NER + BGE reranker, telemetry disabled" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.source="https://github.com/Cursedpotential/mcp-platform-agno-mvp" \
      graphiti.core.version="${GRAPHITI_CORE_VERSION}" \
      graphiti.upstream.ref="${UPSTREAM_REF}"

EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=5s --start-period=60s --retries=5 \
    CMD curl -f http://localhost:8000/health || exit 1
CMD ["uv", "run", "--no-sync", "main.py"]
