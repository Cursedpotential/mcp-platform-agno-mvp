# =============================================================================
# platform-tools — ONE container for all platform tools (owner decision 2026-06-10)
# =============================================================================
# Hosts, under supervisord:
#   - SBV (SMS Backup & Restore viewer/extractor) — BUILT FROM SOURCE out of the
#     forensic fork at vendored/sbv/ (Cursedpotential/sbv-forensic), so the binary
#     carries our H1/H2/H3 custody hooks. REST API + GUI on :8085.
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
# SBV build-from-source. Stages 1-3 REPRODUCE upstream's own Dockerfile
# (vendored/sbv/Dockerfile) verbatim — node frontend build -> golang:1.25-alpine
# CGO build (-tags "fts5 heic") -> alpine:3 runtime — the only change being the
# COPY source prefixes (vendored/sbv/) for the repo-root build context. The `sbv`
# stage output is byte-for-byte the same layout the old ghcr.io/lowcarbdev/sbv
# image had (/app/sbv + /app/frontend/dist), so the final-stage COPYs are unchanged.
# -----------------------------------------------------------------------------

# Stage 1: Build frontend
FROM node:22-alpine AS sbv-frontend
WORKDIR /app/frontend
COPY vendored/sbv/frontend/package*.json ./
RUN npm ci
COPY vendored/sbv/frontend/ ./
# Relative API path so the SPA calls /api on whatever host it is served from.
ENV VITE_API_URL=/api
RUN npm run build

# Stage 2: Build backend (CGO: SQLite FTS5 + libheif HEIC decode)
FROM golang:1.25-alpine AS sbv-backend
WORKDIR /app
RUN apk add --no-cache gcc g++ musl-dev libheif-dev
COPY vendored/sbv/go.mod vendored/sbv/go.sum ./
RUN go mod download
COPY vendored/sbv/*.go ./
COPY vendored/sbv/internal/*.go internal/
# CGO required for go-sqlite3 (fts5) and libheif; heic tag enables HEIC->JPEG.
RUN CGO_ENABLED=1 go build -tags "fts5 heic" -o sbv .

# Stage 3: Assemble the sbv runtime layout (alpine:3, musl) — same /app layout the
# upstream ghcr image shipped. This is the `sbv` stage the final image lifts from.
FROM alpine:3 AS sbv
WORKDIR /app
RUN apk add --no-cache ca-certificates wget ffmpeg libheif su-exec
COPY --from=sbv-backend /app/sbv .
COPY --from=sbv-frontend /app/frontend/dist ./frontend/dist
COPY vendored/sbv/docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh
RUN mkdir -p /data
ARG SBV_VERSION=forensic-fork
RUN echo "{\"version\":\"${SBV_VERSION}\"}" > /app/version.json
ENV PORT=8081 \
    DB_PATH_PREFIX=/data \
    PUID=1000 \
    PGID=1000

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
