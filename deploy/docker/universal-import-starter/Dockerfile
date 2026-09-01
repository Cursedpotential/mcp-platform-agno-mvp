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
    -o /out/universal-import-starter \
    ./temporal/cmd/starter

FROM debian:bookworm-slim

RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates curl tzdata \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 platform \
    && useradd --system --uid 10001 --gid platform --home-dir /nonexistent --shell /usr/sbin/nologin platform

COPY --from=builder /out/universal-import-starter /usr/local/bin/universal-import-starter

USER 10001:10001
EXPOSE 8091
ENV REFERENCE_STARTER_ADDR=:8091
ENV REFERENCE_STARTER_HEALTH_URL=http://127.0.0.1:8091/healthz

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=4 \
    CMD curl --fail --silent --show-error "$REFERENCE_STARTER_HEALTH_URL" || exit 1

ENTRYPOINT ["/usr/local/bin/universal-import-starter"]
