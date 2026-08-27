FROM golang:1.25-bookworm AS builder

WORKDIR /src
COPY engine/go.mod engine/go.sum ./engine/
COPY vendored/sbv/go.mod vendored/sbv/go.sum ./vendored/sbv/
WORKDIR /src/engine
RUN go mod download

COPY engine/ /src/engine/
COPY vendored/sbv/ /src/vendored/sbv/
RUN CGO_ENABLED=1 go build \
    -tags fts5 \
    -trimpath \
    -ldflags="-s -w" \
    -o /out/universal-import-worker \
    ./cmd/universal-import-worker

FROM debian:bookworm-slim

RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates tzdata \
    && groupadd --system --gid 10001 platform \
    && useradd --system --uid 10001 --gid platform --home-dir /nonexistent --shell /usr/sbin/nologin platform \
    && install -d -o platform -g platform -m 0750 \
       /data/uiw/source-objects \
       /data/uiw/parser-bundles \
       /data/uiw/normalized-bundles \
       /data/uiw/inventory-manifests

COPY --from=builder /out/universal-import-worker /usr/local/bin/universal-import-worker

USER 10001:10001
ENV SOURCE_OBJECT_DIR=/data/uiw/source-objects \
    PARSER_BUNDLE_DIR=/data/uiw/parser-bundles \
    NORMALIZED_BUNDLE_DIR=/data/uiw/normalized-bundles \
    INVENTORY_MANIFEST_DIR=/data/uiw/inventory-manifests

ENTRYPOINT ["/usr/local/bin/universal-import-worker"]
