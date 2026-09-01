# Knowledge Workbench — single-container build
# Stage 1 builds the Vite browser application; stage 2 is the Python runtime that
# serves the export at / and the FastAPI staging/promote API at /api.
# One service, one port (8020) — per the one-concern-per-Coolify-app rule.
# Byline: Claude Code · Fable 5 · 2026-07-19

# ---- Stage 1: web build -----------------------------------------------------
FROM node:22-alpine AS webbuild
WORKDIR /web
# package.json + package-lock.json first for layer caching; npm ci installs
# exactly what's locked (deterministic) instead of npm install's unconstrained
# resolution against whatever's newest on the registry at build time.
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
# output: Vite production bundle in /web/dist
RUN npm run build

# ---- Stage 2: python runtime ------------------------------------------------
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    STATIC_DIR=/app/static \
    LANCEDB_PATH=/data/lancedb
COPY api/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY api/ ./
COPY --from=webbuild /web/dist /app/static
EXPOSE 8020
# 0.0.0.0 inside the container is fine — host exposure is restricted to
# ${BIND_IP} (tailnet) at the compose port-mapping layer.
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8020"]
