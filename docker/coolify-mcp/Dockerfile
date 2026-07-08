# coolify-write MCP server — streamable-HTTP container (ovh-app, behind ContextForge).
# Source of truth for the server code: this repo copy (patched from the local
# stdio skill at ~/.claude/skills/coolify-write/server.py).
# Byline: Claude Code · Fable 5 · 2026-07-08
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .

# HTTP mode defaults — compose/Coolify env can override.
ENV MCP_TRANSPORT=http \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8765 \
    PYTHONUNBUFFERED=1

EXPOSE 8765

CMD ["python", "server.py"]
