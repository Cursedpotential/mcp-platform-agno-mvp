# Toolchain pinned to match modules/engine/go.mod (`go 1.26.6`).
FROM golang:1.26-bookworm AS builder

# Hermetic vendored build (repair post-restructure, 2026-09-02): engine/ moved to
# modules/engine/ and sbv moved to modules/forks/sbv/ (a private, gitignored-locally
# submodule Coolify's clone may not have credentials for). modules/engine/vendor/
# snapshots the full module graph, INCLUDING github.com/lowcarbdev/sbv via the
# go.mod `replace => ../forks/sbv`, so the build needs neither network access nor
# a sibling modules/forks/sbv checkout — proven by building with that directory
# absent. Build context is the repo root (see deploy/*.yaml `context: ..`).
WORKDIR /src/engine
COPY modules/engine/ ./
RUN CGO_ENABLED=1 go build \
    -mod=vendor \
    -tags fts5 \
    -trimpath \
    -ldflags="-s -w" \
    -o /out/proffer-worker \
    ./cmd/proffer-worker

FROM debian:bookworm-slim

RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates tzdata \
    && groupadd --system --gid 10001 platform \
    && useradd --system --uid 10001 --gid platform --home-dir /nonexistent --shell /usr/sbin/nologin platform \
    && install -d -o platform -g platform -m 0750 \
       /data/proffer/source-objects \
       /data/proffer/parser-bundles \
       /data/proffer/normalized-bundles \
       /data/proffer/inventory-manifests

COPY --from=builder /out/proffer-worker /usr/local/bin/proffer-worker

USER 10001:10001
ENV SOURCE_OBJECT_DIR=/data/proffer/source-objects \
    PARSER_BUNDLE_DIR=/data/proffer/parser-bundles \
    NORMALIZED_BUNDLE_DIR=/data/proffer/normalized-bundles \
    INVENTORY_MANIFEST_DIR=/data/proffer/inventory-manifests

ENTRYPOINT ["/usr/local/bin/proffer-worker"]
