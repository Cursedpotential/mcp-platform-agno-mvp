# ===========================================================================
# Platform API runtime
# ===========================================================================

FROM agnohq/python:3.12

# ---------------------------------------------------------------------------
# System dependencies
# ---------------------------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/*

# ---------------------------------------------------------------------------
# Application code
# ---------------------------------------------------------------------------
WORKDIR /app
ENV PYTHONPATH=/app
COPY requirements.txt ./
RUN uv pip sync requirements.txt --system
# pymilvus REMOVED 2026-08-09 (D-042): owner ruled the Milvus->Weaviate cutover verified
# (ADR-0040), and its transitive grpcio pin was what made requirements.txt unsatisfiable.
# Legacy Milvus paths (server/analysis/milvus_forensic.py, vendored semantica milvus_store)
# import pymilvus lazily and raise a helpful install message if ever invoked.
COPY . .

# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
RUN chmod +x /app/scripts/entrypoint.sh
ENTRYPOINT ["/app/scripts/entrypoint.sh"]

# ---------------------------------------------------------------------------
# Default production API command
# ---------------------------------------------------------------------------
CMD ["uvicorn", "server.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
