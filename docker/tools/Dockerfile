# =============================================================================
# platform-tools — ONE container for all platform tools (owner decision 2026-06-10)
# =============================================================================
# Hosts, under supervisord:
#   - SBV (SMS Backup & Restore viewer/extractor) — binary lifted from the
#     upstream image (lowcarbdev/sbv), REST API on :8080, GUI same port
#   - tools-facade (FastAPI, :8090) — one HTTP/MCP surface over the ported
#     parsers/extractors (chat exports, messaging, location, pdf/unstructured)
# Parser sources live in extracted-code/ until ported into tools/ here.
# Media conversion deps (HEIC/3GP/AMR) come from ffmpeg + libheif.

FROM ghcr.io/lowcarbdev/sbv:stable AS sbv

FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg libheif1 nodejs npm supervisor curl \
    && rm -rf /var/lib/apt/lists/*

# SBV binary + assets from the upstream image. The binary is musl-linked
# (Alpine upstream), so we also carry over the musl loader and Alpine's
# shared libs (libheif & friends); supervisord runs it with
# LD_LIBRARY_PATH=/opt/sbv-libs. Verified working 2026-06-10.
COPY --from=sbv /app /opt/sbv
COPY --from=sbv /lib/ld-musl-x86_64.so.1 /lib/ld-musl-x86_64.so.1
COPY --from=sbv /usr/lib /opt/sbv-libs

# tools facade (parsers/extractors API) — registry-backed. The evidence + the
# cross-domain `tools` packages are now BAKED INTO THE IMAGE (build context =
# repo root) instead of bind-mounted: Coolify's compose deploy only materializes
# .env + the generated compose into the app dir, never the repo tree, so the old
# `./evidence:/opt/tools/evidence` bind-mount was always an empty stub (-> facade
# ModuleNotFoundError, tool_count 0). Baking makes platform-tools a self-contained
# "custom tools" container (owner: consolidate tools here, don't proliferate apps).
# pydantic = NormalizedRecord schema; bs4/pypdf/pdfplumber = HTML/PDF parsers
# (lazily imported by the parser tools, so they only need to resolve at run time).
WORKDIR /opt/tools
COPY docker/tools/tools/ /opt/tools/
COPY evidence/ /opt/tools/evidence/
COPY tools/ /opt/tools/tools/
RUN pip install --no-cache-dir \
        fastapi uvicorn python-multipart pydantic \
        beautifulsoup4 pypdf pdfplumber

COPY docker/tools/supervisord.conf /etc/supervisor/conf.d/platform-tools.conf
EXPOSE 8080 8090
CMD ["supervisord", "-n", "-c", "/etc/supervisor/supervisord.conf"]
