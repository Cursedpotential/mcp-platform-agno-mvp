# Isolated Python 3.12 + SurrealDB SDK 2.0 runner.
# Byline: Codex · GPT-5 · 2026-08-16

FROM ghcr.io/astral-sh/uv:0.8.17 AS uv
FROM python:3.12-slim

COPY --from=uv /uv /uvx /bin/
WORKDIR /runner
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
COPY schema ./schema
COPY queries ./queries
COPY fixtures ./fixtures
RUN uv sync --frozen --no-dev

USER 65532:65532
ENTRYPOINT ["/runner/.venv/bin/python", "-m", "horizon_surreal_phase1.runner"]
