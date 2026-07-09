# =============================================================================
# platform-tools — ONE container for all platform tools (owner decision 2026-06-10)
# =============================================================================
# Hosts, under supervisord:
#   - SBV (SMS Backup & Restore viewer/extractor) — binary LIFTED from the fork's
#     CI-built image ghcr.io/cursedpotential/sbv-forensic (GitHub Actions builds it
#     from vendored/sbv/), carrying our H1/H2/H3 custody hooks. REST API + GUI :8085.
#   - tools-facade (FastAPI, :8090) — one HTTP/MCP surface over the ported
#     parsers/extractors (chat exports, messaging, location, pdf/unstructured)
# Media conversion deps (HEIC/3GP/AMR) come from ffmpeg + libheif.
#
# BUILD CONTEXT = REPO ROOT (compose.yaml/compose.exec.yaml set `context: .`),
# NOT ./docker/tools, because vendored/sbv/ lives at the repo root and must be in
# the context. Every COPY below is therefore repo-root-relative:
#   vendored/sbv/...      SBV fork source (built in stages 1-3)
#   docker/tools/...      this dir's facade + supervisord
# =============================================================================

# -----------------------------------------------------------------------------
# SBV: lift the binary from the FORK'S CI-BUILT IMAGE (built by GitHub Actions
# in Cursedpotential/sbv-forensic from vendored/sbv/, carrying our H1/H2/H3
# custody hooks). We do NOT build SBV from source here: the exec box is 4CPU/8GB
# and a Go/CGO/node build is too heavy for it; GH runners build it for free/fast.
# The fork image's final stage is alpine:3 (musl) with /app/sbv + /app/frontend/
# dist — same layout the old ghcr.io/lowcarbdev/sbv image had, so the final-stage
# COPYs below are unchanged.
# NOTE: this v0.2.x build has HEIC transcode DISABLED (pinned libheif-go no longer
# compiles vs current Alpine libheif — see restore-heic TODO in docs/COORDINATION.md).
# HEIC attachment bytes are still ingested + custody-hashed; only in-app HEIC
# display is off. To bump SBV: build a new tag in the fork, change the tag below.
# -----------------------------------------------------------------------------
FROM ghcr.io/cursedpotential/sbv-forensic:0.2.3-forensic AS sbv

# -----------------------------------------------------------------------------
# Final image: python facade + the SBV binary/assets lifted from the sbv stage.
# The SBV binary is musl-linked (Alpine), so we also carry the musl loader and
# Alpine's shared libs (libheif & friends); supervisord runs it with
# LD_LIBRARY_PATH=/opt/sbv-libs. (These three COPYs are unchanged from the
# ghcr-image version — only the SBV *source* changed, not this layout.)
# -----------------------------------------------------------------------------
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg libheif1 nodejs npm supervisor curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=sbv /app /opt/sbv
COPY --from=sbv /lib/ld-musl-x86_64.so.1 /lib/ld-musl-x86_64.so.1
COPY --from=sbv /usr/lib /opt/sbv-libs

# tools facade (parsers/extractors API) — registry-backed. The `server` package
# is BAKED IN at build (COPY server/ below), NOT bind-mounted: Coolify does not
# honor relative bind mounts, and the exec tier rebuilds this image on every push
# to main anyway, so a self-contained image is strictly better than a runtime
# mount. facade.py imports `server.evidence.registry` + `load_builtin_tools()`,
# which resolves from the baked /opt/tools/server tree.
# pydantic = NormalizedRecord schema dep for the parser tools.
WORKDIR /opt/tools
COPY docker/tools/tools/ /opt/tools/
# The whole server tree: server.evidence.registry pulls in server.evidence.*
# (normalize, tools/*, _sbv_client) + server.vendored.chatminer transitively.
# All lightweight (stdlib + pydantic); heavy modules (api/workflows/core) are
# never imported by load_builtin_tools, so the slim deps below suffice.
COPY server/ /opt/tools/server/
RUN pip install --no-cache-dir fastapi uvicorn python-multipart pydantic

COPY docker/tools/supervisord.conf /etc/supervisor/conf.d/platform-tools.conf
EXPOSE 8080 8090
CMD ["supervisord", "-n", "-c", "/etc/supervisor/supervisord.conf"]
