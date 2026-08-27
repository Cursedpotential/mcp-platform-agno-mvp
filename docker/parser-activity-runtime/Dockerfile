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
    -o /out/parser-activity-runtime \
    ./cmd/parser-activity-runtime

FROM debian:bookworm-slim

RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates curl tzdata \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 platform \
    && useradd --system --uid 10001 --gid platform --home-dir /nonexistent --shell /usr/sbin/nologin platform \
    && install -d -o platform -g platform -m 0750 /data/uiw/parser-bundles

COPY --from=builder /out/parser-activity-runtime /usr/local/bin/parser-activity-runtime

USER 10001:10001
EXPOSE 8090
ENV PARSER_ACTIVITY_ADDR=:8090 \
    PARSER_BUNDLE_DIR=/data/uiw/parser-bundles

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=4 \
    CMD curl --fail --silent --show-error http://127.0.0.1:8090/healthz || exit 1

ENTRYPOINT ["/usr/local/bin/parser-activity-runtime"]
