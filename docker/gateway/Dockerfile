# =============================================================================
# gateway — OpenCode + LiteLLM in one container (owner decision 2026-06-10)
# =============================================================================
# Two processes under supervisord (one container, not two):
#   - LiteLLM proxy on :4000 — unified OpenAI-compatible gateway over NVIDIA
#     NIM / Ollama Cloud / Anthropic / etc. (config: litellm-config.yaml)
#   - OpenCode server on :4096 — agent/CLI gateway (`opencode serve`)
# Agents and n8n hit ONE model endpoint (:4000) regardless of provider.

FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl nodejs npm supervisor ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir 'litellm[proxy]' \
    && npm install -g opencode-ai

COPY litellm-config.yaml /etc/litellm/config.yaml
COPY supervisord.conf /etc/supervisor/conf.d/gateway.conf
EXPOSE 4000 4096
CMD ["supervisord", "-n", "-c", "/etc/supervisor/supervisord.conf"]
